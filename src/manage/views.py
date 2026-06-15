# -*- coding: utf-8 -*-
from io import BytesIO
from operator import itemgetter
import datetime as dt
import unicodecsv as csv

from flask import (
    Blueprint, current_app, flash, jsonify, redirect, render_template,
    request, send_file, url_for, Response
)
from flask_login import login_required
from flask_paginate import Pagination

from sqlalchemy import or_

from .forms import (
    AddDistributedQueryForm,
    CreateQueryForm,
    UpdateQueryForm,
    UploadQueryForm,
    CreateTagForm,
    UploadPackForm,
    CreatePackForm,
    FilePathForm,
    FilePathUpdateForm,
    CreateRuleForm,
    UpdateRuleForm,
    UpdateNodeForm,
    UploadOfflineLogsForm,
)
from database import db
from models import (
    DistributedQuery, DistributedQueryTask, DistributedQueryResult,
    FilePath, Node, Pack, Query, Tag, Rule, ResultLog, StatusLog,
)
from utils import (
    create_query_pack_from_upload, flash_errors, get_paginate_options,
    validate_osquery_query
)
from services.cmdb_reports import (
    build_cmdb_export_csv,
    build_cmdb_report_context,
    quote_cmdb_export_filename,
    generate_custom_report,
    build_custom_export_csv,
)
from services.offline_import import (
    decode_upload_body,
    group_records_by_host,
    import_grouped_records,
    parse_offline_records,
)
from services.query_uploads import UploadQueryError, parse_uploaded_query


blueprint = Blueprint('manage', __name__,
                      template_folder='../templates/manage',
                      url_prefix='/manage')


@blueprint.context_processor
def inject_models():
    return dict(Node=Node, Pack=Pack, Query=Query, Tag=Tag,
                Rule=Rule, FilePath=FilePath,
                DistributedQuery=DistributedQuery,
                DistributedQueryTask=DistributedQueryTask,
                current_app=current_app,
                db=db)


@blueprint.route('/')
@login_required
def index():
    import datetime
    checkin_interval = current_app.config['INVENTORY_CHECKIN_INTERVAL']
    if isinstance(checkin_interval, (int, float)):
        checkin_interval = datetime.timedelta(seconds=checkin_interval)
    cutoff = datetime.datetime.utcnow() - checkin_interval
    total_nodes = Node.query.count()
    inactive_nodes = Node.query.filter_by(is_active=False).count()
    offline_nodes = Node.query.filter(Node.is_active == True, (Node.last_checkin == None) | (Node.last_checkin < cutoff)).count()
    active_nodes = Node.query.filter(Node.is_active == True, Node.last_checkin != None, Node.last_checkin >= cutoff).count()
    
    recent_nodes = Node.query.order_by(Node.last_checkin.desc().nullsfirst()).limit(5).all()

    return render_template('index.html',
                           total_nodes=total_nodes,
                           inactive_nodes=inactive_nodes,
                           offline_nodes=offline_nodes,
                           active_nodes=active_nodes,
                           recent_nodes=recent_nodes,
                           cutoff=cutoff)


@blueprint.route('/nodes')
@blueprint.route('/nodes/<int:page>')
@blueprint.route('/nodes/<any(active, offline, inactive):status>')
@blueprint.route('/nodes/<any(active, offline, inactive):status>/<int:page>')
@login_required
def nodes(page=1, status='active'):
    import datetime
    checkin_interval = current_app.config['INVENTORY_CHECKIN_INTERVAL']
    if isinstance(checkin_interval, (int, float)):
        checkin_interval = datetime.timedelta(seconds=checkin_interval)
    cutoff = datetime.datetime.utcnow() - checkin_interval
    if status == 'inactive':
        nodes = Node.query.filter_by(is_active=False)
    elif status == 'offline':
        nodes = Node.query.filter(Node.is_active == True, (Node.last_checkin == None) | (Node.last_checkin < cutoff))
    else:
        nodes = Node.query.filter(Node.is_active == True, Node.last_checkin != None, Node.last_checkin >= cutoff)

    nodes = nodes.all()

    return render_template('nodes.html',
                           nodes=nodes,
                           status=status)


@blueprint.route('/nodes.csv')
@login_required
def nodes_csv():
    headers = [
        'Отображаемое имя',
        'Идентификатор хоста',
        'Дата регистрации',
        'Последний сеанс связи',
        'Последний IP-адрес',
        'Активен',
    ]

    column_names = map(itemgetter(0), current_app.config['INVENTORY_CAPTURE_NODE_INFO'])
    labels = map(itemgetter(1), current_app.config['INVENTORY_CAPTURE_NODE_INFO'])
    headers.extend(labels)
    headers = list(headers)

    bio = BytesIO()
    bio.write(b'\xef\xbb\xbf')  # Добавляем UTF-8 BOM для совместимости с Excel
    writer = csv.writer(bio)
    writer.writerow(headers)

    for node in Node.query:
        row = [
            node.display_name,
            node.host_identifier,
            node.enrolled_on,
            node.last_checkin,
            node.last_ip,
            node.is_active,
        ]
        row.extend([node.node_info.get(column, '') for column in column_names])
        writer.writerow(row)

    bio.seek(0)

    response = send_file(
        bio,
        mimetype='text/csv',
        as_attachment=True,
        download_name='nodes.csv'
    )

    return response


@blueprint.route('/nodes/add', methods=['GET', 'POST'])
@login_required
def add_node():
    return redirect(url_for('manage.nodes'))


@blueprint.route('/nodes/tagged/<string:tags>')
@login_required
def nodes_by_tag(tags):
    if tags == 'null':
        nodes = Node.query.filter(Node.tags == None).all()
    else:
        tag_names = [t.strip() for t in tags.split(',')]
        nodes = Node.query.filter(Node.tags.any(Tag.value.in_(tag_names))).all()
    return render_template('nodes.html', nodes=nodes)


@blueprint.route('/node/<int:node_id>', methods=['GET', 'POST'])
@login_required
def get_node(node_id):
    node = Node.query.filter_by(id=node_id).first_or_404()
    form = UpdateNodeForm(request.form)

    if form.validate_on_submit():
        node_info = node.node_info.copy()

        if form.display_name.data:
            node_info['display_name'] = form.display_name.data
        elif 'display_name' in node_info:
            node_info.pop('display_name')

        node.node_info = node_info
        node.is_active = form.is_active.data
        node.save()

        if (request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
            return '', 204

        return redirect(url_for('manage.get_node', node_id=node.id))

    form = UpdateNodeForm(request.form, obj=node)
    flash_errors(form)

    packs = node.packs \
        .options(
            db.joinedload(Pack.tags, innerjoin=True),
            db.joinedload(Pack.queries, innerjoin=True),
        ).order_by(Pack.name)

    queries = node.queries \
        .options(
            db.joinedload(Query.tags, innerjoin=True),
            db.joinedload(Query.packs)
        ).order_by(Query.name)

    return render_template('node.html', form=form, node=node,
                           packs=packs, queries=queries)


@blueprint.route('/node/<int:node_id>/activity')
@login_required
def node_activity(node_id):
    node = Node.query.filter_by(id=node_id) \
        .options(db.lazyload('*')).first()

    try:
        timestamp = request.args.get('timestamp')
        timestamp = dt.datetime.fromtimestamp(float(timestamp))
    except Exception:
        timestamp = dt.datetime.utcnow()
        timestamp -= dt.timedelta(days=7)

    recent = node.result_logs.filter(ResultLog.timestamp > timestamp).all()
    queries = db.session.query(DistributedQueryTask) \
        .join(DistributedQuery) \
        .join(DistributedQueryResult) \
        .join(Node) \
        .options(
            db.lazyload('*'),
            db.contains_eager(DistributedQueryTask.results),
            db.contains_eager(DistributedQueryTask.distributed_query),
            db.contains_eager(DistributedQueryTask.node)
        ) \
        .filter(
            DistributedQueryTask.node == node,
            or_(
                DistributedQuery.timestamp >= timestamp,
                DistributedQueryTask.timestamp >= timestamp,
            )
        ).all()
    return render_template('activity.html', node=node, recent=recent, queries=queries)


@blueprint.route('/node/<int:node_id>/logs')
@blueprint.route('/node/<int:node_id>/logs/<int:page>')
@login_required
def node_logs(node_id, page=1):
    node = Node.query.filter(Node.id == node_id).first_or_404()
    status_logs = StatusLog.query.filter_by(node=node)

    status_logs = get_paginate_options(
        request,
        StatusLog,
        ('line', 'message', 'severity', 'filename'),
        existing_query=status_logs,
        page=page,
        max_pp=500,
        default_sort='desc'
    )

    pagination = Pagination(page=page,
                            per_page=status_logs.per_page,
                            total=status_logs.total,
                            alignment='center',
                            show_single_page=False,
                            record_name='записей журнала состояния',
                            bs_version=3)

    return render_template('logs.html', node=node,
                           status_logs=status_logs.items,
                           pagination=pagination)


@blueprint.route('/node/<int:node_id>/tags', methods=['GET', 'POST'])
@login_required
def tag_node(node_id):
    node = Node.query.filter(Node.id == node_id).first_or_404()
    if (request.headers.get('X-Requested-With') == 'XMLHttpRequest') and request.method == 'POST':
        node.tags = create_tags(*request.get_json())
        node.save()
        return jsonify({}), 202

    return redirect(url_for('manage.get_node', node_id=node.id))


@blueprint.route('/node/<int:node_id>/distributed/result/<string:guid>')
@login_required
def get_distributed_result(node_id, guid):
    node = Node.query.filter(Node.id == node_id).first_or_404()
    query = DistributedQueryTask.query.filter(
        DistributedQueryTask.guid == guid,
        DistributedQueryTask.node == node,
    ).first_or_404()
    return render_template('distributed.result.html', node=node, query=query)


@blueprint.route('/packs')
@login_required
def packs():
    packs = Pack.query \
        .options(
            db.joinedload(Pack.tags),
            db.joinedload(Pack.queries),
            db.joinedload(Pack.queries, Query.packs, innerjoin=True)
        ).all()
    return render_template('packs.html', packs=packs)


@blueprint.route('/packs/add', methods=['GET', 'POST'])
@blueprint.route('/packs/upload', methods=['POST'])
@login_required
def add_pack():
    form = UploadPackForm()
    if form.validate_on_submit():
        pack = create_query_pack_from_upload(form.pack)

        # Only redirect back to the pack list if everything was successful
        if pack is not None:
            return redirect(url_for('manage.packs', _anchor=pack.name))

    flash_errors(form)
    return render_template('pack.html', form=form)


@blueprint.route('/packs/create', methods=['GET', 'POST'])
@login_required
def create_pack():
    form = CreatePackForm()
    if form.validate_on_submit():
        pack = Pack(
            name=form.name.data,
            platform=form.platform.data if form.platform.data else None,
            version=form.version.data if form.version.data else None,
            description=form.description.data if form.description.data else None,
            shard=form.shard.data if form.shard.data else None
        )
        pack.tags = create_tags(*form.tags.data.splitlines())
        pack.save()
        flash(u'Пакет {0} успешно создан.'.format(pack.name), 'success')
        return redirect(url_for('manage.packs', _anchor=pack.name))

    flash_errors(form)
    return render_template('create_pack.html', form=form)


@blueprint.route('/pack/<string:pack_name>/delete', methods=['POST'])
@login_required
def delete_pack(pack_name):
    pack = Pack.query.filter(Pack.name == pack_name).first_or_404()
    pack.queries = []
    pack.tags = []
    pack.delete()
    flash(u'Пакет {0} успешно удален.'.format(pack_name), 'success')
    return redirect(url_for('manage.packs'))


@blueprint.route('/pack/<string:pack_name>/tags', methods=['GET', 'POST'])
@login_required
def tag_pack(pack_name):
    pack = Pack.query.filter(Pack.name == pack_name).first_or_404()
    if (request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
        if request.method == 'POST':
            pack.tags = create_tags(*request.get_json())
            pack.save()
        return jsonify(tags=[t.value for t in pack.tags])

    return redirect(url_for('manage.packs'))


@blueprint.route('/queries')
@login_required
def queries():
    queries = Query.query \
        .options(
            db.joinedload(Query.tags),
            db.joinedload(Query.packs),
            db.joinedload(Query.packs, Pack.queries, innerjoin=True)
        ).all()
    return render_template('queries.html', queries=queries)


@blueprint.route('/queries/add', methods=['GET', 'POST'])
@login_required
def add_query():
    form = CreateQueryForm()
    form.set_choices()

    if form.validate_on_submit():
        query = Query(name=form.name.data,
                      sql=form.sql.data,
                      interval=form.interval.data,
                      platform=form.platform.data,
                      version=form.version.data,
                      description=form.description.data,
                      value=form.value.data,
                      removed=form.removed.data,
                      shard=form.shard.data)
        query.tags = create_tags(*form.tags.data.splitlines())
        if form.packs.data:
            from models import Pack
            query.packs = Pack.query.filter(Pack.name == form.packs.data).all()
        else:
            query.packs = []
        query.save()

        flash(u'Запрос {0} успешно создан.'.format(query.name), 'success')
        return redirect(url_for('manage.queries'))

    flash_errors(form)
    return render_template('query.html', form=form)




@blueprint.route('/queries/upload', methods=['GET', 'POST'])
@login_required
def upload_query():
    form = UploadQueryForm()
    form.set_choices()

    if form.validate_on_submit():
        try:
            uploaded_query = parse_uploaded_query(form.query_file.data)
        except UploadQueryError as error:
            if error.code == 'invalid_json_structure':
                flash(u"Некорректная структура JSON-файла запроса", 'danger')
            elif error.code == 'json_decode_error':
                flash(u"Ошибка декодирования JSON-файла", 'danger')
            elif error.code == 'unsupported_format':
                flash(u"Неподдерживаемый формат файла. Пожалуйста, загрузите .sql или .json файл.", 'danger')
            else:
                flash(u"Не удалось извлечь SQL-запрос из файла", 'danger')
            return render_template('manage/upload_query.html', form=form)

        if not validate_osquery_query(uploaded_query.sql):
            flash('Некорректный SQL-запрос в файле: "{0}"'.format(uploaded_query.sql), 'danger')
            return render_template('manage/upload_query.html', form=form)

        existing_query = Query.query.filter(Query.name == uploaded_query.name).first()
        if existing_query:
            flash(u"Запрос с названием {0} уже существует.".format(uploaded_query.name), 'danger')
            return render_template('manage/upload_query.html', form=form)

        query = Query(name=uploaded_query.name,
                      sql=uploaded_query.sql,
                      interval=uploaded_query.interval,
                      platform=uploaded_query.platform,
                      version=uploaded_query.version,
                      description=uploaded_query.description,
                      value=uploaded_query.value,
                      removed=uploaded_query.removed,
                      shard=uploaded_query.shard)

        query.tags = create_tags(*form.tags.data.splitlines())
        if form.packs.data:
            from models import Pack
            query.packs = Pack.query.filter(Pack.name == form.packs.data).all()
        else:
            query.packs = []
        query.save()

        flash(u"Запрос {0} успешно импортирован!".format(query.name), 'success')
        return redirect(url_for('manage.queries'))

    flash_errors(form)
    return render_template('manage/upload_query.html', form=form)


@blueprint.route('/queries/distributed')
@blueprint.route('/queries/distributed/<int:page>')
@blueprint.route('/queries/distributed/<any(new, pending, complete, failed):status>')
@blueprint.route('/queries/distributed/<any(new, pending, complete, failed):status>/<int:page>')
@blueprint.route('/node/<int:node_id>/distributed/<any(new, pending, complete, failed):status>')
@blueprint.route('/node/<int:node_id>/distributed/<any(new, pending, complete, failed):status>/<int:page>')
@login_required
def distributed(node_id=None, status=None, page=1):
    tasks = DistributedQueryTask.query

    if status == 'new':
        tasks = tasks.filter_by(status=DistributedQueryTask.NEW)
    elif status == 'pending':
        tasks = tasks.filter_by(status=DistributedQueryTask.PENDING)
    elif status == 'complete':
        tasks = tasks.filter_by(status=DistributedQueryTask.COMPLETE)
    elif status == 'failed':
        tasks = tasks.filter_by(status=DistributedQueryTask.FAILED)

    if node_id:
        node = Node.query.filter_by(id=node_id).first_or_404()
        tasks = tasks.filter_by(node_id=node.id)

    tasks = get_paginate_options(
        request,
        DistributedQueryTask,
        ('id', 'status', 'timestamp'),
        existing_query=tasks,
        page=page,
        default_sort='desc'
    )
    display_msg = 'показано <b>{start} - {end}</b> из <b>{total}</b> {record_name}'

    pagination = Pagination(page=page,
                            per_page=tasks.per_page,
                            total=tasks.total,
                            alignment='center',
                            show_single_page=False,
                            display_msg=display_msg,
                            record_name='{0} задач оперативных запросов'.format(status or '').strip(),
                            bs_version=3)

    return render_template('distributed.html', queries=tasks.items,
                           status=status, pagination=pagination)


@blueprint.route('/queries/distributed/results/<int:distributed_id>')
@blueprint.route('/queries/distributed/results/<int:distributed_id>/<int:page>')
@blueprint.route('/queries/distributed/results/<int:distributed_id>/<any(new, pending, complete, failed):status>')
@blueprint.route('/queries/distributed/results/<int:distributed_id>/<any(new, pending, complete, failed):status>/<int:page>')
@login_required
def distributed_results(distributed_id, status=None, page=1):
    query = DistributedQuery.query.filter_by(id=distributed_id).first_or_404()
    tasks = DistributedQueryTask.query.filter_by(distributed_query_id=query.id)

    if status == 'new':
        tasks = tasks.filter_by(status=DistributedQueryTask.NEW)
    elif status == 'pending':
        tasks = tasks.filter_by(status=DistributedQueryTask.PENDING)
    elif status == 'complete':
        tasks = tasks.filter_by(status=DistributedQueryTask.COMPLETE)
    elif status == 'failed':
        tasks = tasks.filter_by(status=DistributedQueryTask.FAILED)

    tasks = get_paginate_options(
        request,
        DistributedQueryTask,
        ('id', 'status', 'timestamp'),
        existing_query=tasks,
        page=page,
        default_sort='desc'
    )
    display_msg = 'показано <b>{start} - {end}</b> из <b>{total}</b> {record_name}'

    pagination = Pagination(page=page,
                            per_page=tasks.per_page,
                            total=tasks.total,
                            alignment='center',
                            show_single_page=False,
                            display_msg=display_msg,
                            record_name='{0} результатов оперативных запросов'.format(status or '').strip(),
                            bs_version=3)

    # We could do this in the template, but it's more clear here.
    columns = []
    for task in tasks.items:
        if len(task.results) > 0 and len(task.results[0].columns) > 0:
            columns = sorted(task.results[0].columns.keys())

    return render_template('distributed_results.html',
                           tasks=tasks.items,
                           columns=columns,
                           query=query,
                           status=status,
                           pagination=pagination,
                           distributed_id=distributed_id)


@blueprint.route('/queries/distributed/add', methods=['GET', 'POST'])
@login_required
def add_distributed():
    form = AddDistributedQueryForm()
    form.set_choices()

    if form.validate_on_submit():
        nodes = []

        if not form.nodes.data and not form.tags.data:
            # all nodes get this query
            nodes = Node.query.all()

        if form.nodes.data:
            nodes.extend(
                Node.query.filter(
                    Node.node_key.in_(form.nodes.data)
                ).all()
            )

        if form.tags.data:
            nodes.extend(
                Node.query.filter(
                    Node.tags.any(
                        Tag.value.in_(form.tags.data)
                    )
                ).all()
            )

        query = DistributedQuery.create(sql=form.sql.data,
                                        description=form.description.data,
                                        not_before=form.not_before.data)

        for node in nodes:
            task = DistributedQueryTask(node=node, distributed_query=query)
            db.session.add(task)
        else:
            db.session.commit()

        flash(u'Оперативный запрос успешно добавлен.', 'success')
        return redirect(url_for('manage.distributed'))

    flash_errors(form)
    return render_template('distributed.html', form=form)


@blueprint.route('/queries/tagged/<string:tags>')
@login_required
def queries_by_tag(tags):
    tag_names = [t.strip() for t in tags.split(',')]
    queries = Query.query.filter(Query.tags.any(Tag.value.in_(tag_names))).all()
    return render_template('queries.html', queries=queries)


@blueprint.route('/query/<int:query_id>', methods=['GET', 'POST'])
@login_required
def query(query_id):
    query = Query.query.filter(Query.id == query_id).first_or_404()

    if request.method == 'POST':
        form = UpdateQueryForm(request.form)
        if form.validate_on_submit():
            if form.packs.data:
                query.packs = Pack.query.filter(Pack.name == form.packs.data).all()
            else:
                query.packs = []

            query.tags = create_tags(*form.tags.data.splitlines())
            query.update(name=form.name.data,
                         sql=form.sql.data,
                         interval=form.interval.data,
                         platform=form.platform.data,
                         version=form.version.data,
                         description=form.description.data,
                         value=form.value.data,
                         removed=form.removed.data,
                         shard=form.shard.data)
            return redirect(url_for('manage.queries'))
    else:
        form = UpdateQueryForm(obj=query)

    flash_errors(form)
    return render_template('query.html', form=form, query=query)


@blueprint.route('/query/<int:query_id>', methods=['DELETE'])
@login_required
def delete_query(query_id):
    query = Query.query.filter(Query.id == query_id).first_or_404()
    query.delete()
    return jsonify({}), 204



@blueprint.route('/query/<int:query_id>/tags', methods=['GET', 'POST'])
@login_required
def tag_query(query_id):
    query = Query.query.filter(Query.id == query_id).first_or_404()
    if (request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
        if request.method == 'POST':
            query.tags = create_tags(*request.get_json())
            query.save()
        return jsonify(tags=[t.value for t in query.tags])

    return redirect(url_for('manage.query', query_id=query.id))


@blueprint.route('/files')
@login_required
def files():
    file_paths = FilePath.query.all()
    return render_template('files.html', file_paths=file_paths)


@blueprint.route('/files/add', methods=['GET', 'POST'])
@login_required
def add_file():
    form = FilePathForm()

    if form.validate_on_submit():
        file_path = FilePath(
            category=form.category.data,
            target_paths=form.target_paths.data.splitlines()
        )
        file_path.tags = create_tags(*form.tags.data.splitlines())
        file_path.save()

        return redirect(url_for('manage.files'))

    flash_errors(form)
    return render_template('file.html', form=form)


@blueprint.route('/file/<int:file_path_id>', methods=['GET', 'POST'])
@login_required
def file_path(file_path_id):
    file_path = FilePath.query.filter(FilePath.id == file_path_id).first_or_404()

    if request.method == 'POST':
        form = FilePathUpdateForm(request.form)
        if form.validate_on_submit():
            file_path.tags = create_tags(*form.tags.data.splitlines())
            file_path.set_paths(*form.target_paths.data.splitlines())
            file_path.update(
                category=form.category.data,
            )
            return redirect(url_for('manage.files'))
    else:
        form = FilePathUpdateForm(obj=file_path)

    flash_errors(form)
    return render_template('file.html', form=form, file_path=file_path)


@blueprint.route('/file/<int:file_path_id>/tags', methods=['GET', 'POST'])
@login_required
def tag_file(file_path_id):
    file_path = FilePath.query.filter(FilePath.id == file_path_id).first_or_404()
    if (request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
        if request.method == 'POST':
            file_path.tags = create_tags(*request.get_json())
            file_path.save()
        return jsonify(tags=[t.value for t in file_path.tags])

    return redirect(url_for('manage.files'))


@blueprint.route('/file/<int:file_path_id>/delete', methods=['POST'])
@login_required
def delete_file_path(file_path_id):
    file_path = FilePath.query.filter(FilePath.id == file_path_id).first_or_404()
    file_path.tags = []
    file_path.delete()
    flash(u'Путь мониторинга {0} успешно удален.'.format(file_path.category), 'success')
    return redirect(url_for('manage.files'))


@blueprint.route('/tags')
@login_required
def tags():
    tags = dict((t.value, {}) for t in Tag.query.all())

    if (request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
        return jsonify(tags=tags.keys())

    baseq = db.session.query(Tag.value, db.func.count(Tag.id))

    for tag, count in baseq.join(Tag.nodes).group_by(Tag.id).all():
        tags[tag]['nodes'] = count
    for tag, count in baseq.join(Tag.packs).group_by(Tag.id).all():
        tags[tag]['packs'] = count
    for tag, count in baseq.join(Tag.queries).group_by(Tag.id).all():
        tags[tag]['queries'] = count
    for tag, count in baseq.join(Tag.file_paths).group_by(Tag.id).all():
        tags[tag]['file_paths'] = count

    return render_template('tags.html', tags=tags)


@blueprint.route('/tags/add', methods=['GET', 'POST'])
@login_required
def add_tag():
    form = CreateTagForm()
    if form.validate_on_submit():
        create_tags(*form.value.data.splitlines())
        return redirect(url_for('manage.tags'))

    flash_errors(form)
    return render_template('tag.html', form=form)


@blueprint.route('/tag/<string:tag_value>')
@login_required
def get_tag(tag_value):
    tag = Tag.query.filter(Tag.value == tag_value).first_or_404()
    return render_template('tag.html', tag=tag)


@blueprint.route('/tag/<string:tag_value>', methods=['DELETE'])
@login_required
def delete_tag(tag_value):
    tag = Tag.query.filter(Tag.value == tag_value).first_or_404()
    tag.delete()
    return jsonify({}), 204


@blueprint.route('/distributed_task/<int:task_id>', methods=['DELETE'])
@login_required
def delete_distributed_task(task_id):
    from models import DistributedQueryTask
    task = DistributedQueryTask.query.filter(DistributedQueryTask.id == task_id).first_or_404()
    task.delete()
    return jsonify({}), 204


def create_tags(*tags):
    values = []
    existing = []

    # create a set, because we haven't yet done our association_proxy in
    # sqlalchemy

    for value in (v.strip() for v in set(tags) if v.strip()):
        tag = Tag.query.filter(Tag.value == value).first()
        if not tag:
            values.append(Tag.create(value=value))
        else:
            existing.append(tag)
    else:
        if values:
            flash(u"Created tag{0} {1}".format(
                  's' if len(values) > 1 else '',
                  ', '.join(tag.value for tag in values)),
                  'info')
    return values + existing


@blueprint.route('/rules')
@login_required
def rules():
    rules = Rule.query.all()
    return render_template('rules.html', rules=rules)


@blueprint.route('/rules/add', methods=['GET', 'POST'])
@login_required
def add_rule():
    form = CreateRuleForm()
    form.set_choices()

    if form.validate_on_submit():
        rule = Rule(name=form.name.data,
                    alerters=form.alerters.data,
                    description=form.description.data,
                    conditions=form.conditions.data,
                    updated_at=dt.datetime.utcnow())
        rule.save()

        return redirect(url_for('manage.rule', rule_id=rule.id))

    flash_errors(form)
    return render_template('rule.html', form=form)


@blueprint.route('/rules/<int:rule_id>', methods=['GET', 'POST'])
@login_required
def rule(rule_id):
    rule = Rule.query.filter(Rule.id == rule_id).first_or_404()
    form = UpdateRuleForm(request.form)

    if form.validate_on_submit():
        rule = rule.update(name=form.name.data,
                           alerters=form.alerters.data,
                           description=form.description.data,
                           conditions=form.conditions.data,
                           updated_at=dt.datetime.utcnow())
        return redirect(url_for('manage.rule', rule_id=rule.id))

    form = UpdateRuleForm(request.form, obj=rule)
    flash_errors(form)
    return render_template('rule.html', form=form, rule=rule)


@blueprint.route('/search', methods=['GET', 'POST'])
@blueprint.route('/search/<int:page>', methods=['GET', 'POST'])
@login_required
def search(page=1, max_pp=500):
    try:
        per_page = int(request.args.pop('pp', max_pp))
    except Exception:
        per_page = 20

    per_page = max(0, min(500, per_page))

    results = ResultLog.query

    tbl_columns = ResultLog.__table__.columns.keys()

    if not request.args:
        return render_template('results.html', results=[])

    for key in request.args:
        if key in ('pp', 'order_by', 'sort'):
            continue

        values = request.args.getlist(key)
        ors = []

        for value in values:
            if key.startswith('columns.') or key not in tbl_columns:
                column = ResultLog.columns[key.replace('columns.', '')].astext
                ors.append(column == value)
            else:
                ors.append(getattr(ResultLog, key) == value)
        else:
            results = results.filter(or_(*ors))

    sort = request.args.get('sort', 'asc')
    if sort not in ('asc', 'desc'):
        sort = 'asc'

    for order_by in request.args.get('order_by', '').split(','):
        if order_by.startswith('columns.') or order_by not in tbl_columns:
            column = ResultLog.columns[order_by.replace('columns.', '')].astext
        else:
            column = getattr(ResultLog, order_by)
        order_by = getattr(column, sort)()
        results = results.order_by(order_by)

    results = results.paginate(page=page, per_page=per_page)

    pagination = Pagination(page=page,
                            per_page=results.per_page,
                            total=results.total,
                            alignment='center',
                            show_single_page=False,
                            search=True,
                            found=results.total,
                            bs_version=3)

    return render_template('results.html',
                           pagination=pagination,
                           results=results.items)


# ---------------------------------------------------------------------------
#  Dynamic CMDB Reports
# ---------------------------------------------------------------------------

@blueprint.route('/cmdb')
@blueprint.route('/cmdb/<string:object_type>')
@login_required
def cmdb_reports(object_type=None):
    context = build_cmdb_report_context(object_type)
    if not object_type and context['types']:
        return redirect(url_for('manage.cmdb_reports', object_type=context['types'][0]))

    return render_template('manage/cmdb_dynamic.html', **context)


@blueprint.route('/cmdb/<string:object_type>/export')
@login_required
def cmdb_export(object_type):
    quoted_filename = quote_cmdb_export_filename(object_type)
    return Response(
        build_cmdb_export_csv(object_type),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename*=UTF-8''{0}".format(quoted_filename)}
    )


@blueprint.route('/cmdb/custom/builder', methods=['GET', 'POST'])
@login_required
def custom_report_builder():
    from models import CmdbAttributeDict
    all_attributes = CmdbAttributeDict.query.order_by(CmdbAttributeDict.name).all()
    
    # Считываем выбранные атрибуты из параметров
    selected_ids = []
    if request.method == 'POST':
        selected_ids = request.form.getlist('attribute_ids', type=int)
    else:
        selected_ids = request.args.getlist('attribute_ids', type=int)

    report_context = None
    if selected_ids:
        report_context = generate_custom_report(selected_ids)
        
    return render_template(
        'manage/custom_report.html',
        attributes=all_attributes,
        selected_ids=selected_ids,
        report=report_context
    )


@blueprint.route('/cmdb/custom/export', methods=['POST'])
@login_required
def custom_report_export():
    from urllib.parse import quote
    selected_ids = request.form.getlist('attribute_ids', type=int)
    if not selected_ids:
        flash(u"Не выбраны атрибуты для экспорта", "danger")
        return redirect(url_for('manage.custom_report_builder'))
        
    csv_data = build_custom_export_csv(selected_ids)
    quoted_filename = quote("custom_report.csv")
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename*=UTF-8''{0}".format(quoted_filename)}
    )


@blueprint.route('/nodes/import', methods=['GET', 'POST'])
@login_required
def import_offline_logs():
    form = UploadOfflineLogsForm()
    if form.validate_on_submit():
        body = decode_upload_body(form.logs_file.data)
        records = parse_offline_records(body)
        if not records:
            flash(u"Не удалось извлечь корректные записи результатов в формате JSON.", "danger")
            return render_template('import_offline.html', form=form)

        grouped = group_records_by_host(records)
        if not grouped:
            flash(u"Не найдены идентификаторы хостов (hostIdentifier) в загруженных данных.", "danger")
            return render_template('import_offline.html', form=form)

        nodes_updated = import_grouped_records(grouped)
        flash(u"Успешно обработаны результаты для {0} хостов.".format(nodes_updated), "success")
        return redirect(url_for('manage.nodes'))
        
    flash_errors(form)
    return render_template('import_offline.html', form=form)
