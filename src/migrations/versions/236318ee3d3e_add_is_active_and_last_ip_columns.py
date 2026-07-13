"""Добавляет колонки is_active и last_ip в таблицу node.

Revision ID: 236318ee3d3e
Revises: 54ef3f06612c
Create Date: 2016-06-21 10:48:13.099132

"""

# Идентификаторы ревизии, используемые Alembic.
revision = '236318ee3d3e'
down_revision = '54ef3f06612c'

from alembic import op
import sqlalchemy as sa
import database
from sqlalchemy.dialects import postgresql

def upgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.add_column('node', sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False))
    op.add_column('node', sa.Column('last_ip', postgresql.INET(), nullable=True))
    ### Конец команд Alembic ###


def downgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.drop_column('node', 'last_ip')
    op.drop_column('node', 'is_active')
    ### Конец команд Alembic ###
