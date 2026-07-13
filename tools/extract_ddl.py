# -*- coding: utf-8 -*-
import ast


# Это должно быть глобальной переменной из-за особенностей работы с `exec`.
current_spec = {}

# Типы SQL.
SQL_TYPES = [
    'TEXT',
    'DATE',
    'DATETIME',
    'INTEGER',
    'BIGINT',
    'UNSIGNED_BIGINT',
    'DOUBLE',
    'BLOB',
]

# Функции, которые нам не нужны.
DUMMY_FUNCTIONS = [
    'ForeignKey',
    'attributes',
    'description',
    'examples',
    'implementation',
    'fuzz_paths',
    'WINDOWS',
    'POSIX',
    'LINUX',
    'DARWIN',
]


RESERVED_KEYWORDS = [
    'table',
    'set',
]


def table_name(name, aliases=None):
    current_spec['name'] = name
    current_spec['aliases'] = aliases


def Column(name, col_type, *args, **kwargs):
    if name in RESERVED_KEYWORDS:
        name = '"%s"' % name
    return (name, col_type)


def schema(schema):
    # Отфильтровываем элементы None, обычно появляющиеся из ForeignKey.
    real_schema = [x for x in schema if x is not None]
    current_spec['schema'] = real_schema

def extended_schema(macro, schema):
    # Отфильтровываем элементы None, обычно появляющиеся из ForeignKey.
    real_schema = [x for x in schema if x is not None]
    current_spec.setdefault('extended_schema', []).extend(real_schema)

def extract_schema(filename):
    namespace = {
        'Column': Column,
        'schema': schema,
        'table_name': table_name,
        'extended_schema': extended_schema,
        'current_spec': {},
    }

    for fn in DUMMY_FUNCTIONS:
        namespace[fn] = lambda *args, **kwargs: None

    for ty in SQL_TYPES:
        namespace[ty] = ty

    with open(filename, 'rU') as f:
        tree = ast.parse(f.read())
        exec(compile(tree, '<string>', 'exec'), namespace)

    columns = ', '.join('%s %s' % (x[0], x[1]) for x in current_spec['schema'])
    statements = []
    statements = []
    statements.append('CREATE TABLE %s (%s);' % (current_spec['name'], columns))
    if 'extended_schema' in current_spec:
        statement = 'ALTER TABLE %s ADD %%s %%s;' % (current_spec['name'], )
        for column_name, column_definition in current_spec['extended_schema']:
            statements.append(statement % (column_name, column_definition))
        del current_spec['extended_schema']
    return '\n'.join(statements)


if __name__ == '__main__':
    import sys
    print(extract_schema(sys.argv[1]))
