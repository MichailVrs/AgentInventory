# -*- coding: utf-8 -*-
import logging
from sqlalchemy.exc import IntegrityError
from database import db
from models import CmdbObject, CmdbAttributeDict, CmdbValue
from utils import extract_results

logger = logging.getLogger(__name__)

def resolve_node_id(node_id):
    """
    Разрешает ID узла из переданного значения (которое может быть dict или ID).
    """
    if not node_id:
        return None
    if isinstance(node_id, dict):
        return node_id.get('id')
    return node_id

def extract_object_type(query_name):
    """
    Извлекает тип объекта из имени запроса.
    """
    if not query_name:
        return None
    clean_name = query_name.split('/')[-1]
    if clean_name.startswith('cmdb_'):
        return clean_name[5:]
    elif 'cmdb_' in clean_name:
        return clean_name.split('cmdb_')[-1]
    return clean_name

def load_attribute_cache(results):
    """
    Предотвращение N+1 SELECT-запросов: загружаем только те атрибуты,
    которые присутствуют в текущей пачке результатов.
    """
    keys = set()
    for _, _, columns, _ in results:
        keys.update(columns.keys())

    if not keys:
        return {}

    attributes = CmdbAttributeDict.query.filter(CmdbAttributeDict.name.in_(keys)).all()
    return {attr.name: attr for attr in attributes}

def replace_snapshot_objects(node_id, object_type, action, cleared_types):
    """
    Удаляет старые данные при обнаружении снимка (snapshot) и добавляет тип в cleared_types.
    """
    if action == 'snapshot' and object_type not in cleared_types:
        objects_to_delete = CmdbObject.query.filter_by(node_id=node_id, object_type=object_type).all()
        for obj in objects_to_delete:
            db.session.delete(obj)
        cleared_types.add(object_type)
        db.session.flush()

def get_or_create_attribute(key, attributes_cache):
    attr = attributes_cache.get(key)
    if attr:
        return attr

    # Double check database to see if another parallel task created it
    attr = CmdbAttributeDict.query.filter_by(name=key).first()
    if attr:
        attributes_cache[key] = attr
        return attr

    # Create using a nested transaction (savepoint) to recover from IntegrityError
    db.session.begin_nested()
    try:
        attr = CmdbAttributeDict(name=key, data_type='string')
        db.session.add(attr)
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        attr = CmdbAttributeDict.query.filter_by(name=key).first()

    attributes_cache[key] = attr
    return attr

def persist_cmdb_object(node_id, object_type, action, columns, attributes_cache):
    """
    Создает CmdbObject и сохраняет связанные значения CmdbValue.
    """
    if action not in ('added', 'snapshot'):
        return

    obj = CmdbObject(node_id=node_id, object_type=object_type)
    db.session.add(obj)
    db.session.flush()

    for key, value in columns.items():
        attr = get_or_create_attribute(key, attributes_cache)
        str_val = str(value)
        val = CmdbValue(object_id=obj.id, attribute_id=attr.id, value=str_val)
        db.session.add(val)

def normalize_to_cmdb_service(result, node_id):
    """
    Нормализует результаты Osquery в EAV-модель CMDB.
    """
    node_id = resolve_node_id(node_id)
    if not node_id:
        return

    logger.debug("normalize_to_cmdb task received for node_id: %s", node_id)

    cleared_types = set()
    results = list(extract_results(result))
    logger.debug("Extracted %d results from batch", len(results))

    attributes_cache = load_attribute_cache(results)

    try:
        for name, action, columns, timestamp in results:
            object_type = extract_object_type(name)
            if not object_type:
                continue

            replace_snapshot_objects(node_id, object_type, action, cleared_types)
            persist_cmdb_object(node_id, object_type, action, columns, attributes_cache)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("Failed to normalize to CMDB: %s", e)
        raise
    return
