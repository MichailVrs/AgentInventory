import sys
from database import db
from models import Node
from application import create_app
from settings import Config
import json

app = create_app(Config)
with app.app_context():
    node = Node.query.filter_by(host_identifier='Windows-Agent-1').first()
    if not node:
        print("Node not found")
        sys.exit(1)
    
    from utils import assemble_configuration
    config = assemble_configuration(node)
    print(json.dumps(config, indent=2))
