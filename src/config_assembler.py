# -*- coding: utf-8 -*-
import datetime as dt
from flask import current_app
from database import db
from models import (
    DistributedQuery, DistributedQueryTask,
    Pack, Query, querypacks
)


def assemble_configuration(node):
    configuration = {}
    configuration['options'] = assemble_options(node)
    configuration['file_paths'] = assemble_file_paths(node)
    configuration['schedule'] = assemble_schedule(node)
    configuration['packs'] = assemble_packs(node)
    return configuration


def assemble_options(node):
    options = {}

    # https://github.com/facebook/osquery/issues/2048#issuecomment-219200524
    if current_app.config['DOORMAN_EXPECTS_UNIQUE_HOST_ID']:
        options['host_identifier'] = 'uuid'
    else:
        options['host_identifier'] = 'hostname'

    options['schedule_splay_percent'] = 10
    return options


def assemble_file_paths(node):
    file_paths = {}
    for file_path in node.file_paths.options(db.lazyload('*')):
        file_paths.update(file_path.to_dict())
    return file_paths


def assemble_schedule(node):
    schedule = {}
    for query in node.queries.options(db.lazyload('*')):
        schedule[query.name] = query.to_dict()
    return schedule


def assemble_packs(node):
    packs = {}
    for pack in node.packs.join(querypacks).join(Query) \
        .options(db.contains_eager(Pack.queries)).all():
        packs[pack.name] = pack.to_dict()
    return packs


def assemble_distributed_queries(node):
    '''
    Retrieve all distributed queries assigned to a particular node
    in the NEW state. This function will change the state of the
    distributed query to PENDING, however will not commit the change.
    It is the responsibility of the caller to commit or rollback on the
    current database session.
    '''
    now = dt.datetime.utcnow()
    query = db.session.query(DistributedQueryTask) \
        .join(DistributedQuery) \
        .filter(
            DistributedQueryTask.node == node,
            DistributedQueryTask.status == DistributedQueryTask.NEW,
            DistributedQuery.not_before < now,
        ).options(
            db.lazyload('*'),
            db.contains_eager(DistributedQueryTask.distributed_query)
        )

    queries = {}
    for task in query:
        queries[task.guid] = task.distributed_query.sql
        task.update(status=DistributedQueryTask.PENDING,
                    timestamp=now,
                    started_at=now,
                    commit=False)

        # add this query to the session, but don't commit until we're
        # as sure as we possibly can be that it's been received by the
        # osqueryd client. unfortunately, there are no guarantees though.
        db.session.add(task)
    return queries
