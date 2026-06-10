# -*- coding: utf-8 -*-
from flask_assets import Bundle, Environment
import os
# Абсолютный путь внутри контейнера (адаптируйте под ваш WORKDIR)
os.environ['LESS_BIN'] = '/src/node_modules/.bin/lessc'

css = Bundle(
    'libs/bootstrap/dist/css/bootstrap.min.css',
    'libs/bootstrap-tagsinput/dist/bootstrap-tagsinput.css',
    'libs/bootstrap-vertical-tabs/bootstrap.vertical-tabs.css',
    'libs/jQuery-QueryBuilder/dist/css/query-builder.default.css',
    'css/yeti.min.css',
    'css/style.css',
    # filters='cssmin',
    output='public/css/common.css',
)

js = Bundle(
    'libs/jQuery/dist/jquery.js',
    'libs/bootstrap/dist/js/bootstrap.js',
    'libs/bootstrap-tagsinput/dist/bootstrap-tagsinput.js',
    # 'libs/jquery-extendext/jQuery.extendext.js',
    'libs/jQuery-QueryBuilder/dist/js/query-builder.standalone.js',
    'libs/interact/dist/interact.js',
    'js/plugins.js',
    # filters='jsmin',
    output='public/js/common.js',
)

assets = Environment()

assets.register('js_all', js)
assets.register('css_all', css)
