"""Добавляет таблицу rule для настройки правил и оповещений.

Revision ID: fd28e46e46a6
Revises: d2b00dd93241
Create Date: 2016-05-02 17:46:46.658227

"""

# Идентификаторы ревизии, используемые Alembic.
revision = 'fd28e46e46a6'
down_revision = 'd2b00dd93241'

from alembic import op
import sqlalchemy as sa
import database
from sqlalchemy.dialects import postgresql

def upgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.create_table('rule',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('action', sa.Enum('added', 'removed', 'both', name='rule_actions'), nullable=False),
    sa.Column('alerters', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('config', postgresql.JSONB(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    ### Конец команд Alembic ###


def downgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.drop_table('rule')
    ### Конец команд Alembic ###
    postgresql.ENUM(name='rule_actions').drop(op.get_bind(), checkfirst=False)
