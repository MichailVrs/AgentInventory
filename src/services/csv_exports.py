# -*- coding: utf-8 -*-
import io
from services.report_queries import get_attribute_names, load_objects_with_values, UNKNOWN_NODE
from services.excel_csv import (
    EXCEL_CSV_PREAMBLE,
    excel_csv_dict_writer,
    format_csv_value,
)

def build_cmdb_export_csv(object_type):
    columns = get_attribute_names(object_type)
    fieldnames = ['node', 'created_at'] + columns

    output = io.StringIO()
    output.write(EXCEL_CSV_PREAMBLE)
    writer = excel_csv_dict_writer(output, fieldnames=fieldnames)
    writer.writeheader()

    objects, values_by_object = load_objects_with_values(object_type)
    for obj in objects:
        row = {
            'node': format_csv_value(obj.node.display_name if obj.node else UNKNOWN_NODE),
            'created_at': format_csv_value(obj.created_at),
        }
        for value in values_by_object[obj.id]:
            row[value.attribute.name] = format_csv_value(value.value)
        writer.writerow(row)

    return output.getvalue()

def quote_cmdb_export_filename(object_type):
    try:
        from urllib.parse import quote
    except ImportError:
        from urllib import quote
    return quote("cmdb_{0}.csv".format(object_type))
