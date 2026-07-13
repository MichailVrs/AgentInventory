"""Добавляет колонку "updated_at" в Rule.

Revision ID: c17f01adbe31
Revises: b50c705fea80
Create Date: 2016-05-27 15:51:58.168840

"""

# Идентификаторы ревизии, используемые Alembic.
revision = 'c17f01adbe31'
down_revision = 'b50c705fea80'

from alembic import op
import sqlalchemy as sa
import database


def upgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.add_column('rule',
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
    ### Конец команд Alembic ###

    op.create_index('idx__rule__updated_at', 'rule', ['updated_at'])


def downgrade():
    op.drop_index('idx__rule__updated_at')
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.drop_column('rule', 'updated_at')
    ### Конец команд Alembic ###
