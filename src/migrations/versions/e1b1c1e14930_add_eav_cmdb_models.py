# -*- coding: utf-8 -*-
"""Добавляет EAV-модели CMDB.

Revision ID: e1b1c1e14930
Revises: a76be8b92780
Create Date: 2026-04-23 12:44:00.000000

"""

# Идентификаторы ревизии, используемые Alembic.
revision = 'e1b1c1e14930'
down_revision = 'a76be8b92780'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # 1. Создаем таблицы
    op.create_table('cmdb_object',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.Column('object_type', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['node_id'], ['node.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('cmdb_attribute_dict',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('data_type', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    op.create_table('cmdb_value',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('object_id', sa.Integer(), nullable=False),
        sa.Column('attribute_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['attribute_id'], ['cmdb_attribute_dict.id'], ),
        sa.ForeignKeyConstraint(['object_id'], ['cmdb_object.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Создаем Views прямо здесь
    op.execute("""
    CREATE OR REPLACE VIEW software_view AS
    SELECT 
        o.node_id,
        o.id AS object_id,
        MAX(CASE WHEN a.name = 'name' THEN v.value END) AS name,
        MAX(CASE WHEN a.name = 'version' THEN v.value END) AS version,
        MAX(CASE WHEN a.name = 'publisher' THEN v.value END) AS publisher,
        MAX(CASE WHEN a.name = 'install_date' THEN v.value END) AS install_date
    FROM cmdb_object o
    JOIN cmdb_value v ON v.object_id = o.id
    JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
    WHERE o.object_type = 'software'
    GROUP BY o.id, o.node_id;

    CREATE OR REPLACE VIEW usb_view AS
    SELECT 
        o.node_id,
        o.id AS object_id,
        MAX(CASE WHEN a.name = 'vendor' THEN v.value END) AS vendor,
        MAX(CASE WHEN a.name = 'model' THEN v.value END) AS model,
        MAX(CASE WHEN a.name = 'serial' THEN v.value END) AS serial,
        MAX(CASE WHEN a.name = 'usb_port' THEN v.value END) AS usb_port
    FROM cmdb_object o
    JOIN cmdb_value v ON v.object_id = o.id
    JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
    WHERE o.object_type = 'usb'
    GROUP BY o.id, o.node_id;

    CREATE OR REPLACE VIEW network_view AS
    SELECT 
        o.node_id,
        o.id AS object_id,
        MAX(CASE WHEN a.name = 'interface' THEN v.value END) AS interface,
        MAX(CASE WHEN a.name = 'mac' THEN v.value END) AS mac,
        MAX(CASE WHEN a.name = 'address' THEN v.value END) AS ip_address,
        MAX(CASE WHEN a.name = 'mask' THEN v.value END) AS mask
    FROM cmdb_object o
    JOIN cmdb_value v ON v.object_id = o.id
    JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
    WHERE o.object_type = 'network'
    GROUP BY o.id, o.node_id;
    """)


def downgrade():
    op.execute("DROP VIEW IF EXISTS network_view;")
    op.execute("DROP VIEW IF EXISTS usb_view;")
    op.execute("DROP VIEW IF EXISTS software_view;")
    
    op.drop_table('cmdb_value')
    op.drop_table('cmdb_attribute_dict')
    op.drop_table('cmdb_object')
