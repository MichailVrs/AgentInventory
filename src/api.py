# -*- coding: utf-8 -*-
from functools import wraps
from io import BytesIO
import datetime as dt
import gzip
import json

from flask import Blueprint, current_app, jsonify, request

from database import db
from extensions import log_tee
from models import (
    Node,
    DistributedQueryTask, DistributedQueryResult,
    StatusLog,
)
from tasks import analyze_result, normalize_to_cmdb, learn_from_result
from utils import process_result


blueprint = Blueprint('api', __name__)


def node_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # in v1.7.4, the Content-Encoding header is set when
        # --logger_tls_compress=true
        if 'Content-Encoding' in request.headers and \
            request.headers['Content-Encoding'] == 'gzip':
            request._cached_data = gzip.GzipFile(
                fileobj=BytesIO(request.get_data())).read()

        request_json = request.get_json()

        if not request_json or 'node_key' not in request_json:
            current_app.logger.error(
                "%s - Request did not contain valid JSON data. This could "
                "be an attempt to gather information about this endpoint "
                "or an automated scanner.",
                request.remote_addr
            )
            # Return nothing
            return ""

        node_key = request_json.get('node_key')
        node = Node.query.filter_by(node_key=node_key) \
            .options(db.lazyload('*')).first()

        if not node:
            current_app.logger.error(
                "%s - Could not find node with node_key %s",
                request.remote_addr, node_key
            )
            return jsonify(node_invalid=True)

        if not node.is_active:
            current_app.logger.error(
                "%s - Node %s came back from the dead!",
                request.remote_addr, node_key
            )
            return jsonify(node_invalid=True)

        node.update(
            last_checkin=dt.datetime.utcnow(),
            last_ip=request.remote_addr,
            commit=False
        )

        response = f(node=node, *args, **kwargs)

        db.session.add(node)
        db.session.commit()

        return response
    return decorated_function


@blueprint.route('/')
def index():
    return '', 204


@blueprint.route('/enroll', methods=['POST', 'PUT'])
@blueprint.route('/v1/enroll', methods=['POST', 'PUT'])
def enroll():
    '''
    Enroll an endpoint with osquery.

    :returns: a `node_key` unique id. Additionally `node_invalid` will
        be true if the node failed to enroll.
    '''
    from services.enrollment import enroll_node
    res, status_code = enroll_node(request.get_json(silent=True), request.remote_addr)
    if not isinstance(res, dict):
        return res, status_code
    return jsonify(**res)



@blueprint.route('/config', methods=['POST', 'PUT'])
@blueprint.route('/v1/config', methods=['POST', 'PUT'])
@node_required
def configuration(node=None):
    '''
    Retrieve an osquery configuration for a given node.

    :returns: an osquery configuration file
    '''
    current_app.logger.info(
        "%s - %s checking in to retrieve a new configuration",
        request.remote_addr, node
    )
    config = node.get_config()

    # last_checkin, last_ip and session commit are handled by the decorator
    return jsonify(node_invalid=False, **config)


@blueprint.route('/log', methods=['POST', 'PUT'])
@blueprint.route('/v1/log', methods=['POST', 'PUT'])
@node_required
def logger(node=None):
    '''
    '''
    data = request.get_json()
    log_type = data['log_type']
    log_level = current_app.config['DOORMAN_MINIMUM_OSQUERY_LOG_LEVEL']

    if current_app.debug:
        current_app.logger.debug(json.dumps(data, indent=2))

    if log_type == 'status':
        log_tee.handle_status(data, host_identifier=node.host_identifier)
        status_logs = []
        for item in data.get('data', []):
            if int(item['severity']) < log_level:
                continue
            status_logs.append(StatusLog(node_id=node.id, **item))
        else:
            db.session.bulk_save_objects(status_logs)

    elif log_type == 'result':
        db.session.bulk_save_objects(process_result(data, node))
        log_tee.handle_result(data, host_identifier=node.host_identifier)
        
        try:
            analyze_result.delay(data, node.to_dict())
            normalize_to_cmdb.delay(data, node.id)
            learn_from_result.delay(data, node.to_dict())
            current_app.logger.debug("Tasks sent to Celery for node %s", node.id)
        except Exception as e:
            current_app.logger.error("Failed to send tasks to Celery: %s", str(e))

    else:
        current_app.logger.error("%s - Unknown log_type %r",
            request.remote_addr, log_type
        )
        current_app.logger.info(json.dumps(data))
        # last_checkin, last_ip and session commit are handled by the decorator
        pass

    return jsonify(node_invalid=False)


@blueprint.route('/distributed/read', methods=['POST', 'PUT'])
@blueprint.route('/v1/distributed/read', methods=['POST', 'PUT'])
@node_required
def distributed_read(node=None):
    '''
    '''
    data = request.get_json()

    current_app.logger.info(
        "%s - %s checking in to retrieve distributed queries",
        request.remote_addr, node
    )

    queries = node.get_new_queries()

    # last_checkin, last_ip, and query state updates are committed by the decorator
    pass

    return jsonify(queries=queries, node_invalid=False)


@blueprint.route('/distributed/write', methods=['POST', 'PUT'])
@blueprint.route('/v1/distributed/write', methods=['POST', 'PUT'])
@node_required
def distributed_write(node=None):
    '''
    '''
    data = request.get_json()

    if current_app.debug:
        current_app.logger.debug(json.dumps(data, indent=2))

    queries = data.get('queries', {})
    statuses = data.get('statuses', {})
    messages = data.get('messages', {})

    for guid, results in queries.items():
        task = DistributedQueryTask.query.filter(
            DistributedQueryTask.guid == guid,
            DistributedQueryTask.status == DistributedQueryTask.PENDING,
            DistributedQueryTask.node == node,
        ).first()

        if not task:
            current_app.logger.error(
                "%s - Got result for distributed query not in PENDING "
                "state: %s: %s",
                request.remote_addr, guid, json.dumps(data)
            )
            continue

        # non-zero status indicates sqlite errors
        now = dt.datetime.utcnow()
        error_message = None
        if not statuses.get(guid, 0):
            status = DistributedQueryTask.COMPLETE
        else:
            current_app.logger.error(
                "%s - Got non-zero status code (%d) on distributed query %s",
                request.remote_addr, statuses.get(guid), guid
            )
            status = DistributedQueryTask.FAILED
            error_message = messages.get(guid, "Unknown error")

        for columns in results:
            result = DistributedQueryResult(
                columns,
                distributed_query=task.distributed_query,
                distributed_query_task=task
            )
            db.session.add(result)
        else:
            task.status = status
            task.finished_at = now
            task.error_message = error_message
            db.session.add(task)

    else:
        # last_checkin, last_ip and session commit are handled by the decorator
        pass

    return jsonify(node_invalid=False)
