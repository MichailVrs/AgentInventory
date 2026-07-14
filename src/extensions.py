# -*- coding: utf-8 -*-
from flask_bcrypt import Bcrypt
from flask_ldap3_login import LDAP3LoginManager
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from raven import Client
from raven.contrib.celery import register_signal, register_logger_signal
from raven.contrib.flask import Sentry


class LogTee(object):
    def __init__(self, app=None):
        self.app = app
        self.plugins = []

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        from importlib import import_module
        from plugins import AbstractLogsPlugin

        plugins = app.config.setdefault('INVENTORY_LOG_PLUGINS', [])

        for plugin in plugins:
            package, classname = plugin.rsplit('.', 1)
            module = import_module(package)
            klass = getattr(module, classname, None)

            if klass is None:
                raise ValueError('Could not find a class named "{0}" in package "{1}"'.format(classname, package))

            if not issubclass(klass, AbstractLogsPlugin):
                raise ValueError('{0} is not a subclass of AbstractLogsPlugin'.format(klass))

            self.plugins.append(klass(app.config))

    def handle_status(self, data, **kwargs):
        for plugin in self.plugins:
            plugin.handle_status(data, **kwargs)

    def handle_result(self, data, **kwargs):
        for plugin in self.plugins:
            plugin.handle_result(data, **kwargs)


class RuleManager(object):
    def __init__(self, app=None):
        self.network = None
        self.last_update = None
        self.rules_map = {}

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        self.load_alerters()

        # Сохраняем этот экземпляр в приложении, чтобы к нему можно было обратиться.
        app.rule_manager = self

    def load_alerters(self):
        """Загружает плагины оповещения, указанные в конфигурации приложения."""
        from importlib import import_module
        from plugins import AbstractAlerterPlugin

        alerters = self.app.config.get('INVENTORY_ALERTER_PLUGINS', {})

        self.alerters = {}
        for name, (plugin, config) in alerters.items():
            package, classname = plugin.rsplit('.', 1)
            module = import_module(package)
            klass = getattr(module, classname, None)

            if klass is None:
                raise ValueError('Could not find a class named "{0}" in package "{1}"'.format(classname, package))

            if not issubclass(klass, AbstractAlerterPlugin):
                raise ValueError('{0} is not a subclass of AbstractAlerterPlugin'.format(name))

            self.alerters[name] = klass(config)

    def should_reload_rules(self):
        """Проверяет, нужно ли перезагрузить набор правил."""
        from models import Rule

        if self.last_update is None:
            return True

        newest_rule = Rule.query.order_by(Rule.updated_at.desc()).limit(1).first()
        if newest_rule and self.last_update < newest_rule.updated_at:
            return True

        return False

    def load_rules(self):
        """Загружает правила из базы данных."""
        from rules import Network
        from models import Rule

        if not self.should_reload_rules():
            return

        all_rules = list(Rule.query.all())

        self.network = Network()
        self.rules_map = {r.id: r for r in all_rules}

        if not all_rules:
            return

        for rule in all_rules:
            # Проверяем оповещатели.
            for alerter in rule.alerters:
                if alerter not in self.alerters:
                    raise ValueError('No such alerter: "{0}"'.format(alerter))

            # Создаем правило.
            self.network.parse_query(rule.conditions, alerters=rule.alerters, rule_id=rule.id)

        # Сохраняем дату последнего обновления.
        # Важно: делаем это здесь, а не в should_reload_rules, потому что
        # правило могло быть перезагружено между двумя функциями, и тогда
        # мы случайно не перезагрузим правила, когда это действительно нужно.
        self.last_update = max(r.updated_at for r in all_rules)

    def handle_log_entry(self, entry, node):
        """Основная точка входа для обработки входящих записей логов."""
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
            if len(alerts) == 0:
                continue

            # Alerts - это набор кортежей (имя оповещателя, id правила).
            # Преобразуем их в экземпляры RuleMatch, именно их ожидают
            # наши оповещатели.
            for alerter, rule_id in alerts:
                rule = self.rules_map.get(rule_id)
                if not rule:
                    rule = Rule.get_by_id(rule_id)

                to_trigger.append((alerter, RuleMatch(
                    rule=rule,
                    result=result,
                    node=node
                )))

        # Когда все результаты собраны, начинаем запускать оповещения.
        for alerter, match in to_trigger:
            self.alerters[alerter].handle_alert(node, match)


def make_celery(app, celery):
    """По материалам http://flask.pocoo.org/docs/0.10/patterns/celery/."""
    # Регистрируем собственный тип сериализатора перед обновлением конфигурации.
    from kombu.serialization import register
    from celery_serializer import djson_dumps, djson_loads

    register(
        'djson', djson_dumps, djson_loads,
        content_type='application/x-djson',
        content_encoding='utf-8'
    )

    # Обновляем конфигурацию.
    celery.config_from_object(app.config)

    # Регистрируем клиент Sentry.
    if 'SENTRY_DSN' in app.config and app.config['SENTRY_DSN']:
        client = Client(app.config['SENTRY_DSN'])
        # Регистрируем пользовательский фильтр для отсеивания дублирующихся логов.
        register_logger_signal(client)
        # Подключаемся к обработчику ошибок Celery.
        register_signal(client)

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
log_tee = LogTee()
ldap_manager = LDAP3LoginManager()
login_manager = LoginManager()
rule_manager = RuleManager()
sentry = Sentry()
