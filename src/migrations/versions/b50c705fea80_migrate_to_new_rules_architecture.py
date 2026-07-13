"""Переносит данные на новую архитектуру правил.

Revision ID: b50c705fea80
Revises: 4f95ecd76bf8
Create Date: 2016-05-26 16:17:40.084938

"""

# Идентификаторы ревизии, используемые Alembic.
revision = 'b50c705fea80'
down_revision = '4f95ecd76bf8'

from alembic import op
import sqlalchemy as sa
import database
from sqlalchemy.dialects import postgresql

def upgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.add_column('rule', sa.Column('conditions', postgresql.JSONB(), nullable=True))
    op.add_column('rule', sa.Column('description', sa.String(), nullable=True))
    op.drop_column('rule', 'action')
    op.drop_column('rule', 'type')
    op.drop_column('rule', 'config')
    ### Конец команд Alembic ###


def downgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.add_column('rule', sa.Column('config', postgresql.JSONB(), autoincrement=False, nullable=True))
    op.add_column('rule', sa.Column('type', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.add_column('rule', sa.Column('action', postgresql.ENUM(u'added', u'removed', u'both', name='rule_actions'), autoincrement=False, nullable=False))
    op.drop_column('rule', 'description')
    op.drop_column('rule', 'conditions')
    ### Конец команд Alembic ###
