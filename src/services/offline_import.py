# -*- coding: utf-8 -*-
import json

from flask import current_app

from database import db
from models import Node


def decode_upload_body(file_data):
    body = file_data.read()
    if isinstance(body, bytes):
        body = body.decode('utf-8')
    return body


def parse_offline_records(body):
    records = []
    try:
        parsed = json.loads(body)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except ValueError:
        pass

    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records


def group_records_by_host(records):
    grouped = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        host_id = record.get('hostIdentifier') or record.get('host_identifier')
        if not host_id:
            continue
        grouped.setdefault(host_id, []).append(record)
    return grouped


def find_hostname(records):
    for record in records:
        columns = record.get('columns', {})
        if 'hostname' in columns:
            return columns['hostname']
    return None


def get_or_create_offline_node(host_id, records):
    node = Node.query.filter(
        (Node.host_identifier == host_id) | (Node.node_key == host_id)
    ).first()
    return node


def import_grouped_records(grouped):
    from tasks import analyze_result, learn_from_result, normalize_to_cmdb
    from utils import process_result

    nodes_updated = 0
    for host_id, records in grouped.items():
        node = get_or_create_offline_node(host_id, records)
        if not node:
            continue
        payload = {
            'node_key': node.node_key,
            'log_type': 'result',
            'data': records,
        }

        db.session.add(node)
        db.session.bulk_save_objects(process_result(payload, node))
        db.session.commit()

        try:
            analyze_result.delay(payload, node.to_dict())
            normalize_to_cmdb.delay(payload, node.id)
            learn_from_result.delay(payload, node.to_dict())
        except Exception as exc:
            current_app.logger.error("Failed to run celery tasks for offline import: %s", exc)
            normalize_to_cmdb(payload, node.id)

        nodes_updated += 1

    return nodes_updated

