# -*- coding: utf-8 -*-
from collections import namedtuple
from os.path import basename, splitext
import json


UploadedQuery = namedtuple(
    'UploadedQuery',
    [
        'name',
        'sql',
        'interval',
        'platform',
        'version',
        'description',
        'value',
        'removed',
        'shard',
    ]
)


class UploadQueryError(ValueError):
    def __init__(self, code):
        super(UploadQueryError, self).__init__(code)
        self.code = code


CYRILLIC_MAP = {
    u'\xe0': 'a', u'\xe1': 'b', u'\xe2': 'v', u'\xe3': 'g', u'\xe4': 'd',
    u'\xe5': 'e', u'\xb8': 'yo', u'\xe6': 'zh', u'\xe7': 'z', u'\xe8': 'i',
    u'\xe9': 'y', u'\xea': 'k', u'\xeb': 'l', u'\xec': 'm', u'\xed': 'n',
    u'\xee': 'o', u'\xef': 'p', u'\xf0': 'r', u'\xf1': 's', u'\xf2': 't',
    u'\xf3': 'u', u'\xf4': 'f', u'\xf5': 'kh', u'\xf6': 'ts', u'\xf7': 'ch',
    u'\xf8': 'sh', u'\xf9': 'shch', u'\xfa': '', u'\xfb': 'y',
    u'\xfc': '', u'\xfd': 'e', u'\xfe': 'yu', u'\xff': 'ya',
    u'\xc0': 'a', u'\xc1': 'b', u'\xc2': 'v', u'\xc3': 'g', u'\xc4': 'd',
    u'\xc5': 'e', u'\xa8': 'yo', u'\xc6': 'zh', u'\xc7': 'z', u'\xc8': 'i',
    u'\xc9': 'y', u'\xca': 'k', u'\xcb': 'l', u'\xcc': 'm', u'\xcd': 'n',
    u'\xce': 'o', u'\xcf': 'p', u'\xd0': 'r', u'\xd1': 's', u'\xd2': 't',
    u'\xd3': 'u', u'\xd4': 'f', u'\xd5': 'kh', u'\xd6': 'ts', u'\xd7': 'ch',
    u'\xd8': 'sh', u'\xd9': 'shch', u'\xda': '', u'\xdb': 'y',
    u'\xdc': '', u'\xdd': 'e', u'\xde': 'yu', u'\xdf': 'ya',
    u'\u0430': 'a', u'\u0431': 'b', u'\u0432': 'v', u'\u0433': 'g', u'\u0434': 'd',
    u'\u0435': 'e', u'\u0451': 'yo', u'\u0436': 'zh', u'\u0437': 'z',
    u'\u0438': 'i', u'\u0439': 'y', u'\u043a': 'k', u'\u043b': 'l',
    u'\u043c': 'm', u'\u043d': 'n', u'\u043e': 'o', u'\u043f': 'p',
    u'\u0440': 'r', u'\u0441': 's', u'\u0442': 't', u'\u0443': 'u',
    u'\u0444': 'f', u'\u0445': 'kh', u'\u0446': 'ts', u'\u0447': 'ch',
    u'\u0448': 'sh', u'\u0449': 'shch', u'\u044a': '', u'\u044b': 'y',
    u'\u044c': '', u'\u044d': 'e', u'\u044e': 'yu', u'\u044f': 'ya',
    u'\u0410': 'a', u'\u0411': 'b', u'\u0412': 'v', u'\u0413': 'g', u'\u0414': 'd',
    u'\u0415': 'e', u'\u0401': 'yo', u'\u0416': 'zh', u'\u0417': 'z',
    u'\u0418': 'i', u'\u0419': 'y', u'\u041a': 'k', u'\u041b': 'l',
    u'\u041c': 'm', u'\u041d': 'n', u'\u041e': 'o', u'\u041f': 'p',
    u'\u0420': 'r', u'\u0421': 's', u'\u0422': 't', u'\u0423': 'u',
    u'\u0424': 'f', u'\u0425': 'kh', u'\u0426': 'ts', u'\u0427': 'ch',
    u'\u0428': 'sh', u'\u0429': 'shch', u'\u042a': '', u'\u042b': 'y',
    u'\u042c': '', u'\u042d': 'e', u'\u042e': 'yu', u'\u042f': 'ya',
}


def slugify_cyrillic(text):
    result = []
    for char in text:
        if char in CYRILLIC_MAP:
            result.append(CYRILLIC_MAP[char])
        elif char.isalnum() or char == '_':
            result.append(char.lower())
        elif char.isspace() or char == '-':
            result.append('_')

    slug = ''.join(result)
    while '__' in slug:
        slug = slug.replace('__', '_')
    slug = slug.strip('_')
    if not slug.startswith('cmdb_'):
        slug = 'cmdb_' + slug
    return slug


def parse_uploaded_query(file_data):
    filename = file_data.filename
    body = file_data.read()
    if isinstance(body, bytes):
        body = body.decode('utf-8')

    name = None
    sql = None
    description = ''
    interval = 3600
    platform = 'all'
    version = ''
    value = ''
    removed = False
    shard = None

    if filename.endswith('.json'):
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise UploadQueryError('invalid_json_structure')

            name = data.get('name') or slugify_cyrillic(splitext(basename(filename))[0])
            sql = data.get('query') or data.get('sql')
            if 'description' in data:
                description = data['description']
            if 'interval' in data:
                interval = int(data['interval'])
            if 'platform' in data:
                platform = data['platform']
            if 'version' in data:
                version = data['version']
            if 'value' in data:
                value = data['value']
            if 'removed' in data:
                removed = bool(data['removed'])
            if 'shard' in data:
                shard = int(data['shard']) if data['shard'] is not None else None
        except UploadQueryError:
            raise
        except ValueError:
            raise UploadQueryError('json_decode_error')
    elif filename.endswith('.sql'):
        name = slugify_cyrillic(splitext(basename(filename))[0])
        sql = body.strip()
    else:
        raise UploadQueryError('unsupported_format')

    if not sql:
        raise UploadQueryError('missing_sql')

    return UploadedQuery(
        name=name,
        sql=sql,
        interval=interval,
        platform=platform,
        version=version,
        description=description,
        value=value,
        removed=removed,
        shard=shard,
    )

