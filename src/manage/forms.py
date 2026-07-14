# -*- coding: utf-8 -*-
import json

from flask import current_app
from flask_wtf import FlaskForm as Form
from flask_wtf.file import FileField, FileRequired, FileAllowed

from wtforms.fields import (
    BooleanField,
    DateTimeField,
    Field,
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
    TextAreaField
)
from wtforms.validators import DataRequired, Optional, ValidationError
from wtforms.widgets import HiddenInput

from models import Rule
from utils import validate_osquery_query


class ValidSQL(object):
    def __init__(self, message=None):
        if not message:
            message = u'Поле должно содержать корректный SQL-запрос для таблиц osquery'
        self.message = message

    def __call__(self, form, field):
        if not validate_osquery_query(field.data):
            raise ValidationError(self.message)


class HiddenJSONField(Field):
    widget = HiddenInput()

    def _value(self):
        if self.data:
            return json.dumps(self.data)
        else:
            return u''

    def process_formdata(self, incoming):
        if incoming:
            self.data = json.loads(incoming[0])
        else:
            self.data = None


class UploadPackForm(Form):

    pack = FileField(u'Файл конфигурации пакета', validators=[FileRequired()])


class CreatePackForm(Form):

    name = StringField(u'Название пакета', validators=[DataRequired()])
    platform = SelectField(u'Платформа', default='all', choices=[
        ('all', u'Все'),
        ('darwin', 'Darwin'),
        ('linux', 'Linux'),
        ('freebsd', 'FreeBSD'),
        ('posix', u'POSIX-совместимые'),
        ('windows', 'Windows'),
    ])
    version = StringField(u'Версия', validators=[Optional()])
    description = TextAreaField(u'Описание', validators=[Optional()])
    shard = IntegerField(u'Охват хостов (%)', validators=[Optional()])
    tags = TextAreaField(u'Метки хостов', validators=[DataRequired(message=u"Укажите хотя бы одну метку хоста для применения пакета.")])

    def validate(self, **kwargs):
        from models import Pack
        initial_validation = super(CreatePackForm, self).validate(**kwargs)
        if not initial_validation:
            return False

        pack = Pack.query.filter(Pack.name == self.name.data).first()
        if pack:
            self.name.errors.append(
                u"Пакет с названием {0} уже существует.".format(
                self.name.data)
            )
            return False

        return True


class QueryForm(Form):

    name = StringField(u'Название', validators=[DataRequired()])
    sql = TextAreaField(u'Запрос', validators=[DataRequired(), ValidSQL()])
    interval = IntegerField(u'Интервал, сек.', default=3600, validators=[DataRequired()])
    platform = SelectField(u'Платформа', default='all', choices=[
        ('all', u'Все'),
        ('darwin', 'Darwin'),
        ('linux', 'Linux'),
        ('freebsd', 'FreeBSD'),
        ('posix', u'POSIX-совместимые'),
        ('windows', 'Windows'),
    ])
    version = StringField(u'Версия')
    description = TextAreaField(u'Описание')
    value = TextAreaField(u'Значение')
    removed = BooleanField(u'Записывать удалённые строки?', default=False)
    packs = SelectField(u'Пакеты', default='', choices=[
    ])
    tags = TextAreaField(u'Метки')
    shard = IntegerField(u'Охват хостов (%)', validators=[Optional()])

    def set_choices(self):
        from models import Pack
        self.packs.choices = [('', u'— Не выбран —')] + [
            (pack.name, pack.name)
            for pack in Pack.query.order_by(Pack.name).all()
        ]


class UpdateQueryForm(QueryForm):

    def __init__(self, *args, **kwargs):
        super(UpdateQueryForm, self).__init__(*args, **kwargs)
        self.set_choices()
        query = kwargs.pop('obj', None)
        if query:
            self.packs.process_data(query.packs[0].name if query.packs else '')
            self.tags.process_data('\n'.join(t.value for t in query.tags))


class CreateQueryForm(QueryForm):

    def validate(self, **kwargs):
        from models import Query
        initial_validation = super(CreateQueryForm, self).validate(**kwargs)
        if not initial_validation:
            return False

        query = Query.query.filter(Query.name == self.name.data).first()
        if query:
            self.name.errors.append(
                u"Запрос с названием {0} уже существует.".format(
                self.name.data)
            )
            return False

        return True


class UploadQueryForm(Form):
    query_file = FileField(u'Файл запроса (.json или .sql)', validators=[FileRequired()])
    packs = SelectField(u'Пакет запросов (опционально)', default='', choices=[])
    tags = TextAreaField(u'Метки хостов (опционально, одна на строку)')

    def set_choices(self):
        from models import Pack
        self.packs.choices = [('', u'— Не выбран —')] + [
            (pack.name, pack.name)
            for pack in Pack.query.order_by(Pack.name).all()
        ]


class AddDistributedQueryForm(Form):

    sql = TextAreaField(u'Запрос', validators=[DataRequired(), ValidSQL()])
    description = TextAreaField(u'Описание', validators=[Optional()])
    not_before = DateTimeField(u'Запустить не ранее', format="%Y-%m-%d %H:%M:%S",
                               validators=[Optional()])
    nodes = SelectMultipleField(u'Агенты', choices=[])
    tags = SelectMultipleField(u'Метки', choices=[])

    def set_choices(self):
        from models import Node, Tag
        self.nodes.choices = [
            (node.node_key, node.display_name or node.host_identifier)
            for node in Node.query.order_by(Node.host_identifier).all()
        ]
        self.tags.choices = [
            (tag.value, tag.value)
            for tag in Tag.query.order_by(Tag.value).all()
        ]


class CreateTagForm(Form):
    value = TextAreaField(u'Метка', validators=[DataRequired()])


class FilePathForm(Form):
    category = StringField(u'Категория', validators=[DataRequired()])
    target_paths = TextAreaField(u'Файлы', validators=[DataRequired()])
    tags = TextAreaField(u'Метки')


class FilePathUpdateForm(FilePathForm):

    def __init__(self, *args, **kwargs):
        super(FilePathUpdateForm, self).__init__(*args, **kwargs)
        # self.set_choices()
        file_path = kwargs.pop('obj', None)
        if file_path:
            self.target_paths.process_data('\n'.join(file_path.get_paths()))
            self.tags.process_data('\n'.join(t.value for t in file_path.tags))


class RuleForm(Form):

    name = StringField(u'Название правила', validators=[DataRequired()])
    alerters = SelectMultipleField(u'Каналы оповещения', default=None, choices=[
    ])
    description = TextAreaField(u'Описание', validators=[Optional()])
    conditions = HiddenJSONField(u'Условия')

    def set_choices(self):
        alerter_ids = list(current_app.config.get('INVENTORY_ALERTER_PLUGINS', {}).keys())
        self.alerters.choices = [(a, a.title()) for a in alerter_ids]


class CreateRuleForm(RuleForm):

    def validate(self, **kwargs):
        from models import Rule

        initial_validation = super(CreateRuleForm, self).validate(**kwargs)
        if not initial_validation:
            return False

        query = Rule.query.filter(Rule.name == self.name.data).first()
        if query:
            self.name.errors.append(
                u"Правило с названием {0} уже существует.".format(
                self.name.data)
            )
            return False

        return True


class UpdateRuleForm(RuleForm):

    def __init__(self, *args, **kwargs):
        super(UpdateRuleForm, self).__init__(*args, **kwargs)
        self.set_choices()


class UpdateNodeForm(Form):

    display_name = StringField(u'Название', validators=[Optional()])
    is_active = BooleanField(u'Активен', validators=[Optional()])


class UploadOfflineLogsForm(Form):
    logs_file = FileField(u'Файл результатов сбора (.json или .log)', validators=[
        FileRequired(),
        FileAllowed(['json', 'log'], u'Допускаются только файлы с расширением .json или .log')
    ])

    def validate_logs_file(self, field):
        if field.data:
            max_size = 20 * 1024 * 1024 # 20MB
            field.data.seek(0, 2)
            size = field.data.tell()
            field.data.seek(0)
            if size > max_size:
                raise ValidationError(u"Размер файла превышает максимально допустимый предел (20 МБ).")
