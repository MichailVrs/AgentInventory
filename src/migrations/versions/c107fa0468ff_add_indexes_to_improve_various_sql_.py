"""Добавляет индексы для ускорения различных SQL-запросов.

Revision ID: c107fa0468ff
Revises: 236318ee3d3e
Create Date: 2017-08-22 15:33:13.706301

"""

# Идентификаторы ревизии, используемые Alembic.
revision = 'c107fa0468ff'
down_revision = '236318ee3d3e'

from alembic import op
import sqlalchemy as sa
import database


def upgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.create_index('idx_distributed_query_task_node_id_status', 'distributed_query_task', ['node_id', 'status'], unique=False)
    op.create_index(op.f('ix_file_path_tags_file_path_id'), 'file_path_tags', ['file_path_id'], unique=False)
    op.create_index(op.f('ix_node_tags_node_id'), 'node_tags', ['node_id'], unique=False)
    op.create_index(op.f('ix_pack_tags_pack_id'), 'pack_tags', ['pack_id'], unique=False)
    op.create_index(op.f('ix_query_tags_query_id'), 'query_tags', ['query_id'], unique=False)
    op.create_index('idx_result_log_node_id_timestamp_desc', 'result_log', ['node_id', sa.text(u'timestamp DESC')], unique=False)
    op.create_index('idx_status_log_node_id_created_desc', 'status_log', ['node_id', sa.text(u'created DESC')], unique=False)
    ### Конец команд Alembic ###


def downgrade():
    ### Команды автоматически сгенерированы Alembic - при необходимости поправьте! ###
    op.drop_index('idx_status_log_node_id_created_desc', table_name='status_log')
    op.drop_index('idx_result_log_node_id_timestamp_desc', table_name='result_log')
    op.drop_index(op.f('ix_query_tags_query_id'), table_name='query_tags')
    op.drop_index(op.f('ix_pack_tags_pack_id'), table_name='pack_tags')
    op.drop_index(op.f('ix_node_tags_node_id'), table_name='node_tags')
    op.drop_index(op.f('ix_file_path_tags_file_path_id'), table_name='file_path_tags')
    op.drop_index('idx_distributed_query_task_node_id_status', table_name='distributed_query_task')
    ### Конец команд Alembic ###
