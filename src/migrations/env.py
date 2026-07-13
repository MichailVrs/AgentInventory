from __future__ import with_statement
from alembic import context
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig
import logging
from flask import current_app

# Это объект конфигурации Alembic, который предоставляет
# доступ к значениям из используемого .ini-файла.
config = context.config

# Интерпретируем файл конфигурации для логирования Python.
# Эта строка настраивает логгеры.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# Добавьте сюда объект MetaData вашей модели
# для поддержки 'autogenerate'.
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url',
                       current_app.config.get('SQLALCHEMY_DATABASE_URI'))
target_metadata = current_app.extensions['migrate'].db.metadata

# Другие значения из конфигурации, нужные env.py,
# можно получить так:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Запускает миграции в режиме 'offline'.

    Настраивает контекст только с URL, а не с Engine, хотя Engine
    здесь тоже допустим. Поскольку Engine не создается, наличие DBAPI
    не требуется.

    Вызовы context.execute() здесь выводят переданную строку
    в вывод скрипта.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Запускает миграции в режиме 'online'.

    В этом сценарии нужно создать Engine и связать соединение с контекстом.

    """

    # Этот callback предотвращает генерацию автомиграции,
    # если в схеме нет изменений.
    # Справка: http://alembic.readthedocs.org/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    engine = engine_from_config(config.get_section(config.config_ini_section),
                                prefix='sqlalchemy.',
                                poolclass=pool.NullPool)

    connection = engine.connect()
    context.configure(connection=connection,
                      target_metadata=target_metadata,
                      process_revision_directives=process_revision_directives,
                      **current_app.extensions['migrate'].configure_args)

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
