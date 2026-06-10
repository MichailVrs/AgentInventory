# -*- coding: utf-8 -*-
from celery import Celery
from flask import current_app
import datetime as dt


celery = Celery(__name__)


@celery.task(ignore_result=True, name='tasks.analyze_result')
def analyze_result(result, node):
    current_app.rule_manager.handle_log_entry(result, node)
    return


@celery.task(ignore_result=True, name='tasks.normalize_to_cmdb')
def normalize_to_cmdb(result, node_id):
    """
    Нормализует результаты Osquery в EAV-модель CMDB.
    """
    from services.cmdb_normalization import normalize_to_cmdb_service
    return normalize_to_cmdb_service(result, node_id)



@celery.task()
def learn_from_result(result, node):
    from utils import learn_from_result as learn_from_result_impl
    learn_from_result_impl(result, node)
    return


@celery.task()
def example_task(one, two):
    from celery.utils.log import get_task_logger
    logger = get_task_logger(__name__)
    logger.info('Adding {0} and {1}'.format(one, two))
    return one + two



@celery.task()
def notify_of_node_enrollment(node):
    '''
    Create a result that gets run through our Rule Manager whenever a new
    node is enrolled so that we may alert on this action.

    A rule can be created within inventory's rule manager to alert on
    any of the following conditions:
        - query name: inventory/tasks/node_enrolled
        - action: triggered
        - columns:
            - enrolled_on
            - last_ip
            - node_id
    '''
    entry = {
        'name': 'inventory/tasks/node_enrolled',
        'calendarTime': dt.datetime.utcnow().strftime('%a %b %d %H:%M:%S %Y UTC'),
        'action': 'triggered',
    }
    columns = entry['columns'] = {}
    columns['enrolled_on'] = node.get('enrolled_on')
    columns['last_ip'] = node.get('last_ip')
    columns['node_id'] = node.get('id')
    result = {'data': [entry]}
    current_app.rule_manager.handle_log_entry(result, node)
    return


@celery.task()
def alert_when_node_goes_offline():
    '''
    This task is intended to periodically comb the database to identify
    nodes that have not posted results in some time, checked in for some
    time, or have not posted results within some time of their last
    checkin. The purpose of this task is to identify nodes that go offline,
    or in some cases, nodes with corrupted osquery rocksdb databases.

    A rule can be created within inventory's rules manager to alert on
    any of the following conditions:
        - query name: inventory/tasks/node_offline_checks
        - action: triggered
        - columns:
            - since_last_result
            - since_last_result_days
            - since_last_result_seconds
            - since_last_checkin
            - since_last_checkin_days
            - since_last_checkin_seconds
            - since_last_checkin_to_last_result
            - since_last_checkin_to_last_result_days
            - since_last_checkin_to_last_result_seconds
    '''
    from collections import namedtuple
    from sqlalchemy import func
    from models import db, Node, ResultLog

    _Node = namedtuple('Node', [
        'id', 'host_identifier', 'node_info', 'enrolled_on', 'is_active',
        'last_ip', 'last_checkin', 'last_result',
    ])

    query = db.session.query(
        ResultLog.node_id,
        Node.host_identifier,
        Node.node_info,
        Node.enrolled_on,
        Node.is_active,
        Node.last_ip,
        Node.last_checkin,
        func.max(ResultLog.timestamp),
    ).join(Node).filter(Node.is_active).group_by(ResultLog.node_id, Node.id)

    now = dt.datetime.utcnow()
    calendarTime = now.strftime('%a %b %d %H:%M:%S %Y UTC')

    for processed, node in enumerate(map(_Node._make, query), 1):
        entry = {
            'name': 'inventory/tasks/node_offline_checks',
            'calendarTime': calendarTime,
            'action': 'triggered',
        }
        columns = entry['columns'] = {}

        since_last_result = now - node.last_result
        since_last_checkin = now - node.last_checkin
        since_last_checkin_to_last_result = node.last_checkin - node.last_result

        columns['since_last_result_seconds'] = since_last_result.total_seconds()
        columns['since_last_checkin_seconds'] = since_last_checkin.total_seconds()
        columns['since_last_checkin_to_last_result_seconds'] = since_last_checkin_to_last_result.total_seconds()

        columns['since_last_result_days'] = since_last_result.days
        columns['since_last_checkin_days'] = since_last_checkin.days
        columns['since_last_checkin_to_last_result_days'] = since_last_checkin_to_last_result.days

        columns['since_last_result'] = since_last_result
        columns['since_last_checkin'] = since_last_checkin
        columns['since_last_checkin_to_last_result'] = since_last_checkin_to_last_result

        _node = dict(node._asdict())
        _node['display_name'] = node.node_info.get('display_name') or \
            node.node_info.get('hostname') or \
            node.node_info.get('computer_name') or \
            node.host_identifier

        result = {'data': [entry]}
        current_app.rule_manager.handle_log_entry(result, _node)

    else:
        return processed
