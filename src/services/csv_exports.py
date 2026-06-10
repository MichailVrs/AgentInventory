# -*- coding: utf-8 -*-
import csv
import io
from services.report_queries import get_attribute_names, load_objects_with_values, UNKNOWN_NODE

def build_cmdb_export_csv(object_type):
    columns = get_attribute_names(object_type)
    fieldnames = ['node', 'created_at'] + columns

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    objects, values_by_object = load_objects_with_values(object_type)
    for obj in objects:
        row = {
            'node': obj.node.display_name if obj.node else UNKNOWN_NODE,
            'created_at': obj.created_at.isoformat(),
        }
        for value in values_by_object[obj.id]:
            row[value.attribute.name] = value.value if value.value else ''
        writer.writerow(row)

    return output.getvalue()

def quote_cmdb_export_filename(object_type):
    try:
        from urllib.parse import quote
    except ImportError:
        from urllib import quote
    return quote("cmdb_{0}.csv".format(object_type))
