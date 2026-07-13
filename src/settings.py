# -*- coding: utf-8 -*-
from binascii import b2a_hex
import datetime as dt
import os


class Config(object):
    SECRET_KEY = os.environ.get("SECRET_KEY", "vkr-inventory-default-secret-key-2026")
    SERVER_NAME = None  # Отключаем строгое совпадение, чтобы исправить 404 за прокси.

    SQLALCHEMY_DATABASE_URI = "postgresql://{user}:{pwd}@{host}:{port}/{dbname}".format(
        user=os.environ.get('POSTGRES_USER'),
        pwd=os.environ.get('POSTGRES_PASSWORD'),
        host=os.environ.get('POSTGRES_HOST'),
        port=os.environ.get('POSTGRES_PORT','5432'),
        dbname=os.environ.get('POSTGRES_DATABASE', 'inventory')
    )

    ASSETS_DEBUG = False
    # Установите следующее значение, чтобы воркеры Celery могли создавать
    # внешние URL-адреса с помощью `url_for`.
    # SERVER_NAME = "inventory.domain.com"
    PREFERRED_URL_SCHEME = 'https'

    ENROLL_SECRET = os.environ.get('ENROLL_SECRET', 'secret')

    # PREFERRED_URL_SCHEME не будет работать без настроенного SERVER_NAME,
    # поэтому для этого нам нужно использовать расширение SSLify.
    # По умолчанию оно включено для всех конфигураций production.
    ENFORCE_SSL = True

    DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
    DEBUG_TB_ENABLED = False
    DEBUG_TB_INTERCEPT_REDIRECTS = os.environ.get('DEBUG_TB_INTERCEPT_REDIRECTS', 'False').lower() in ('true', '1', 'yes')

    APP_DIR = os.path.abspath(os.path.dirname(__file__))  # Эта директория.
    PROJECT_ROOT = os.path.abspath(os.path.join(APP_DIR, os.pardir))

    SQLALCHEMY_TRACK_MODIFICATIONS = os.environ.get('SQLALCHEMY_TRACK_MODIFICATIONS', 'False').lower() in ('true', '1', 'yes')

    # Когда osquery настроен на запуск с флагом командной строки
    # --host_identifier=uuid, установите это значение в True. Это позволит
    # узлам, запрашивающим регистрацию / повторную регистрацию, повторно использовать тот же node_key.
    #
    # Если установлено значение False, узлы, которые впоследствии запрашивают эндпоинт /enroll,
    # получат новый node_key и соответствующую другую запись узла в базе данных.
    # Это приведет к появлению устаревших записей узлов.
    INVENTORY_EXPECTS_UNIQUE_HOST_ID = True
    INVENTORY_CHECKIN_INTERVAL = dt.timedelta(seconds=3600)
    INVENTORY_ENROLL_OVERRIDE = 'enroll_secret'
    INVENTORY_PACK_DELIMITER = '/'
    INVENTORY_MINIMUM_OSQUERY_LOG_LEVEL = 0

    INVENTORY_ENROLL_SECRET_TAG_DELIMITER = None
    INVENTORY_ENROLL_DEFAULT_TAGS = [
    ]

    INVENTORY_CAPTURE_NODE_INFO = [
        ('computer_name', 'name'),
        ('hardware_vendor', 'make'),
        ('hardware_model', 'model'),
        ('hardware_serial', 'serial'),
        ('cpu_brand', 'cpu'),
        ('cpu_physical_cores', 'cpu cores'),
        ('physical_memory', 'memory'),
    ]

    # Система будет проверять запросы на соответствие ожидаемому набору таблиц из
    # osquery. Если вы используете какие-либо пользовательские расширения, вам нужно добавить
    # соответствующую схему сюда, чтобы вы могли использовать их в запросах.
    INVENTORY_EXTRA_SCHEMA = [
        #'CREATE TABLE example_extension_table(thing1 INTEGER, thing2 TEXT);',
    ]
    BROKER_URL = "redis://{host}:{port}/0".format(
        host=os.environ.get('REDIS_HOST'),
        port=os.environ.get('REDIS_PORT','6379')
    )
    CELERY_RESULT_BACKEND = BROKER_URL

    CELERY_ACCEPT_CONTENT = ['djson', 'application/x-djson']
    CELERY_EVENT_SERIALIZER = 'djson'
    CELERY_RESULT_SERIALIZER = 'djson'
    CELERY_TASK_SERIALIZER = 'djson'
    CELERYBEAT_SCHEDULE = {
        'alert-when-node-goes-offline': {
            'task': 'tasks.alert_when_node_goes_offline',
            'schedule': 86400,
        },
    }

    # Здесь вы можете указать набор пользовательских плагинов логгера. Эти плагины будут
    # вызываться для каждого полученного лога состояния или результата, и могут
    # обрабатывать их по своему усмотрению.
    INVENTORY_LOG_PLUGINS = [
        # 'plugins.logs.file.LogPlugin',
        # 'plugins.logs.logstash.LogstashPlugin',
    ]

    # Это конфигурационные переменные для примера плагина логгера, приведенного
    # выше. Раскомментируйте их, чтобы начать логировать результаты или логи состояния в
    # указанный файл.
    # INVENTORY_LOG_FILE_PLUGIN_JSON_LOG = '/tmp/osquery.log'     # По умолчанию: не логировать в json-файл
    # INVENTORY_LOG_FILE_PLUGIN_STATUS_LOG = '/tmp/status.log'     # По умолчанию: не логировать логи состояния
    # INVENTORY_LOG_FILE_PLUGIN_RESULT_LOG = '/tmp/result.log'     # По умолчанию: не логировать результаты
    # INVENTORY_LOG_FILE_PLUGIN_APPEND = True                      # По умолчанию: True

    # Здесь вы можете указать набор плагинов оповещения. Эти плагины могут быть
    # настроены в правилах для отправки оповещений в определенное место. Каждый
    # плагин состоит из полного пути для импорта в сочетании с некоторой
    # конфигурацией для плагина. Обратите внимание, что, поскольку один и тот же оповещатель может быть
    # настроен несколько раз под разными именами, мы предоставляем конфигурацию для каждого имени отдельно.
    INVENTORY_ALERTER_PLUGINS = {
        'debug': ('plugins.alerters.debug.DebugAlerter', {
            'level': 'error',
        }),

        # 'pagerduty-security': ('inventory.plugins.alerters.pagerduty.PagerDutyAlerter', {
        #     # Обязательно
        #     'service_key': 'foobar',

        #     # Необязательно
        #     'client_url': 'https://inventory.domain.com',
        #     'key_format': 'inventory-security-{count}',
        # }),

        # 'email': ('inventory.plugins.alerters.emailer.EmailAlerter', {
        #     # Обязательно
        #     'recipients': [
        #         # 'security@example.com',
        #     ],

        #     # Необязательно, шаблоны см. в inventory/plugins/alerters/emailer.py
        #     'subject_prefix': '[Inventory]',
        #     'subject_template': '',
        #     'message_template': '',

        # }),

        # 'sentry': ('inventory.plugins.alerters.sentry.SentryAlerter', {
        #     'dsn': 'https://<key>:<secret>@app.getsentry.com/<project>',
        # }),

        # 'slack': ('inventory.plugins.alerters.slack.SlackAlerter', {
        #     # Обязательно, создайте webhook здесь: https://my.slack.com/services/new/incoming-webhook/
        #     'slack_webhook' : 'https://example.com/slack-webhook-placeholder',

        #     # Необязательно
        #     'printColumns': False,
        #     'color': '#36a64f',
        # })
    }

    # MAIL_SERVER = 'localhost'
    # MAIL_PORT = 25
    # MAIL_USE_TLS = False
    # MAIL_USE_SSL = False
    # MAIL_USERNAME = None
    # MAIL_PASSWORD = None
    MAIL_DEFAULT_SENDER = 'inventory@localhost'

    # Система использует WatchedFileHandler из модуля logging.handlers.
    # Система сама должна периодически ротировать эти логи, так как файл
    # будет бесконечно расти. Для получения дополнительной информации см.
    # https://docs.python.org/dev/library/logging.handlers.html#watchedfilehandler
    # В качестве альтернативы вы можете установить имя файла в '-', чтобы логировать в stdout.
    INVENTORY_LOGGING_FILENAME = '-'
    INVENTORY_LOGGING_FORMAT = '%(asctime)s -  %(name)s - %(levelname)s - %(thread)d - %(message)s'
    INVENTORY_LOGGING_LEVEL = 'WARNING'

    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_DURATION = dt.timedelta(days=30)
    REMEMBER_COOKIE_PATH = '/manage'
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True

    # см. http://flask-login.readthedocs.io/en/latest/#session-protection
    # применяется только когда AUTH_METHOD = 'inventory'
    SESSION_PROTECTION = "strong"

    BCRYPT_LOG_ROUNDS = 13
    WTF_CSRF_SSL_STRICT = False
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False

    AUTH_METHOD = None
    # AUTH_METHOD = 'internal'
    # AUTH_METHOD = 'google'
    # AUTH_METHOD = 'ldap'

    INVENTORY_OAUTH_GOOGLE_ALLOWED_DOMAINS = [
    ]

    INVENTORY_OAUTH_GOOGLE_ALLOWED_USERS = [
    ]

    INVENTORY_OAUTH_CLIENT_ID = ''
    INVENTORY_OAUTH_CLIENT_SECRET = ''

    # При использовании AUTH_METHOD = 'ldap' см.
    # http://flask-ldap3-login.readthedocs.io/en/latest/configuration.html#core
    # Примечание: не все параметры конфигурации задокументированы по ссылке
    # выше. Полный список опций можно изучить, просмотрев
    # исходный код flask-ldap3-login.

    # LDAP_HOST = None
    # LDAP_PORT = 636
    # LDAP_USE_SSL = True
    # LDAP_BASE_DN = 'dc=example,dc=org'
    # LDAP_USER_DN = 'ou=People'
    # LDAP_GROUP_DN = ''
    # LDAP_USER_OBJECT_FILTER = '(objectClass=inetOrgPerson)'
    # LDAP_USER_LOGIN_ATTR = 'uid'
    # LDAP_USER_RDN_ATTR = 'uid'
    # LDAP_GROUP_SEARCH_SCOPE = 'SEARCH_SCOPE_WHOLE_SUBTREE'
    # LDAP_GROUP_OBJECT_FILTER = '(cn=*)(objectClass=groupOfUniqueNames)'
    # LDAP_GROUP_MEMBERS_ATTR = 'uniquemember'
    # LDAP_GET_GROUP_ATTRIBUTES = ['cn']
    # LDAP_OPT_X_TLS_CACERTFILE = None
    # LDAP_OPT_X_TLS_CERTIFICATE_FILE = None
    # LDAP_OPT_X_TLS_PRIVATE_KEY_FILE = None
    # LDAP_OPT_X_TLS_REQUIRE_CERT = 2  # ssl.CERT_REQUIRED
    # LDAP_OPT_X_TLS_USE_VERSION = 3  # ssl.PROTOCOL_TLSv1
    # LDAP_OPT_X_TLS_VALID_NAMES = []

    # Чтобы включить отчеты Sentry, настройте следующие ключи
    # https://docs.getsentry.com/hosted/clients/python/integrations/flask/
    # SENTRY_DSN = 'https://<key>:<secret>@app.getsentry.com/<project>'
    # SENTRY_INCLUDE_PATHS = ['inventory']
    # SENTRY_USER_ATTRS = ['username', 'first_name', 'last_name', 'email']
    #
    # https://docs.getsentry.com/hosted/clients/python/advanced/#sanitizing-data
    # SENTRY_PROCESSORS = [
    #     'raven.processors.SanitizePasswordsProcessor',
    # ]
    # RAVEN_IGNORE_EXCEPTIONS = []


class ProdConfig(Config):

    ENV = 'prod'
    DEBUG = False
    DEBUG_TB_ENABLED = False
    DEBUG_TB_INTERCEPT_REDIRECTS = False

    ENFORCE_SSL = True

    SQLALCHEMY_DATABASE_URI = ''

    ENROLL_SECRET = [

    ]
    INVENTORY_MINIMUM_OSQUERY_LOG_LEVEL = 1

    BROKER_URL = ''
    CELERY_RESULT_BACKEND = ''


class DevConfig(Config):
    """
    Этот класс определяет конфигурацию, подходящую для разработки.
    Ее не следует использовать для запуска в рабочей среде (production).
    """
    ENV = 'dev'
    DEBUG = True
    DEBUG_TB_ENABLED = True
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    ASSETS_DEBUG = True

    # SQLALCHEMY_DATABASE_URI наследуется из Config.

    ENROLL_SECRET = [
        'secret',
    ]



class TestConfig(Config):
    """
    Этот класс определяет конфигурацию, которая используется для тестов.
    """
    TESTING = True
    DEBUG = True

    SQLALCHEMY_DATABASE_URI = 'postgresql://localhost:5432/inventory_test'

    WTF_CSRF_ENABLED = False

    ENROLL_SECRET = [
        'secret',
    ]
    INVENTORY_EXPECTS_UNIQUE_HOST_ID = False

    AUTH_METHOD = None

    INVENTORY_COLUMN_RENDER = {
        'computer_name': '<a href="https://{{ value | urlencode }}/">{{ value }}</a>'
    }
