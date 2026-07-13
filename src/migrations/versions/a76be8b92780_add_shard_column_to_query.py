"""Добавляет колонку shard в query.

Revision ID: a76be8b92780
Revises: c107fa0468ff
Create Date: 2017-08-25 11:39:24.754460

"""

# Идентификаторы ревизии, используемые Alembic.
revision = 'a76be8b92780'
down_revision = 'c107fa0468ff'

from alembic import op
import sqlalchemy as sa
import database


def upgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    query_tbl = sa.sql.table('query', sa.sql.column('platform', sa.String))
    pack_tbl = sa.sql.table('pack', sa.sql.column('platform', sa.String))
    op.execute(
        query_tbl.update() \
            .where(
                sa.or_(
                    query_tbl.c.platform==op.inline_literal('redhat,centos'),
                    query_tbl.c.platform==op.inline_literal('ubuntu'),
                )
            ).values({'platform': op.inline_literal('linux')})
    )
    op.execute(
        pack_tbl.update() \
            .where(
                sa.or_(
                    query_tbl.c.platform==op.inline_literal('redhat,centos'),
                    query_tbl.c.platform==op.inline_literal('ubuntu'),
                )
            ).values({'platform': op.inline_literal('linux')})
    )
    op.add_column('query', sa.Column('shard', sa.Integer(), nullable=True))
    ### Конец команд Alembic ###


def downgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.drop_column('query', 'shard')
    ### Конец команд Alembic ###
