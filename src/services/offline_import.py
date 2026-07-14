# -*- coding: utf-8 -*-
import json
import datetime as dt

from flask import current_app

from database import db
from models import Node


def decode_upload_body(file_data):
    body = file_data.read()
    if isinstance(body, bytes):
        body = body.decode('utf-8')
    return body


def validate_offline_record(record):
    if not isinstance(record, dict):
        return False
        
    host_id = record.get('hostIdentifier') or record.get('host_identifier')
    if not host_id:
        return False
        
    name = record.get('name')
    if not name:
        return False
        
    calendar_time = record.get('calendarTime')
    if not calendar_time:
        return False
        
    timefmt = '%a %b %d %H:%M:%S %Y UTC'
    try:
        dt.datetime.strptime(calendar_time, timefmt)
    except (ValueError, TypeError):
        return False
        
    if 'columns' in record:
        if 'action' not in record:
            return False
    elif 'diffResults' in record:
        diff = record['diffResults']
        if not isinstance(diff, dict) or 'added' not in diff or 'removed' not in diff:
            return False
    elif 'snapshot' in record:
        if not isinstance(record['snapshot'], list):
            return False
    else:
        return False
        
    return True


def parse_offline_records(body):
    raw_records = []
    try:
        parsed = json.loads(body)
        if isinstance(parsed, list):
            raw_records = parsed
        elif isinstance(parsed, dict):
            raw_records = [parsed]
    except ValueError:
        pass

    valid_records = []
    invalid_count = 0

    if not raw_records:
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw_records.append(json.loads(line))
            except ValueError:
                invalid_count += 1
                continue
    for r in raw_records:
        if validate_offline_record(r):
            valid_records.append(r)
        else:
            invalid_count += 1
            
    return valid_records, invalid_count


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
    nodes_skipped = 0
    for host_id, records in grouped.items():
        node = get_or_create_offline_node(host_id, records)
        if not node:
            nodes_skipped += 1
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

    return nodes_updated, nodes_skipped

