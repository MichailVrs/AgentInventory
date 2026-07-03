# -*- coding: utf-8 -*-
from collections import defaultdict
import io
from database import db
from models import CmdbAttributeDict, CmdbObject, CmdbValue, Node
from services.excel_csv import (
    EXCEL_CSV_PREAMBLE,
    excel_csv_writer,
    format_csv_value,
)

def generate_custom_report(selected_attribute_ids):
    """Генерирует сводный отчет по списку выбранных ID атрибутов."""
    if not selected_attribute_ids:
        return {
            'columns': [],
            'records': [],
        }

    attributes = CmdbAttributeDict.query.filter(
        CmdbAttributeDict.id.in_(selected_attribute_ids)
    ).all()
    
    headers_map = {attr.id: attr.name for attr in attributes}
    column_names = [attr.name for attr in attributes]

    values = db.session.query(
        CmdbObject.node_id,
        CmdbValue.attribute_id,
        CmdbValue.value
    ).join(CmdbValue, CmdbValue.object_id == CmdbObject.id)\
     .filter(CmdbValue.attribute_id.in_(selected_attribute_ids)).all()

    report_data = defaultdict(dict)
    for node_id, attr_id, val in values:
        attr_name = headers_map.get(attr_id)
        if attr_name:
            if attr_name in report_data[node_id]:
                existing = report_data[node_id][attr_name]
                if val and val not in existing.split(', '):
                    report_data[node_id][attr_name] = existing + u", " + val
            else:
                report_data[node_id][attr_name] = val or ''

    # Оптимизация: загружаем только те узлы, у которых есть значения для выбранных атрибутов
    node_ids = [nid for nid in report_data.keys() if nid is not None]
    if not node_ids:
        nodes = []
    else:
        nodes = Node.query.filter(Node.id.in_(node_ids)).order_by(Node.host_identifier).all()

    records = []
    for node in nodes:
        row = {
            'node_name': node.display_name,
            'last_checkin': node.last_checkin.strftime('%Y-%m-%d %H:%M') if node.last_checkin else u'Нет связи'
        }
        for col in column_names:
            row[col] = report_data[node.id].get(col, u'—')
        records.append(row)

    return {
        'columns': column_names,
        'records': records
    }

def build_custom_export_csv(selected_attribute_ids):
    """Формирует CSV файл для кастомного отчета."""
    report = generate_custom_report(selected_attribute_ids)
    
    output = io.StringIO()
    output.write(EXCEL_CSV_PREAMBLE)
    
    ru_fieldnames = [u'Узел', u'Последний сеанс связи'] + report['columns']
    
    writer = excel_csv_writer(output)
    writer.writerow(ru_fieldnames)

    for row in report['records']:
        line = [format_csv_value(row['node_name']), format_csv_value(row['last_checkin'])]
        for col in report['columns']:
            line.append(format_csv_value(row[col]))
        writer.writerow(line)

    return output.getvalue()
