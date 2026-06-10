# -*- coding: utf-8 -*-
import sys
import datetime as dt
from database import db
from models import Node, ResultLog, StatusLog, DistributedQueryTask, DistributedQuery, DistributedQueryResult, CmdbObject, CmdbValue
from application import create_app
from settings import Config

app = create_app(Config)
with app.app_context():
    # Cutoff for offline: checkin older than 1 hour or last_checkin is None
    cutoff = dt.datetime.utcnow() - dt.timedelta(hours=1)
    
    # We want to find nodes that have last_checkin before cutoff or last_checkin is None
    offline_nodes = Node.query.filter((Node.last_checkin == None) | (Node.last_checkin < cutoff)).all()
    
    if not offline_nodes:
        print("No offline nodes found to clean up.")
        sys.exit(0)
        
    print(f"Found {len(offline_nodes)} offline nodes to clean up.")
    
    for node in offline_nodes:
        print(f"Purging offline node: {node.host_identifier} ({node.last_ip})")
        
        # 1. Delete associated CMDB objects and values
        cmdb_objs = CmdbObject.query.filter_by(node_id=node.id).all()
        for co in cmdb_objs:
            db.session.delete(co)
            
        # 2. Delete result logs
        ResultLog.query.filter_by(node_id=node.id).delete(synchronize_session=False)
        
        # 3. Delete status logs
        StatusLog.query.filter_by(node_id=node.id).delete(synchronize_session=False)
        
        # 4. Delete distributed query tasks (cascades automatically to results!)
        tasks = DistributedQueryTask.query.filter_by(node_id=node.id).all()
        for task in tasks:
            db.session.delete(task)
            
        # 5. Remove tag associations
        node.tags = []
        
        # 6. Delete the node itself
        db.session.delete(node)
        
    db.session.commit()
    print("Database committed successfully. All offline nodes have been completely purged.")
