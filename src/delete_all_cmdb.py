import sys
from database import db
from models import Pack, Query
from application import create_app
from settings import Config

app = create_app(Config)
with app.app_context():
    packs = Pack.query.filter(Pack.name.like('%cmdb%')).all()
    for p in packs:
        db.session.delete(p)
        print(f"Deleted pack: {p.name}")
        
    queries = Query.query.filter(Query.name.like('%cmdb%')).all()
    for q in queries:
        db.session.delete(q)
        print(f"Deleted query: {q.name}")
            
    db.session.commit()
    print("Database committed. All cmdb packs and queries removed.")
