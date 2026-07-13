import sys
from database import db
from models import Node, Tag
from application import create_app
from settings import Config

app = create_app(Config)
with app.app_context():
    tag = Tag.query.filter_by(value='метка 1').first()
    if tag:
        print(f"Nodes with tag 'метка 1':")
        for n in tag.nodes:
            print(f"- {n.host_identifier} (Last checkin: {n.last_checkin})")
    else:
        print("Tag 'метка 1' not found")
