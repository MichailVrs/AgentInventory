# -*- coding: utf-8 -*-
import datetime as dt
import csv


EXCEL_CSV_PREAMBLE = u'\ufeffsep=;\r\n'
EXCEL_CSV_PREAMBLE_BYTES = EXCEL_CSV_PREAMBLE.encode('utf-8')
EXCEL_CSV_DELIMITER = ';'
EXCEL_CSV_LINETERMINATOR = '\r\n'


def excel_csv_writer(output):
    return csv.writer(
        output,
        delimiter=EXCEL_CSV_DELIMITER,
        lineterminator=EXCEL_CSV_LINETERMINATOR,
    )


def excel_csv_dict_writer(output, fieldnames):
    return csv.DictWriter(
        output,
        fieldnames=fieldnames,
        delimiter=EXCEL_CSV_DELIMITER,
        lineterminator=EXCEL_CSV_LINETERMINATOR,
    )


def format_csv_value(value):
    if value is None:
        return ''

    if isinstance(value, bool):
        return u'Да' if value else u'Нет'

    if isinstance(value, dt.datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')

    if isinstance(value, dt.date):
        return value.strftime('%Y-%m-%d')

    return str(value).replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
