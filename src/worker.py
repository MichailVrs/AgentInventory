# -*- coding: utf-8 -*-
from application import create_app
from settings import Config
from tasks import celery  # noqa


app = create_app(config=Config)
