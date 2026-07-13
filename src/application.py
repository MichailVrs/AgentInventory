# -*- coding: utf-8 -*-
import os

from flask import Flask,render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from api import blueprint as api
from assets import assets
from manage import blueprint as backend
from extensions import (
    bcrypt, csrf, db, debug_toolbar, ldap_manager, log_tee, login_manager,
    mail, make_celery, migrate, rule_manager, sentry
)
from settings import ProdConfig
from tasks import celery
from utils import get_node_health, pretty_field, pretty_operator, render_column, ru_translate, relative_time


def create_app(config=ProdConfig):
    app = Flask(__name__)
    app.config.from_object(config)
    app.config.from_envvar('INVENTORY_SETTINGS', silent=True)

    # Проверка безопасности секретных ключей при запуске приложения в рабочей среде
    if not app.testing and not app.debug:
        if app.config.get('SECRET_KEY') in ("vkr-inventory-default-secret-key-2026", "super-secret-production-key-change-me") or not os.environ.get("SECRET_KEY"):
            raise ValueError("Критическая ошибка безопасности: Переменная окружения SECRET_KEY не задана или использует небезопасное стандартное значение в .env.")
        if app.config.get('ENROLL_SECRET') == "secret" or not os.environ.get("ENROLL_SECRET"):
            raise ValueError("Критическая ошибка безопасности: Переменная окружения ENROLL_SECRET не задана или использует небезопасное стандартное значение в .env.")

    register_blueprints(app)
    register_errorhandlers(app)
    register_loggers(app)
    register_extensions(app)
    register_auth_method(app)
    register_filters(app)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    return app


def register_blueprints(app):
    app.register_blueprint(api)
    csrf.exempt(api)

    # Если переменная окружения INVENTORY_NO_MANAGER не задана,
    # зарегистрировать блупринт бэкенда (панель управления). Это полезно,
    # когда требуется развернуть только API как отдельный сервис.

    if 'INVENTORY_NO_MANAGER' in os.environ:
        return

    app.register_blueprint(backend)


def register_extensions(app):
    bcrypt.init_app(app)
    csrf.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    assets.init_app(app)
    # debug_toolbar.init_app(app)
    log_tee.init_app(app)
    rule_manager.init_app(app)
    mail.init_app(app)
    make_celery(app, celery)
    login_manager.init_app(app)
    sentry.init_app(app)
    if app.config['ENFORCE_SSL']:
        # Из-за архитектуры flask-sslify его конструктор ожидает запуска
        # внутри контекста приложения, если только объект приложения не передан явно.
        # В результате мы не можем создать объект sslify в модуле `extensions`
        # без возникновения ошибки.
        from flask_sslify import SSLify
        SSLify(app)


def register_loggers(app):
    if app.debug:
        return

    import logging
    from logging.handlers import WatchedFileHandler
    import sys

    logfile = app.config['INVENTORY_LOGGING_FILENAME']
    if logfile == '-':
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = WatchedFileHandler(logfile)
    levelname = app.config['INVENTORY_LOGGING_LEVEL']
    if levelname in ('DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'CRITICAL'):
        handler.setLevel(getattr(logging, levelname))
    formatter = logging.Formatter(app.config['INVENTORY_LOGGING_FORMAT'])
    handler.setFormatter(formatter)

    app.logger.addHandler(handler)


def register_errorhandlers(app):
    """Регистрация обработчиков ошибок."""
    from flask_wtf.csrf import CSRFError
    from flask import redirect, url_for, flash, request

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        flash(u'Срок действия сессии (CSRF-токена) истек. Пожалуйста, попробуйте еще раз.', 'danger')
        next_url = request.referrer or url_for('manage.index')
        return redirect(next_url)

    def render_error(error):
        """Отрисовка шаблона ошибки."""
        # Если это HTTPException, извлекаем атрибут 'code'; по умолчанию 500
        error_code = getattr(error, 'code', 500)
        if 'INVENTORY_NO_MANAGER' in os.environ:
            return '', 400
        return render_template('{0}.html'.format(error_code)), error_code

    for errcode in [400, 401, 403, 404, 500]:
        app.errorhandler(errcode)(render_error)


def register_filters(app):
    app.jinja_env.filters['health'] = get_node_health
    app.jinja_env.filters['pretty_field'] = pretty_field
    app.jinja_env.filters['pretty_operator'] = pretty_operator
    app.jinja_env.filters['render'] = render_column
    app.jinja_env.filters['ru_translate'] = ru_translate
    app.jinja_env.filters['relative_time'] = relative_time


def register_auth_method(app):
    from users import views
    app.register_blueprint(views.blueprint)

    if app.config['AUTH_METHOD'] is None:
        from users.mixins import NoAuthUserMixin
        login_manager.anonymous_user = NoAuthUserMixin
        return

    login_manager.login_view = 'users.login'
    login_manager.login_message_category = 'warning'

    if app.config['AUTH_METHOD'] == 'ldap':
        ldap_manager.init_app(app)
        return

    # Другие методы аутентификации отсутствуют, переключаемся на OAuth

    if app.config['AUTH_METHOD'] != 'internal':
        login_manager.login_message = None
        login_manager.needs_refresh_message = None

        from users.oauth import OAuthLogin
        provider = OAuthLogin.get_provider(app.config['AUTH_METHOD'])
        provider.init_app(app)
