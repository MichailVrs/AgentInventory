"""Добавляет поле version, появившееся в osquery v1.7.4.

Revision ID: 14c992522209
Revises: 0bc0a93ac867
Create Date: 2016-05-13 14:31:45.273281

"""

# Идентификаторы ревизии, используемые Alembic.
revision = '14c992522209'
down_revision = '0bc0a93ac867'

from alembic import op
import sqlalchemy as sa
import database


def upgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.add_column('status_log', sa.Column('version', sa.String(), nullable=True))
    ### Конец команд Alembic ###


def downgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.drop_column('status_log', 'version')
    ### Конец команд Alembic ###
