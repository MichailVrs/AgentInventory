import sys
from database import db
from models import Pack, Query
from application import create_app
from settings import Config

app = create_app(Config)
with app.app_context():
    pack = Pack.query.filter_by(name='pack_cmdb_inventory').first()
    if pack:
        print(f"Pack tags: {[t.value for t in pack.tags]}")
    else:
        print("Pack not found")
        
    for qname in ['cmdb_system_info', 'cmdb_os_version', 'cmdb_storage_mounts', 'cmdb_local_users']:
        q = Query.query.filter_by(name=qname).first()
        if q:
            print(f"Query {qname} tags: {[t.value for t in q.tags]}")
        else:
            print(f"Query {qname} not found")
