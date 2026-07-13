# Листинги программного кода для ВКР

Ниже приведены фрагменты, которые лучше всего показывают устройство системы: запуск приложения, работу с базой данных, прием данных от osquery-агентов, фоновую обработку, нормализацию в CMDB, офлайн-импорт и формирование отчетов.

## Листинг 1 - создание и настройка Flask-приложения

Источник: `migration_py3/src/application.py`

```python
def create_app(config=ProdConfig):
    app = Flask(__name__)
    app.config.from_object(config)
    app.config.from_envvar('INVENTORY_SETTINGS', silent=True)

    register_blueprints(app)
    register_errorhandlers(app)
    register_loggers(app)
    register_extensions(app)
    register_auth_method(app)
    register_filters(app)
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1
    )
    return app


def register_blueprints(app):
    app.register_blueprint(api)
    csrf.exempt(api)

    if 'INVENTORY_NO_MANAGER' in os.environ:
        return

    app.register_blueprint(backend)


def register_extensions(app):
    bcrypt.init_app(app)
    csrf.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    assets.init_app(app)
    log_tee.init_app(app)
    rule_manager.init_app(app)
    mail.init_app(app)
    make_celery(app, celery)
    login_manager.init_app(app)
    sentry.init_app(app)

    if app.config['ENFORCE_SSL']:
        from flask_sslify import SSLify
        SSLify(app)
```

Этот фрагмент показывает центральную точку сборки приложения. Здесь подключаются REST API для агентов, административный интерфейс, база данных, миграции, Celery, авторизация и другие инфраструктурные компоненты.

## Листинг 2 - базовый слой работы с БД

Источник: `migration_py3/src/database.py`

```python
Column = db.Column
Table = db.Table
ForeignKey = db.ForeignKey
UniqueConstraint = db.UniqueConstraint
Index = db.Index


class CRUDMixin(object):
    @classmethod
    def create(cls, **kwargs):
        instance = cls(**kwargs)
        return instance.save()

    def update(self, commit=True, **kwargs):
        for attr, value in kwargs.items():
            setattr(self, attr, value)
        return commit and self.save() or self

    def save(self, commit=True):
        db.session.add(self)
        if commit:
            db.session.commit()
        return self

    def delete(self, commit=True):
        db.session.delete(self)
        return commit and db.session.commit()


class Model(CRUDMixin, db.Model):
    __abstract__ = True


class SurrogatePK(object):
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)

    @classmethod
    def get_by_id(cls, record_id):
        if any((
            isinstance(record_id, basestring) and record_id.isdigit(),
            isinstance(record_id, (int, float)),
        )):
            return cls.query.get(int(record_id))
        return None


def reference_col(tablename, nullable=False, pk_name='id', **kwargs):
    return db.Column(
        ForeignKey('{0}.{1}'.format(tablename, pk_name)),
        nullable=nullable,
        **kwargs
    )
```

Фрагмент демонстрирует общий базовый класс моделей и универсальные операции создания, обновления, сохранения и удаления записей.

## Листинг 3 - инициализация расширений и Celery

Источник: `migration_py3/src/extensions.py`

```python
def make_celery(app, celery):
    from kombu.serialization import register
    from celery_serializer import djson_dumps, djson_loads

    register(
        'djson',
        djson_dumps,
        djson_loads,
        content_type='application/x-djson',
        content_encoding='utf-8'
    )

    celery.config_from_object(app.config)

    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery


bcrypt = Bcrypt()
csrf = CSRFProtect()
db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
debug_toolbar = DebugToolbarExtension()
log_tee = LogTee()
ldap_manager = LDAP3LoginManager()
login_manager = LoginManager()
rule_manager = RuleManager()
sentry = Sentry()
```

Здесь создаются общие объекты расширений Flask. Функция `make_celery` связывает фоновые задачи Celery с контекстом Flask-приложения, чтобы задачи могли использовать конфигурацию, базу данных и логирование.

## Листинг 4 - менеджер правил и обработка событий

Источник: `migration_py3/src/extensions.py`

```python
class RuleManager(object):
    def init_app(self, app):
        self.app = app
        self.load_alerters()
        app.rule_manager = self

    def load_rules(self):
        from rules import Network
        from models import Rule

        if not self.should_reload_rules():
            return

        all_rules = list(Rule.query.all())
        self.network = Network()
        self.rules_map = {r.id: r for r in all_rules}

        for rule in all_rules:
            for alerter in rule.alerters:
                if alerter not in self.alerters:
                    raise ValueError('No such alerter: "{0}"'.format(alerter))

            self.network.parse_query(
                rule.conditions,
                alerters=rule.alerters,
                rule_id=rule.id
            )

        if all_rules:
            self.last_update = max(r.updated_at for r in all_rules)

    def handle_log_entry(self, entry, node):
        from models import Rule
        from rules import RuleMatch
        from utils import extract_results

        self.load_rules()
        to_trigger = []

        for name, action, columns, timestamp in extract_results(entry):
            result = {
                'name': name,
                'action': action,
                'timestamp': timestamp,
                'columns': columns,
            }
            alerts = self.network.process(result, node)

            for alerter, rule_id in alerts:
                rule = self.rules_map.get(rule_id) or Rule.get_by_id(rule_id)
                to_trigger.append((alerter, RuleMatch(
                    rule=rule,
                    result=result,
                    node=node
                )))

        for alerter, match in to_trigger:
            self.alerters[alerter].handle_alert(node, match)
```

Данный фрагмент показывает механизм обработки событий: результаты инвентаризации сопоставляются с правилами, после чего система вызывает соответствующие обработчики уведомлений.

## Листинг 5 - модель инвентаризируемого узла

Источник: `migration_py3/src/models.py`

```python
class Node(SurrogatePK, Model):
    node_key = Column(db.String, nullable=False, unique=True)
    enroll_secret = Column(db.String)
    enrolled_on = Column(db.DateTime)
    host_identifier = Column(db.String)
    last_checkin = Column(db.DateTime)
    node_info = Column(JSONB, default={}, nullable=False)
    is_active = Column(db.Boolean, default=True, nullable=False)
    last_ip = Column(INET, nullable=True)

    tags = relationship(
        'Tag',
        secondary=node_tags,
        back_populates='nodes',
        lazy='joined',
    )

    def __init__(self, host_identifier, node_key=None,
                 enroll_secret=None, enrolled_on=None, last_checkin=None,
                 is_active=True, last_ip=None, **kwargs):
        self.node_key = node_key or str(uuid.uuid4())
        self.host_identifier = host_identifier
        self.enroll_secret = enroll_secret
        self.enrolled_on = enrolled_on
        self.last_checkin = last_checkin
        self.is_active = is_active
        self.last_ip = last_ip

    def get_config(self, **kwargs):
        from config_assembler import assemble_configuration
        return assemble_configuration(self)

    def get_new_queries(self, **kwargs):
        from config_assembler import assemble_distributed_queries
        return assemble_distributed_queries(self)

    @property
    def display_name(self):
        if 'display_name' in self.node_info and self.node_info['display_name']:
            return self.node_info['display_name']
        elif 'hostname' in self.node_info and self.node_info['hostname']:
            return self.node_info['hostname']
        elif 'computer_name' in self.node_info and self.node_info['computer_name']:
            return self.node_info['computer_name']
        return self.host_identifier
```

`Node` является основной сущностью системы: запись содержит уникальный ключ агента, идентификатор хоста, время последней связи, IP-адрес, статус активности и дополнительные сведения об устройстве.

## Листинг 6 - EAV-модель CMDB

Источник: `migration_py3/src/models.py`

```python
class CmdbObject(SurrogatePK, Model):
    __tablename__ = 'cmdb_object'

    node_id = reference_col('node', nullable=False)
    node = relationship('Node', backref=db.backref('cmdb_objects', lazy='dynamic'))
    object_type = Column(db.String, nullable=False)
    created_at = Column(db.DateTime, default=dt.datetime.utcnow)


class CmdbAttributeDict(SurrogatePK, Model):
    __tablename__ = 'cmdb_attribute_dict'

    name = Column(db.String, nullable=False, unique=True)
    data_type = Column(db.String, default='string')
    description = Column(db.String)


class CmdbValue(SurrogatePK, Model):
    __tablename__ = 'cmdb_value'

    object_id = reference_col('cmdb_object', nullable=False)
    object = relationship(
        'CmdbObject',
        backref=db.backref('values', cascade='all, delete-orphan', lazy='dynamic')
    )

    attribute_id = reference_col('cmdb_attribute_dict', nullable=False)
    attribute = relationship(
        'CmdbAttributeDict',
        backref=db.backref('values', cascade='all, delete-orphan', lazy='dynamic')
    )

    value = Column(db.Text)
```

CMDB реализована по схеме EAV: объект хранится отдельно от словаря атрибутов и значений. Это позволяет сохранять разные типы инвентаризационных данных без изменения структуры таблиц под каждый новый набор полей.

## Листинг 7 - проверка агента по node_key

Источник: `migration_py3/src/api.py`

```python
def node_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'Content-Encoding' in request.headers and \
                request.headers['Content-Encoding'] == 'gzip':
            request._cached_data = gzip.GzipFile(
                fileobj=BytesIO(request.get_data())
            ).read()

        request_json = request.get_json()

        if not request_json or 'node_key' not in request_json:
            current_app.logger.error(
                "%s - Request did not contain valid JSON data.",
                request.remote_addr
            )
            return ""

        node_key = request_json.get('node_key')
        node = Node.query.filter_by(node_key=node_key) \
            .options(db.lazyload('*')).first()

        if not node:
            current_app.logger.error(
                "%s - Could not find node with node_key %s",
                request.remote_addr,
                node_key
            )
            return jsonify(node_invalid=True)

        if not node.is_active:
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
```

Декоратор используется для защищенных API-методов osquery. Он проверяет ключ узла, отсекает неизвестных и отключенных агентов, а также обновляет время последнего обращения и IP-адрес.

## Листинг 8 - прием результатов от osquery-агента

Источник: `migration_py3/src/api.py`

```python
@blueprint.route('/log', methods=['POST', 'PUT'])
@blueprint.route('/v1/log', methods=['POST', 'PUT'])
@node_required
def logger(node=None):
    data = request.get_json()
    log_type = data['log_type']
    log_level = current_app.config['INVENTORY_MINIMUM_OSQUERY_LOG_LEVEL']

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
        except Exception as e:
            current_app.logger.error(
                "Failed to send tasks to Celery: %s",
                str(e)
            )

    else:
        current_app.logger.error(
            "%s - Unknown log_type %r",
            request.remote_addr,
            log_type
        )

    return jsonify(node_invalid=False)
```

Фрагмент показывает основной поток обработки данных: результаты osquery сохраняются в журнал, после чего запускаются фоновые задачи анализа, нормализации в CMDB и обучения по результатам.

## Листинг 9 - фоновые задачи обработки результатов

Источник: `migration_py3/src/tasks.py`

```python
celery = Celery(__name__)


@celery.task(ignore_result=True, name='tasks.analyze_result')
def analyze_result(result, node):
    current_app.rule_manager.handle_log_entry(result, node)
    return


@celery.task(ignore_result=True, name='tasks.normalize_to_cmdb')
def normalize_to_cmdb(result, node_id):
    from services.cmdb_normalization import normalize_to_cmdb_service
    return normalize_to_cmdb_service(result, node_id)


@celery.task()
def learn_from_result(result, node):
    from utils import learn_from_result as learn_from_result_impl
    learn_from_result_impl(result, node)
    return
```

Celery-задачи отделяют прием данных от их последующей обработки. Это снижает время ответа API и позволяет выполнять тяжелую обработку асинхронно.

## Листинг 10 - импорт офлайн-результатов

Источник: `migration_py3/src/services/offline_import.py`

```python
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


def import_grouped_records(grouped):
    from tasks import analyze_result, learn_from_result, normalize_to_cmdb
    from utils import process_result

    nodes_updated = 0
    for host_id, records in grouped.items():
        node = get_or_create_offline_node(host_id, records)
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
        except Exception:
            normalize_to_cmdb(payload, node.id)

        nodes_updated += 1

    return nodes_updated
```

Фрагмент демонстрирует офлайн-сценарий: система принимает файл с результатами, группирует записи по хостам, создает или находит соответствующие узлы и запускает тот же конвейер обработки, что и для онлайн-агентов.

## Листинг 11 - нормализация результатов в CMDB

Источник: `migration_py3/src/services/cmdb_normalization.py`

```python
def extract_object_type(query_name):
    if not query_name:
        return None

    clean_name = query_name.split('/')[-1]
    if clean_name.startswith('cmdb_'):
        return clean_name[5:]
    elif 'cmdb_' in clean_name:
        return clean_name.split('cmdb_')[-1]

    return clean_name


def get_or_create_attribute(key, attributes_cache):
    attr = attributes_cache.get(key)
    if attr:
        return attr

    attr = CmdbAttributeDict.query.filter_by(name=key).first()
    if attr:
        attributes_cache[key] = attr
        return attr

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
    if action not in ('added', 'snapshot'):
        return

    obj = CmdbObject(node_id=node_id, object_type=object_type)
    db.session.add(obj)
    db.session.flush()

    for key, value in columns.items():
        attr = get_or_create_attribute(key, attributes_cache)
        val = CmdbValue(
            object_id=obj.id,
            attribute_id=attr.id,
            value=str(value)
        )
        db.session.add(val)


def normalize_to_cmdb_service(result, node_id):
    node_id = resolve_node_id(node_id)
    if not node_id:
        return

    cleared_types = set()
    results = list(extract_results(result))
    attributes_cache = load_attribute_cache(results)

    try:
        for name, action, columns, timestamp in results:
            object_type = extract_object_type(name)
            if not object_type:
                continue

            replace_snapshot_objects(
                node_id,
                object_type,
                action,
                cleared_types
            )
            persist_cmdb_object(
                node_id,
                object_type,
                action,
                columns,
                attributes_cache
            )

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
```

Это один из ключевых фрагментов системы. Он преобразует строки результатов osquery в объекты CMDB, автоматически создает недостающие атрибуты и сохраняет значения в EAV-структуру.

## Листинг 12 - построение контекста CMDB-отчета

Источник: `migration_py3/src/services/report_queries.py`

```python
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


def build_cmdb_report_context(object_type):
    all_types, type_counts = get_cmdb_type_summary()
    if not object_type:
        return {
            'types': all_types,
            'type_counts': type_counts,
            'active_type': None,
            'columns': [],
            'records': [],
            'total_nodes': 0,
        }

    columns = get_attribute_names(object_type)
    objects, values_by_object = load_objects_with_values(
        object_type,
        newest_first=True
    )

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
```

Фрагмент показывает подготовку данных для динамического CMDB-отчета: система получает доступные типы объектов, атрибуты выбранного типа и значения по каждому объекту.

## Листинг 13 - маршруты CMDB-отчетов

Источник: `migration_py3/src/manage/views.py`

```python
@blueprint.route('/cmdb')
@blueprint.route('/cmdb/<string:object_type>')
@login_required
def cmdb_reports(object_type=None):
    context = build_cmdb_report_context(object_type)
    if not object_type and context['types']:
        return redirect(url_for(
            'manage.cmdb_reports',
            object_type=context['types'][0]
        ))

    return render_template('manage/cmdb_dynamic.html', **context)


@blueprint.route('/cmdb/<string:object_type>/export')
@login_required
def cmdb_export(object_type):
    quoted_filename = quote_cmdb_export_filename(object_type)
    return Response(
        build_cmdb_export_csv(object_type),
        mimetype="text/csv",
        headers={
            "Content-disposition":
                "attachment; filename*=UTF-8''{0}".format(quoted_filename)
        }
    )
```

Фрагмент показывает пользовательские сценарии административного интерфейса: просмотр CMDB-отчетов и экспорт данных.

## Листинг 14 - подключение Alembic к Flask-приложению

Источник: `migration_py3/src/migrations/env.py`

```python
config = context.config

config.set_main_option(
    'sqlalchemy.url',
    current_app.config.get('SQLALCHEMY_DATABASE_URI')
)
target_metadata = current_app.extensions['migrate'].db.metadata


def run_migrations_online():
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    engine = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool
    )

    connection = engine.connect()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        process_revision_directives=process_revision_directives,
        **current_app.extensions['migrate'].configure_args
    )

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Файл связывает Alembic с Flask-конфигурацией и метаданными SQLAlchemy-моделей. Благодаря этому миграции строятся на основе актуальной структуры моделей приложения.


