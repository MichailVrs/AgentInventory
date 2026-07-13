# -*- coding: utf-8 -*-
import unittest
import json
import os
from unittest.mock import patch
from application import create_app
from database import db
from models import Node, Tag, StatusLog
from settings import TestConfig

# Определяем URI базы данных из окружения или используем локальную тестовую конфигурацию.
db_host = os.environ.get('POSTGRES_HOST', 'db')
db_port = os.environ.get('POSTGRES_PORT', '5432')
db_user = os.environ.get('POSTGRES_USER', 'inventory')
db_pass = os.environ.get('POSTGRES_PASSWORD', '123456')
db_name = os.environ.get('POSTGRES_TEST_DATABASE', 'inventory_test')

env_uri = os.environ.get('TEST_SQLALCHEMY_DATABASE_URI')
if env_uri:
    db_uri = env_uri
else:
    db_uri = f'postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}'

# Проверка безопасности: имя базы должно содержать 'test', чтобы не удалить общую БД.
if 'test' not in db_uri.split('/')[-1].lower():
    raise ValueError(
        f"Safety check failed: SQLALCHEMY_DATABASE_URI '{db_uri}' "
        "does not appear to be a test database. The database name must contain 'test'."
    )

class TestAPIConfig(TestConfig):
    SQLALCHEMY_DATABASE_URI = db_uri
    WTF_CSRF_ENABLED = False
    ENROLL_SECRET = 'secret'
    
    # Конфигурация eager-режима Celery.
    CELERY_ALWAYS_EAGER = True
    CELERY_TASK_ALWAYS_EAGER = True
    task_always_eager = True

class APISmokeTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestAPIConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Инициализируем изолированные таблицы тестовой базы данных.
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_enroll_success(self):
        # Проверяем регистрацию с корректным секретом.
        payload = {
            'enroll_secret': 'secret',
            'host_identifier': 'test-node-uuid-1'
        }
        response = self.client.post('/enroll', 
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('node_key', data)
        self.assertFalse(data['node_invalid'])
        
        # Проверяем, что узел создан в базе данных.
        node = Node.query.filter_by(host_identifier='test-node-uuid-1').first()
        self.assertIsNotNone(node)
        self.assertEqual(node.node_key, data['node_key'])

    def test_enroll_invalid_secret(self):
        payload = {
            'enroll_secret': 'wrong_secret',
            'host_identifier': 'test-node-uuid-2'
        }
        response = self.client.post('/enroll', 
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertTrue(data['node_invalid'])

    def test_enroll_empty_json(self):
        # Проверяем, что пустой или некорректный JSON возвращает пустую строку со статусом 200.
        response = self.client.post('/enroll', 
                                    data='',
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode('utf-8'), '')

    def test_log_status_and_result(self):
        # Сначала регистрируем узел, чтобы получить node_key.
        payload = {
            'enroll_secret': 'secret',
            'host_identifier': 'test-node-uuid-3'
        }
        response = self.client.post('/enroll', 
                                    data=json.dumps(payload),
                                    content_type='application/json')
        node_key = json.loads(response.data.decode('utf-8'))['node_key']

        # Проверяем отправку лога состояния.
        status_payload = {
            'node_key': node_key,
            'log_type': 'status',
            'data': [
                {
                    'severity': '0',
                    'filename': 'test.cpp',
                    'line': '42',
                    'message': 'Test status message',
                    'version': '1.0',
                    'calendarTime': 'Wed Jun 10 14:00:00 2026',
                    'unixTime': 1781090400
                }
            ]
        }
        response = self.client.post('/log',
                                    data=json.dumps(status_payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)

        # Проверяем отправку лога результата, запускающую нормализацию/EAV.
        with patch('tasks.normalize_to_cmdb.delay') as mock_normalize, \
             patch('tasks.analyze_result.delay'), \
             patch('tasks.learn_from_result.delay'):
             
            result_payload = {
                'node_key': node_key,
                'log_type': 'result',
                'data': [
                    {
                        'name': 'pack/cmdb_full/cmdb_os_info',
                        'action': 'added',
                        'columns': {
                            'os_name': 'Ubuntu',
                            'os_version': '22.04'
                        },
                        'calendarTime': 'Wed Jun 10 14:00:00 2026 UTC',
                        'unixTime': 1781090400
                    }
                ]
            }
            response = self.client.post('/log',
                                        data=json.dumps(result_payload),
                                        content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(mock_normalize.called)

    def test_delete_distributed_task(self):
        from models import DistributedQuery, DistributedQueryTask
        
        # Обходим обязательный вход в тестовом режиме.
        self.app.config['LOGIN_DISABLED'] = True
        
        # Создаем тестовый узел.
        node = Node.create(host_identifier='test-delete-task-node')
        
        # Создаем тестовый оперативный запрос.
        dq = DistributedQuery.create(sql='select 1;', description='test')
        
        # Создаем задачу оперативного запроса.
        task = DistributedQueryTask.create(node=node, distributed_query=dq)
        task_id = task.id
        
        # Проверяем, что она существует в базе данных.
        self.assertIsNotNone(DistributedQueryTask.query.get(task_id))
        
        # Выполняем запрос на удаление.
        response = self.client.delete(f'/manage/distributed_task/{task_id}')
        self.assertEqual(response.status_code, 204)
        
        # Проверяем, что она успешно удалена из базы данных.
        self.assertIsNone(DistributedQueryTask.query.get(task_id))

if __name__ == '__main__':
    unittest.main()
