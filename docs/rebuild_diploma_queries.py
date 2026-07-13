# -*- coding: utf-8 -*-
"""
Пересобирает плановые пакеты osquery для дипломного демонстрационного стенда.

Скрипт сохраняет агентов и узлы, удаляет старые плановые пакеты запросов,
очищает ранее собранные строки инвентаризации и создает один компактный
пакет инвентаризации Windows.
"""
from application import create_app
from database import db
from models import (
    CmdbObject,
    CmdbValue,
    DistributedQuery,
    DistributedQueryResult,
    DistributedQueryTask,
    Node,
    Pack,
    Query,
    ResultLog,
    Tag,
    pack_tags,
    query_tags,
    querypacks,
)
from settings import Config
from utils import validate_osquery_query


import json
import os

# Получаем директорию этого скрипта.
script_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(script_dir, 'diploma_base_inventory.json')

with open(json_path, 'r', encoding='utf-8') as f:
    pack_data = json.load(f)

INTERVAL_SECONDS = 20
PACK_TAG = u"диплом"
PACK_NAME = u"Диплом: базовая инвентаризация"
PACK_DESCRIPTION = pack_data.get('description', u'')

QUERY_SPECS = []
for q_name, q_val in pack_data.get('queries', {}).items():
    QUERY_SPECS.append({
        "name": q_name,
        "category": q_val.get('value', u''),
        "description": q_val.get('description', u''),
        "sql": q_val.get('query', u'')
    })



def get_or_create_tag(value):
    tag = Tag.query.filter_by(value=value).first()
    if tag:
        return tag
    tag = Tag(value=value)
    db.session.add(tag)
    db.session.flush()
    return tag


def add_tag_once(target, tag):
    if tag.value not in [existing.value for existing in target.tags]:
        target.tags.append(tag)


def validate_queries():
    invalid = []
    for spec in QUERY_SPECS:
        if not validate_osquery_query(spec["sql"]):
            invalid.append(spec["name"])
    if invalid:
        raise RuntimeError(
            u"Некорректные SQL-запросы: {0}".format(u", ".join(invalid))
        )


def rebuild():
    validate_queries()

    old_packs = Pack.query.count()
    old_queries = Query.query.count()
    old_results = ResultLog.query.count()

    db.session.execute(querypacks.delete())
    db.session.execute(pack_tags.delete())
    db.session.execute(query_tags.delete())

    deleted_distributed_results = DistributedQueryResult.query.delete(
        synchronize_session=False
    )
    deleted_distributed_tasks = DistributedQueryTask.query.delete(
        synchronize_session=False
    )
    deleted_distributed_queries = DistributedQuery.query.delete(
        synchronize_session=False
    )
    deleted_result_logs = ResultLog.query.delete(synchronize_session=False)
    deleted_cmdb_values = CmdbValue.query.delete(synchronize_session=False)
    deleted_cmdb_objects = CmdbObject.query.delete(synchronize_session=False)
    deleted_queries = Query.query.delete(synchronize_session=False)
    deleted_packs = Pack.query.delete(synchronize_session=False)

    diploma_tag = get_or_create_tag(PACK_TAG)
    pack = Pack(
        name=PACK_NAME,
        platform="windows",
        version="1.0.0",
        description=PACK_DESCRIPTION,
    )
    pack.tags = [diploma_tag]
    db.session.add(pack)

    for spec in QUERY_SPECS:
        category_tag = get_or_create_tag(spec["category"])
        query = Query(
            name=spec["name"],
            sql=spec["sql"],
            interval=INTERVAL_SECONDS,
            platform="windows",
            description=spec["description"],
            value=spec["category"],
            removed=False,
        )
        db.session.add(query)
        query.tags = [diploma_tag, category_tag]
        pack.queries.append(query)

    tagged_nodes = 0
    for node in Node.query.filter_by(is_active=True).all():
        before = len(node.tags)
        add_tag_once(node, diploma_tag)
        if len(node.tags) != before:
            tagged_nodes += 1

    db.session.commit()

    print(u"Готово.")
    print(u"Старые пакеты: {0}, удалено: {1}".format(old_packs, deleted_packs))
    print(u"Старые запросы: {0}, удалено: {1}".format(old_queries, deleted_queries))
    print(u"Новый пакет: {0}".format(PACK_NAME))
    print(u"Новых запросов: {0}".format(len(QUERY_SPECS)))
    print(u"Интервал каждого запроса: {0} секунд".format(INTERVAL_SECONDS))
    print(u"Метка пакета и агентов: {0}".format(PACK_TAG))
    print(u"Агентов промаркировано: {0}".format(tagged_nodes))
    print(u"Старые ResultLog: {0}, удалено: {1}".format(old_results, deleted_result_logs))
    print(u"Удалено CMDB objects/values: {0}/{1}".format(deleted_cmdb_objects, deleted_cmdb_values))
    print(
        u"Удалено оперативных запросов/tasks/results: {0}/{1}/{2}".format(
            deleted_distributed_queries,
            deleted_distributed_tasks,
            deleted_distributed_results,
        )
    )


if __name__ == "__main__":
    app = create_app(Config)
    with app.app_context():
        rebuild()
