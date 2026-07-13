import os
import sys
sys.path.append('/src')
from application import create_app
from settings import Config
from models import User

app = create_app(Config)
with app.app_context():
    password = os.environ.get('ADMIN_PASSWORD')
    if not password:
        try:
            if sys.stdin.isatty():
                import getpass
                password = getpass.getpass('Введите пароль администратора: ')
            else:
                # Fallback to reading from stdin in case of non-interactive pipelines
                password = sys.stdin.readline().strip()
        except Exception:
            pass

    if not password:
        print("Ошибка: Переменная окружения ADMIN_PASSWORD не задана, и интерактивный ввод недоступен.")
        sys.exit(1)

    u = User.query.filter_by(username='admin').first()
    if u:
        u.set_password(password)
        u.save()
        print('Пароль администратора (admin) успешно обновлен.')
    else:
        User.create(username='admin', password=password, email='admin@example.com')
        print('Администратор (admin) успешно создан.')
