import sys
from database import db
from models import Node, ResultLog
from application import create_app
from settings import Config

app = create_app(Config)
with app.app_context():
    print(f"Total ResultLogs: {ResultLog.query.count()}")
    for r in ResultLog.query.order_by(ResultLog.id.desc()).limit(10).all():
        print(f"Result: {r.name}, Action: {r.action}, Node: {r.node_id}")
