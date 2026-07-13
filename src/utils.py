# -*- coding: utf-8 -*-
from collections import namedtuple
from operator import itemgetter
from os.path import basename, join, splitext
import os
import datetime as dt
import json
import pkg_resources
import sqlite3
import string
import threading

import six
from flask import current_app, flash
from markupsafe import Markup
from jinja2 import Template

from database import db
from models import (
    DistributedQuery, DistributedQueryTask,
    Node, Pack, Query, ResultLog, querypacks,
)


Field = namedtuple('Field', ['name', 'action', 'columns', 'timestamp'])

# Получаем директорию текущего скрипта
base_dir = os.path.dirname(os.path.abspath(__file__))
schema_path = os.path.join(base_dir, 'resources', 'osquery_schema.sql')

with open(schema_path, 'r', encoding='utf-8') as f:
    schema = f.read()
# Читаем DDL-выражения из пакета.
# schema = pkg_resources.resource_string('src', join('resources', 'osquery_schema.sql'))
# schema = schema.decode('utf-8')
schema = [x for x in schema.strip().split('\n') if not x.startswith('--')]

# SQLite в Python будет ругаться при попытке использовать его из нескольких потоков.
# Создаем thread-local переменную с базой данных, которая лениво инициализируется.
osquery_mock_db = threading.local()


from config_assembler import assemble_configuration, assemble_distributed_queries


RESULT_IDENTITY_KEYS = {
    u'Система и ОС': (('uuid',), ('hostname',), ('computer_name',)),
    u'Процессор': (('device_id',),),
    u'Оперативная память': (('device_locator',), ('serial_number',), ('bank_locator', 'part_number')),
    u'Физические диски': (('disk_index',), ('id',), ('serial',)),
    u'Логические диски': (('device_id',),),
    u'Установленное ПО': (
        ('identifying_number',),
        ('name', 'version', 'publisher'),
        ('name', 'install_location'),
    ),
    u'Сетевые интерфейсы': (('interface',), ('mac',), ('friendly_name',)),
    u'IP-адреса': (('interface', 'address'), ('address',),),
    u'Маршруты': (('destination', 'netmask', 'gateway', 'interface'),),
    u'Открытые порты': (('address', 'port', 'protocol', 'family'),),
}


def clean_result_name(name):
    return (name or '').split('/')[-1]


def result_identity(name, columns):
    columns = columns or {}
    query_name = clean_result_name(name)

    for keys in RESULT_IDENTITY_KEYS.get(query_name, ()):
        if all(columns.get(key) not in (None, '') for key in keys):
            return {key: columns.get(key) for key in keys}

    for keys in (
        ('id',),
        ('uuid',),
        ('device_id',),
        ('name',),
        ('address',),
    ):
        if all(columns.get(key) not in (None, '') for key in keys):
            return {key: columns.get(key) for key in keys}

    return columns


def create_query_pack_from_upload(upload):
    '''
    Создает пакет и запросы из файла пакета запросов. **Важно**: если пакет
    уже существует под именем загружаемого файла, все описанные здесь запросы
    будут добавлены в существующий пакет. Однако если запрос с таким именем
    уже существует, но его SQL отличается, будет создан новый запрос с тем же
    именем и другим id, чтобы не перезаписать существующий запрос. Если SQL
    идентичен, будет повторно использован существующий запрос.

    '''
    # Модуль json в Python 3 ожидает вход типа `str`, поэтому читаем тело
    # и при необходимости приводим его к правильному типу.
    body = upload.data.read()
    if not isinstance(body, six.string_types):
        body = body.decode('utf-8')

    try:
        data = json.loads(body)
    except ValueError:
        flash(u"Could not load pack as JSON - ensure it is JSON encoded",
              'danger')
        return None
    else:
        if 'queries' not in data:
            flash(u"No queries in pack", 'danger')
            return None

        name = splitext(basename(upload.data.filename))[0]
        pack = Pack.query.filter(Pack.name == name).first()

    if not pack:
        current_app.logger.debug("Creating pack %s", name)
        pack = Pack.create(name=name, **data)

    for query_name, query in data['queries'].items():
        if not validate_osquery_query(query['query']):
            flash('Invalid osquery query: "{0}"'.format(query['query']), 'danger')
            return None

        q = Query.query.filter(Query.name == query_name).first()

        if not q:
            q = Query.create(name=query_name, **query)
            pack.queries.append(q)
            current_app.logger.debug("Adding new query %s to pack %s",
                                     q.name, pack.name)
            continue

        if q in pack.queries:
            continue

        if q.sql == query['query']:
            current_app.logger.debug("Adding existing query %s to pack %s",
                                     q.name, pack.name)
            pack.queries.append(q)
        else:
            q2 = Query.create(name=query_name, **query)
            current_app.logger.debug(
                "Created another query named %s, but different sql: %r vs %r",
                query_name, q2.sql, q.sql)
            pack.queries.append(q2)

    else:
        pack.save()
        flash(u"Imported query pack {0}".format(pack.name), 'success')

    return pack


def get_node_health(node):
    checkin_interval = current_app.config['INVENTORY_CHECKIN_INTERVAL']
    if isinstance(checkin_interval, (int, float)):
        checkin_interval = dt.timedelta(seconds=checkin_interval)
    if (dt.datetime.utcnow() - node.last_checkin) > checkin_interval:
        return u'danger'
    else:
        return ''


# Не лучшее решение дублировать это и здесь, и в JS, но удобного способа
# передать данные из JS в Python или обратно здесь нет.
PRETTY_OPERATORS = {
    'equal': 'equals',
    'not_equal': "doesn't equal",
    'begins_with': 'begins with',
    'not_begins_with': "doesn't begins with",
    'contains': 'contains',
    'not_contains': "doesn't contain",
    'ends_with': 'ends with',
    'not_ends_with': "doesn't end with",
    'is_empty': 'is empty',
    'is_not_empty': 'is not empty',
    'less': 'less than',
    'less_or_equal': 'less than or equal',
    'greater': 'greater than',
    'greater_or_equal': 'greater than or equal',
    'matches_regex': 'matches regex',
    'not_matches_regex': "doesn't match regex",
}

def pretty_operator(cond):
    return PRETTY_OPERATORS.get(cond, cond)


PRETTY_FIELDS = {
    'query_name': 'Query name',
    'action': 'Action',
    'host_identifier': 'Host identifier',
    'timestamp': 'Timestamp',
}

def pretty_field(field):
    return PRETTY_FIELDS.get(field, field)


# Так как 'string.printable' включает управляющие символы.
PRINTABLE = string.ascii_letters + string.digits + string.punctuation + ' '


def quote(s, quote='"'):
    buf = [quote]
    for ch in s:
        if ch == quote or ch == '\\':
            buf.append('\\')
            buf.append(ch)
        elif ch == '\n':
            buf.append('\\n')
        elif ch == '\r':
            buf.append('\\r')
        elif ch == '\t':
            buf.append('\\t')
        elif ch in PRINTABLE:
            buf.append(ch)
        else:
            # Hex-экранирование.
            buf.append('\\x')
            buf.append(hex(ord(ch))[2:])

    buf.append(quote)
    return ''.join(buf)


def create_mock_db():
    mock_db = sqlite3.connect(':memory:')
    for ddl in schema:
        mock_db.execute(ddl)

    extra_schema = current_app.config.get('INVENTORY_EXTRA_SCHEMA', [])
    for ddl in extra_schema:
        mock_db.execute(ddl)

    return mock_db


def validate_osquery_query(query):
    # Проверяем, есть ли у этого потока экземпляр базы данных SQLite.
    db = getattr(osquery_mock_db, 'db', None)
    if db is None:
        db = create_mock_db()
        osquery_mock_db.db = db

    try:
        db.execute(query)
    except sqlite3.Error:
        current_app.logger.exception("Invalid query: %s", query)
        return False

    return True


def learn_from_result(result, node):
    if not result['data']:
        return

    capture_columns = set(
        map(itemgetter(0),
            current_app.config['INVENTORY_CAPTURE_NODE_INFO']
        )
    )

    if not capture_columns:
        return

    node_info = node.get('node_info', {})
    orig_node_info = node_info.copy()

    for _, action, columns, _, in extract_results(result):
        # Обновляем только колонки, общие для обоих наборов.
        for column in capture_columns & set(columns):

            cvalue = node_info.get(column)  # текущее значение
            value = columns.get(column)

            if action == 'removed' and (cvalue is None or cvalue != value):
                pass
            elif action == 'removed' and cvalue == value:
                node_info.pop(column)
            elif action == 'added' and (cvalue is None or cvalue != value):
                node_info[column] = value

    # Обновляем node_info только при фактическом изменении.

    if orig_node_info == node_info:
        return

    node = Node.get_by_id(node['id'])
    node.update(node_info=node_info)
    return


def process_result(result, node):
    if not result['data']:
        current_app.logger.error("No results to process from %s", node)
        return

    for name, action, columns, timestamp, in extract_results(result):
        if action == 'removed':
            continue

        identity = result_identity(name, columns)
        existing = ResultLog.query.filter(
            ResultLog.node_id == node.id,
            ResultLog.name == name,
        )
        if identity == columns:
            existing = existing.filter(ResultLog.columns == columns)
        else:
            existing = existing.filter(ResultLog.columns.contains(identity))
        existing = existing.first()

        if existing:
            existing.update(
                action='added',
                columns=columns,
                timestamp=timestamp,
                commit=False,
            )
            continue

        yield ResultLog(name=name,
                        action='added',
                        columns=columns,
                        timestamp=timestamp,
                        node_id=node.id)


def extract_results(result):
    """
    Преобразует входящие данные логов в последовательность Field, нормализуя
    и/или агрегируя пакетный и событийный форматы в пакетный формат,
    используемый во всей остальной части inventory.
    """
    if not result['data']:
        return

    timefmt = '%a %b %d %H:%M:%S %Y UTC'
    strptime = dt.datetime.strptime

    for entry in result['data']:
        name = entry['name']
        timestamp = strptime(entry['calendarTime'], timefmt)

        if 'columns' in entry:
            yield Field(name=name,
                        action=entry['action'],
                        columns=entry['columns'],
                        timestamp=timestamp)

        elif 'diffResults' in entry:
            added = entry['diffResults']['added']
            removed = entry['diffResults']['removed']
            for (action, items) in (('added', added), ('removed', removed)):
                # items может быть "", поэтому итерация все еще безопасна;
                # дополнительно гарантируем, что не вернем пустое значение columns.
                for columns in items:
                    yield Field(name=name,
                                action=action,
                                columns=columns,
                                timestamp=timestamp)

        elif 'snapshot' in entry:
            for columns in entry['snapshot']:
                yield Field(name=name,
                            action='added',
                            columns=columns,
                            timestamp=timestamp)

        else:
            current_app.logger.error("Encountered a result entry that "
                                     "could not be processed! %s",
                                     json.dumps(entry))


def flash_errors(form):
    '''http://flask.pocoo.org/snippets/12/'''
    for field, errors in form.errors.items():
        for error in errors:
            message = u"Ошибка в поле «{0}»: {1}".format(
                getattr(form, field).label.text, error
            )
            flash(message, 'danger')


def get_paginate_options(request, model, choices, existing_query=None,
                         default='id', page=1, max_pp=20, default_sort='asc'):

    try:
        per_page = int(request.args.get('pp', max_pp))
    except Exception:
        per_page = 20

    per_page = max(0, min(max_pp, per_page))

    order_by = request.args.get('order_by', 'id')
    if order_by not in choices:
        order_by = default
    order_by = getattr(model, order_by, 'id')

    sort = request.args.get('sort', default_sort)
    if sort not in ('asc', 'desc'):
        sort = default_sort

    order_by = getattr(order_by, sort)()

    if existing_query:
        query = existing_query.order_by(order_by)
    else:
        query = model.query.order_by(order_by)

    query = query.paginate(page=page, per_page=per_page)
    return query


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, dt.datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)


def render_column(value, column):
    renders = current_app.config.get('INVENTORY_COLUMN_RENDER', {})
    if column not in renders:
        return value

    template = renders[column]

    try:
        if callable(template):
            return template(value)
        else:
            template = Template(template, autoescape=True)
            rendered = template.render(value=value)

            # Возвращаем объект markup, чтобы шаблон, где он рендерится,
            # не экранировал его повторно.

            return Markup(rendered)
    except Exception:
        current_app.logger.exception(
            "Failed to render %s, returning original value",
            column
        )
        return value


from localization import ru_translate

def relative_time(value):
    if not value:
        return u'Никогда'
    
    # Если значение является строковым представлением даты.
    if isinstance(value, six.string_types):
        try:
            if '.' in value:
                value = dt.datetime.strptime(value.split('.')[0], '%Y-%m-%d %H:%M:%S')
            else:
                value = dt.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except Exception:
            try:
                value = dt.datetime.strptime(value, '%Y-%m-%d %H:%M')
            except Exception:
                return value
                
    if not isinstance(value, dt.datetime):
        return value

    now = dt.datetime.utcnow()
    diff = now - value

    if diff.total_seconds() < 0:
        return u'Только что'

    seconds = diff.total_seconds()
    if seconds < 60:
        return u'Только что'
    elif seconds < 3600:
        minutes = int(seconds // 60)
        if minutes == 1:
            return u'1 минуту назад'
        elif 2 <= minutes <= 4 or (22 <= minutes <= 24) or (32 <= minutes <= 34) or (42 <= minutes <= 44) or (52 <= minutes <= 54):
            return u'{0} минуты назад'.format(minutes)
        else:
            return u'{0} минут назад'.format(minutes)
    elif seconds < 86400:
        hours = int(seconds // 3600)
        if hours == 1:
            return u'1 час назад'
        elif 2 <= hours <= 4 or hours == 22 or hours == 23:
            return u'{0} часа назад'.format(hours)
        else:
            return u'{0} часов назад'.format(hours)
    else:
        days = int(seconds // 86400)
        if days == 1:
            return u'1 день назад'
        elif 2 <= days <= 4 or (days % 10 in [2, 3, 4] and days % 100 not in [12, 13, 14]):
            return u'{0} дня назад'.format(days)
        else:
            return u'{0} дней назад'.format(days)

