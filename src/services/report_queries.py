# -*- coding: utf-8 -*-
from collections import defaultdict
from database import db
from models import CmdbAttributeDict, CmdbObject, CmdbValue

UNKNOWN_NODE = u'\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e'

def get_cmdb_type_summary():
    rows = db.session.query(
        CmdbObject.object_type,
        db.func.count(CmdbObject.id)
    ).group_by(CmdbObject.object_type).all()

    all_types = sorted([row[0] for row in rows])
    type_counts = {row[0]: row[1] for row in rows}
    return all_types, type_counts

def get_attribute_names(object_type):
    rows = db.session.query(CmdbAttributeDict.name) \
        .join(CmdbValue, CmdbValue.attribute_id == CmdbAttributeDict.id) \
        .join(CmdbObject, CmdbValue.object_id == CmdbObject.id) \
        .filter(CmdbObject.object_type == object_type) \
        .distinct().all()
    return sorted([row[0] for row in rows])

def load_objects_with_values(object_type, newest_first=False):
    objects_query = CmdbObject.query.filter_by(object_type=object_type) \
        .options(db.joinedload(CmdbObject.node))
    if newest_first:
        objects_query = objects_query.order_by(CmdbObject.created_at.desc())

    objects = objects_query.all()
    object_ids = [obj.id for obj in objects]

    values_by_object = defaultdict(list)
    if object_ids:
        values = CmdbValue.query.filter(CmdbValue.object_id.in_(object_ids)) \
            .options(db.joinedload(CmdbValue.attribute)).all()
        for value in values:
            values_by_object[value.object_id].append(value)

    return objects, values_by_object

def empty_report_context():
    return {
        'types': [],
        'type_counts': {},
        'active_type': None,
        'columns': [],
        'records': [],
        'total_nodes': 0,
    }

def build_cmdb_report_context(object_type):
    all_types, type_counts = get_cmdb_type_summary()
    if not object_type:
        context = empty_report_context()
        context['types'] = all_types
        context['type_counts'] = type_counts
        return context

    columns = get_attribute_names(object_type)
    objects, values_by_object = load_objects_with_values(object_type, newest_first=True)

    unique_nodes = set()
    records = []
    for obj in objects:
        if obj.node:
            unique_nodes.add(obj.node_id)

        row = {
            '__node': obj.node.display_name if obj.node else UNKNOWN_NODE,
            '__created_at': obj.created_at.strftime('%Y-%m-%d %H:%M'),
        }
        for value in values_by_object[obj.id]:
            row[value.attribute.name] = value.value
        records.append(row)

    return {
        'types': all_types,
        'type_counts': type_counts,
        'active_type': object_type,
        'columns': columns,
        'records': records,
        'total_nodes': len(unique_nodes),
    }
