# -*- coding: utf-8 -*-
import sys
import datetime as dt
from database import db
from models import Node, ResultLog, StatusLog, DistributedQueryTask, DistributedQuery, DistributedQueryResult, CmdbObject, CmdbValue
from application import create_app
from settings import Config

app = create_app(Config)
with app.app_context():
    # Граница оффлайна: checkin старше 1 часа или last_checkin равен None.
    cutoff = dt.datetime.utcnow() - dt.timedelta(hours=1)
    
    # Ищем узлы, у которых last_checkin раньше границы или равен None.
    offline_nodes = Node.query.filter((Node.last_checkin == None) | (Node.last_checkin < cutoff)).all()
    
    if not offline_nodes:
        print("No offline nodes found to clean up.")
        sys.exit(0)
        
    print(f"Found {len(offline_nodes)} offline nodes to clean up.")
    
    for node in offline_nodes:
        print(f"Purging offline node: {node.host_identifier} ({node.last_ip})")
        
        # 1. Удаляем связанные объекты и значения CMDB.
        cmdb_objs = CmdbObject.query.filter_by(node_id=node.id).all()
        for co in cmdb_objs:
            db.session.delete(co)
            
        # 2. Удаляем логи результатов.
        ResultLog.query.filter_by(node_id=node.id).delete(synchronize_session=False)
        
        # 3. Удаляем логи состояния.
        StatusLog.query.filter_by(node_id=node.id).delete(synchronize_session=False)
        
        # 4. Удаляем задачи оперативных запросов (результаты удаляются каскадно).
        tasks = DistributedQueryTask.query.filter_by(node_id=node.id).all()
        for task in tasks:
            db.session.delete(task)
            
        # 5. Удаляем связи с тегами.
        node.tags = []
        
        # 6. Удаляем сам узел.
        db.session.delete(node)
        
    db.session.commit()
    print("Database committed successfully. All offline nodes have been completely purged.")
