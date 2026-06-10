import sys
from database import db
from models import Pack, Query
from application import create_app
from settings import Config

app = create_app(Config)
with app.app_context():
    pack = Pack.query.filter_by(name='pack_cmdb_inventory').first()
    if pack:
        db.session.delete(pack)
        print("Deleted pack: pack_cmdb_inventory")
        
    for qname in ['cmdb_system_info', 'cmdb_os_version', 'cmdb_storage_mounts', 'cmdb_local_users']:
        q = Query.query.filter_by(name=qname).first()
        if q:
            db.session.delete(q)
            print(f"Deleted query: {qname}")
            
    db.session.commit()
    print("Database committed. Pack and queries removed.")
