"""Добавляет логирование выполнения для задач оперативных запросов.

Revision ID: 9a1e305c4b91
Revises: e1b1c1e14930
Create Date: 2026-06-09 14:22:51.798928

"""

# Идентификаторы ревизии, используемые Alembic.
revision = '9a1e305c4b91'
down_revision = 'e1b1c1e14930'

from alembic import op
import sqlalchemy as sa
import database


def upgrade():
    # ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    with op.batch_alter_table('distributed_query_task', schema=None) as batch_op:
        batch_op.add_column(sa.Column('started_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('finished_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('error_message', sa.String(), nullable=True))

    # ### Конец команд Alembic ###


def downgrade():
    # ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    with op.batch_alter_table('distributed_query_task', schema=None) as batch_op:
        batch_op.drop_column('error_message')
        batch_op.drop_column('finished_at')
        batch_op.drop_column('started_at')

    # ### Конец команд Alembic ###
