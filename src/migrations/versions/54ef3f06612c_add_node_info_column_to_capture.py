"""Добавляет колонку "node_info" для сбора произвольной информации об узле на лету.

Revision ID: 54ef3f06612c
Revises: c17f01adbe31
Create Date: 2016-06-15 10:31:13.791641

"""

# Идентификаторы ревизии, используемые Alembic.
revision = '54ef3f06612c'
down_revision = 'c17f01adbe31'

from alembic import op
import sqlalchemy as sa
import database
from sqlalchemy.dialects import postgresql

def upgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.add_column('node', sa.Column('node_info', postgresql.JSONB(), server_default='{}', nullable=False))
    op.drop_index('idx__rule__updated_at', table_name='rule')
    ### Конец команд Alembic ###


def downgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.create_index('idx__rule__updated_at', 'rule', ['updated_at'], unique=False)
    op.drop_column('node', 'node_info')
    ### Конец команд Alembic ###
