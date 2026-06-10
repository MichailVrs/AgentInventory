import sys
from doorman.database import db
from doorman.models import Node, Pack, Query, ResultLog, CmdbObject
from manage import create_app

app = create_app()
with app.app_context():
    packs = Pack.query.all()
    print("=== Packs ===")
    for p in packs:
        print(f"Pack: {p.name}, Queries: {[q.name for q in p.queries]}")
    
    print("\n=== CMDB Objects ===")
    cmdb_objs = CmdbObject.query.all()
    print(f"Total CMDB Objects: {len(cmdb_objs)}")
    for obj in cmdb_objs[:5]:
        print(f"Type: {obj.object_type}, Node: {obj.node_id}")

    print("\n=== Recent Result Logs (cmdb_) ===")
    logs = ResultLog.query.filter(ResultLog.name.like('pack_cmdb_%')).order_by(ResultLog.id.desc()).limit(5).all()
    for log in logs:
        print(f"Log: {log.name}, Action: {log.action}, Node: {log.node_id}")
