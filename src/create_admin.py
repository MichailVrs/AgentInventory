import sys
sys.path.append('/src')
from application import create_app
from settings import Config
from models import User

app = create_app(Config)
with app.app_context():
    u = User.query.filter_by(username='admin').first()
    if u:
        u.set_password('password')
        u.save()
        print('Password for admin reset and hashed to: password')
    else:
        User.create(username='admin', password='password', email='admin@example.com')
        print('Admin user created with password: password')
