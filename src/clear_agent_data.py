# -*- coding: utf-8 -*-
from database import db
from models import (
    ResultLog, 
    StatusLog, 
    DistributedQueryResult, 
    DistributedQueryTask, 
    DistributedQuery, 
    CmdbValue, 
    CmdbObject,
    Node
)
from application import create_app
from settings import Config

app = create_app(Config)
with app.app_context():
    print("=== Clearing all data collected from agents ===")
    
    # 1. Очищаем ResultLog.
    print("Clearing ResultLog...")
    num_results = ResultLog.query.delete()
    
    # 2. Очищаем StatusLog.
    print("Clearing StatusLog...")
    num_status = StatusLog.query.delete()
    
    # 3. Очищаем DistributedQueryResult.
    print("Clearing DistributedQueryResult...")
    num_dist_res = DistributedQueryResult.query.delete()
    
    # 4. Очищаем DistributedQueryTask.
    print("Clearing DistributedQueryTask...")
    num_dist_task = DistributedQueryTask.query.delete()

    # 5. Очищаем DistributedQuery.
    print("Clearing DistributedQuery...")
    num_dist_q = DistributedQuery.query.delete()
    
    # 6. Очищаем CmdbValue.
    print("Clearing CmdbValue...")
    num_values = CmdbValue.query.delete()
    
    # 7. Очищаем CmdbObject.
    print("Clearing CmdbObject...")
    num_objects = CmdbObject.query.delete()

    # 8. Очищаем кэшированные поля инвентаризации узла, полученные из результатов агента.
    print("Clearing Node.node_info...")
    num_node_info = Node.query.update({Node.node_info: {}}, synchronize_session=False)
    
    db.session.commit()
    print("=== Data cleanup successfully finished! ===")
    print(f"ResultLogs deleted: {num_results}")
    print(f"StatusLogs deleted: {num_status}")
    print(f"DistributedQueryResults deleted: {num_dist_res}")
    print(f"DistributedQueryTasks deleted: {num_dist_task}")
    print(f"DistributedQueries deleted: {num_dist_q}")
    print(f"CmdbValues deleted: {num_values}")
    print(f"CmdbObjects deleted: {num_objects}")
    print(f"Node info cleared: {num_node_info}")
