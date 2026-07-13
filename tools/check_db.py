import sys
from database import db
from models import Node, Pack, Query, ResultLog, CmdbObject
from application import create_app
from settings import Config

app = create_app(Config)
with app.app_context():
    packs = Pack.query.all()
    print("=== Packs ===")
    for p in packs:
        print("Pack: {}, Queries: {}".format(p.name, [q.name for q in p.queries]))
    
    print("\n=== CMDB Objects ===")
    cmdb_objs = CmdbObject.query.all()
    print("Total CMDB Objects: {}".format(len(cmdb_objs)))
    for obj in cmdb_objs[:5]:
        print("Type: {}, Node: {}".format(obj.object_type, obj.node_id))

    print("\n=== Recent Result Logs ===")
    logs = ResultLog.query.order_by(ResultLog.id.desc()).limit(10).all()
    for log in logs:
        print("Log: {}, Action: {}, Node: {}".format(log.name, log.action, log.node_id))

    print("\n=== Nodes ===")
    for n in Node.query.all():
        print("Node: {}, Last Checkin: {}".format(n.host_identifier, n.last_checkin))
