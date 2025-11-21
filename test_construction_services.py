import pytest
import json
import uuid
import os
from datetime import datetime, timedelta

# Тестовые данные
TEST_USERS = {
    'engineer': {'email': 'engineer@system.com', 'password': 'engineer123'},
    'manager': {'email': 'manager@system.com', 'password': 'manager123'},
    'admin': {'email': 'admin@system.com', 'password': 'admin123'}
}

class TestConstructionServices:
    """Класс тестов для системы управления строительными сервисами"""
    
    @pytest.fixture
    def users_client(self):
        from service_users.app import app as users_app, init_db
        users_app.config['TESTING'] = True
        users_app.config['DATABASE'] = 'test_users.db'  # Используем тестовую БД
        
        # Удаляем тестовую БД если существует
        if os.path.exists('test_users.db'):
            os.remove('test_users.db')
            
        with users_app.test_client() as client:
            # Инициализируем БД внутри контекста приложения
            with users_app.app_context():
                init_db()
            yield client
        
        # Очистка после тестов
        if os.path.exists('test_users.db'):
            os.remove('test_users.db')
    
    @pytest.fixture
    def orders_client(self):
        from service_orders.app import app as orders_app, init_db
        orders_app.config['TESTING'] = True
        orders_app.config['DATABASE'] = 'test_orders.db'  # Используем тестовую БД
        
        # Удаляем тестовую БД если существует
        if os.path.exists('test_orders.db'):
            os.remove('test_orders.db')
            
        with orders_app.test_client() as client:
            # Инициализируем БД внутри контекста приложения
            with orders_app.app_context():
                init_db()
            yield client
        
        # Очистка после тестов
        if os.path.exists('test_orders.db'):
            os.remove('test_orders.db')
    
    @pytest.fixture
    def tasks_client(self):
        from service_tasks.app import app as tasks_app, init_db
        tasks_app.config['TESTING'] = True
        tasks_app.config['DATABASE'] = 'test_tasks.db'  # Используем тестовую БД
        
        # Удаляем тестовую БД если существует
        if os.path.exists('test_tasks.db'):
            os.remove('test_tasks.db')
            
        with tasks_app.test_client() as client:
            # Инициализируем БД внутри контекста приложения
            with tasks_app.app_context():
                init_db()
            yield client
        
        # Очистка после тестов
        if os.path.exists('test_tasks.db'):
            os.remove('test_tasks.db')

    # 1. Тест регистрации нового пользователя
    def test_user_registration_success(self, users_client):
        """Тест успешной регистрации пользователя"""
        user_data = {
            'email': f'test_{uuid.uuid4().hex[:8]}@example.com',
            'password': 'test123',
            'name': 'Test User',
            'role': 'engineer'
        }
        response = users_client.post('/v1/auth/register', 
                                   json=user_data,
                                   content_type='application/json')
        data = json.loads(response.data)
        
        assert response.status_code == 201
        assert data['success'] == True
        assert 'token' in data['data']
        assert data['data']['user']['email'] == user_data['email']
        assert data['data']['user']['role'] == 'engineer'
    
    # 2. Тест регистрации с существующим email
    def test_user_registration_duplicate_email(self, users_client):
        """Тест регистрации с уже существующим email"""
        user_data = {
            'email': 'engineer@system.com',  # Этот email уже есть в демо-данных
            'password': 'test123',
            'name': 'Test User'
        }
        response = users_client.post('/v1/auth/register', json=user_data)
        data = json.loads(response.data)
        
        assert response.status_code == 409
        assert data['success'] == False
        assert data['error']['code'] == 'USER_EXISTS'
    
    # 3. Тест входа с правильными учетными данными
    def test_user_login_success(self, users_client):
        """Тест успешного входа в систему"""
        login_data = {
            'email': 'engineer@system.com',
            'password': 'engineer123'
        }
        response = users_client.post('/v1/auth/login', json=login_data)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] == True
        assert 'token' in data['data']
        assert data['data']['user']['role'] == 'engineer'
        assert data['data']['user']['email'] == 'engineer@system.com'
    
    # 4. Тест входа с неправильным паролем
    def test_user_login_wrong_password(self, users_client):
        """Тест входа с неверным паролем"""
        login_data = {
            'email': 'engineer@system.com',
            'password': 'wrongpassword'
        }
        response = users_client.post('/v1/auth/login', json=login_data)
        data = json.loads(response.data)
        
        assert response.status_code == 401
        assert data['success'] == False
        assert data['error']['code'] == 'INVALID_CREDENTIALS'
    
    # 5. Тест получения списка пользователей
    def test_get_users_list(self, users_client):
        """Тест получения списка всех пользователей"""
        response = users_client.get('/v1/users')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] == True
        assert 'users' in data['data']
        assert len(data['data']['users']) >= 4  # Должны быть как минимум 4 дефолтных пользователя
    
    # 6. Тест создания нового заказа
    def test_create_order_success(self, orders_client):
        """Тест успешного создания заказа"""
        order_data = {
            'title': 'Тестовый заказ строительных материалов',
            'description': 'Тестовое описание заказа',
            'items': [
                {
                    'product': 'Цемент М500',
                    'quantity': 100,
                    'unit_price': 500
                },
                {
                    'product': 'Песок',
                    'quantity': 50,
                    'unit_price': 1000
                }
            ]
        }
        headers = {
            'X-User-ID': 'test-user-id-123',
            'X-User-Role': 'engineer',
            'X-Request-ID': 'test-request-1'
        }
        response = orders_client.post('/v1/orders', 
                                    json=order_data,
                                    headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 201
        assert data['success'] == True
        assert 'order_id' in data['data']
        assert data['data']['total_amount'] == 100000  # 100*500 + 50*1000
    
    # 7. Тест создания заказа без заголовка
    def test_create_order_without_title(self, orders_client):
        """Тест создания заказа без обязательного поля title"""
        order_data = {
            'description': 'Тестовое описание без заголовка',
            'items': [{'product': 'Test', 'quantity': 1, 'unit_price': 100}]
        }
        headers = {
            'X-User-ID': 'test-user',
            'X-User-Role': 'engineer'
        }
        response = orders_client.post('/v1/orders', json=order_data, headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert data['success'] == False
        assert data['error']['code'] == 'VALIDATION_ERROR'
    
    # 8. Тест получения списка заказов
    def test_get_orders_list(self, orders_client):
        """Тест получения списка заказов с пагинацией"""
        headers = {
            'X-User-ID': 'test-user',
            'X-User-Role': 'engineer'
        }
        response = orders_client.get('/v1/orders', headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] == True
        assert 'orders' in data['data']
        assert 'pagination' in data['data']
        assert data['data']['pagination']['page'] == 1
        assert data['data']['pagination']['limit'] == 10
    
    # 9. Тест получения конкретного заказа
    def test_get_specific_order(self, orders_client):
        """Тест получения информации о конкретном заказе"""
        # Сначала создаем заказ
        order_data = {
            'title': 'Заказ для теста получения',
            'items': [{'product': 'Тестовый продукт', 'quantity': 5, 'unit_price': 200}]
        }
        headers = {
            'X-User-ID': 'test-user-specific',
            'X-User-Role': 'engineer'
        }
        create_response = orders_client.post('/v1/orders', json=order_data, headers=headers)
        order_id = json.loads(create_response.data)['data']['order_id']
        
        # Получаем созданный заказ
        response = orders_client.get(f'/v1/orders/{order_id}', headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] == True
        assert data['data']['id'] == order_id
        assert data['data']['title'] == 'Заказ для теста получения'
        assert data['data']['total_amount'] == 1000
    
    # 10. Тест обновления заказа
    def test_update_order(self, orders_client):
        """Тест обновления информации о заказе"""
        # Создаем заказ
        order_data = {
            'title': 'Заказ для обновления',
            'items': [{'product': 'Test', 'quantity': 1, 'unit_price': 100}]
        }
        headers = {
            'X-User-ID': 'test-user-update',
            'X-User-Role': 'engineer'
        }
        create_response = orders_client.post('/v1/orders', json=order_data, headers=headers)
        order_id = json.loads(create_response.data)['data']['order_id']
        
        # Обновляем заказ
        update_data = {
            'title': 'Обновленный заголовок заказа',
            'status': 'in_progress',
            'description': 'Обновленное описание'
        }
        response = orders_client.put(f'/v1/orders/{order_id}', json=update_data, headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] == True
        assert data['data']['message'] == 'Order updated successfully'
    
    # 11. Тест отмены заказа
    def test_cancel_order(self, orders_client):
        """Тест отмены заказа"""
        # Создаем заказ
        order_data = {
            'title': 'Заказ для отмены',
            'items': [{'product': 'Test Product', 'quantity': 2, 'unit_price': 150}]
        }
        headers = {
            'X-User-ID': 'test-user-cancel',
            'X-User-Role': 'engineer'
        }
        create_response = orders_client.post('/v1/orders', json=order_data, headers=headers)
        order_id = json.loads(create_response.data)['data']['order_id']
        
        # Отменяем заказ
        response = orders_client.post(f'/v1/orders/{order_id}/cancel', headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] == True
        assert data['data']['message'] == 'Order cancelled successfully'
    
    # 12. Тест создания дефекта
    def test_create_defect(self, tasks_client):
        """Тест создания дефекта"""
        defect_data = {
            'title': 'Трещина в стене здания',
            'description': 'Обнаружена вертикальная трещина в несущей стене',
            'severity': 'high'
        }
        headers = {
            'X-User-ID': 'engineer@system.com',
            'X-Request-ID': 'test-defect-1'
        }
        response = tasks_client.post('/v1/defects', json=defect_data, headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 201
        assert data['success'] == True
        assert 'defect_id' in data['data']
    
    # 13. Тест получения списка дефектов
    def test_get_defects(self, tasks_client):
        """Тест получения списка всех дефектов"""
        response = tasks_client.get('/v1/defects')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] == True
        assert 'defects' in data['data']
        assert len(data['data']['defects']) > 0
    
    # 14. Тест создания задачи
    def test_create_task(self, tasks_client):
        """Тест создания задачи"""
        task_data = {
            'title': 'Устранение протечки кровли',
            'description': 'Необходимо устранить протечку в центральной части кровли',
            'priority': 'high',
            'assigned_to': 'engineer@system.com',
            'due_date': '2024-12-31'
        }
        headers = {
            'X-User-ID': 'manager@system.com'
        }
        response = tasks_client.post('/v1/tasks', json=task_data, headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 201
        assert data['success'] == True
        assert 'task_id' in data['data']
    
    # 15. Тест обновления задачи
    def test_update_task(self, tasks_client):
        """Тест обновления информации о задаче"""
        # Сначала создаем задачу
        task_data = {
            'title': 'Задача для обновления',
            'description': 'Описание задачи',
            'priority': 'medium',
            'assigned_to': 'engineer@system.com'
        }
        headers = {
            'X-User-ID': 'manager@system.com'
        }
        create_response = tasks_client.post('/v1/tasks', json=task_data, headers=headers)
        task_id = json.loads(create_response.data)['data']['task_id']
        
        # Обновляем задачу
        update_data = {
            'status': 'in_progress',
            'priority': 'high',
            'description': 'Обновленное описание задачи'
        }
        response = tasks_client.put(f'/v1/tasks/{task_id}', json=update_data)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] == True
    
    # 16. Тест создания отчета
    def test_create_report(self, tasks_client):
        """Тест создания отчета"""
        report_data = {
            'title': 'Еженедельный отчет о работах',
            'content': 'За неделю выполнено 15 задач, открыто 2 новых дефекта',
            'report_type': 'progress'
        }
        headers = {
            'X-User-ID': 'manager@system.com'
        }
        response = tasks_client.post('/v1/reports', json=report_data, headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 201
        assert data['success'] == True
        assert 'report_id' in data['data']
    
    # 17. Тест генерации статистического отчета
    def test_generate_statistics_report(self, tasks_client):
        """Тест автоматической генерации статистического отчета"""
        report_data = {
            'title': 'Автоматический статистический отчет',
            'report_type': 'statistics'
        }
        headers = {
            'X-User-ID': 'manager@system.com'
        }
        response = tasks_client.post('/v1/reports/generate/statistics', 
                                   json=report_data, headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 201
        assert data['success'] == True
        assert 'report_id' in data['data']
    
    # 18. Тест получения статистики
    def test_get_statistics(self, tasks_client):
        """Тест получения статистики по задачам и дефектам"""
        response = tasks_client.get('/v1/statistics')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] == True
        assert 'tasks_total' in data['data']
        assert 'defects_total' in data['data']
        assert 'tasks_completed' in data['data']
        assert 'defects_open' in data['data']
    
    # 19. Тест проверки здоровья сервисов
    def test_health_checks(self, users_client, orders_client, tasks_client):
        """Тест проверки работоспособности всех сервисов"""
        # Проверяем сервис пользователей
        response = users_client.get('/health')
        data = json.loads(response.data)
        assert response.status_code == 200
        assert data['status'] == 'healthy'
        assert data['service'] == 'users'
        
        # Проверяем сервис заказов
        response = orders_client.get('/health')
        data = json.loads(response.data)
        assert response.status_code == 200
        assert data['status'] == 'healthy'
        assert data['service'] == 'orders'
        
        # Проверяем сервис задач
        response = tasks_client.get('/health')
        data = json.loads(response.data)
        assert response.status_code == 200
        assert data['status'] == 'healthy'
        assert data['service'] == 'tasks'
    
    # 20. Тест пагинации в заказах
    def test_orders_pagination(self, orders_client):
        """Тест пагинации при получении списка заказов"""
        headers = {
            'X-User-ID': 'test-user-pagination',
            'X-User-Role': 'engineer'
        }
        response = orders_client.get('/v1/orders?page=2&limit=3', headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert 'pagination' in data['data']
        assert data['data']['pagination']['page'] == 2
        assert data['data']['pagination']['limit'] == 3
    
    # 21. Тест фильтрации заказов по статусу
    def test_orders_status_filter(self, orders_client):
        """Тест фильтрации заказов по статусу"""
        headers = {
            'X-User-ID': 'test-user',
            'X-User-Role': 'manager'  # Менеджер видит все заказы
        }
        response = orders_client.get('/v1/orders?status=completed', headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        # Проверяем, что все возвращенные заказы имеют статус 'completed'
        if data['data']['orders']:
            for order in data['data']['orders']:
                assert order['status'] == 'completed'
    
    # 22. Тест доступа к заказу другого пользователя
    def test_access_other_user_order(self, orders_client):
        """Тест попытки доступа к заказу другого пользователя"""
        # Создаем заказ от первого пользователя
        order_data = {
            'title': 'Приватный заказ пользователя 1',
            'items': [{'product': 'Private Item', 'quantity': 1, 'unit_price': 100}]
        }
        headers_user1 = {
            'X-User-ID': 'user-1-private',
            'X-User-Role': 'engineer'
        }
        create_response = orders_client.post('/v1/orders', json=order_data, headers=headers_user1)
        order_id = json.loads(create_response.data)['data']['order_id']
        
        # Пытаемся получить доступ от другого пользователя (не менеджера/админа)
        headers_user2 = {
            'X-User-ID': 'user-2-private',
            'X-User-Role': 'engineer'
        }
        response = orders_client.get(f'/v1/orders/{order_id}', headers=headers_user2)
        data = json.loads(response.data)
        
        assert response.status_code == 403
        assert data['success'] == False
        assert data['error']['code'] == 'FORBIDDEN'
    
    # 23. Тест создания заказа с невалидными items
    def test_create_order_invalid_items(self, orders_client):
        """Тест создания заказа с некорректными данными items"""
        order_data = {
            'title': 'Заказ с невалидными items',
            'items': [
                {
                    'product': 'Test Product',
                    'quantity': 1
                    # Отсутствует unit_price - должно вызвать ошибку
                }
            ]
        }
        headers = {
            'X-User-ID': 'test-user',
            'X-User-Role': 'engineer'
        }
        response = orders_client.post('/v1/orders', json=order_data, headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert data['success'] == False
        assert data['error']['code'] == 'VALIDATION_ERROR'
    
    # 24. Тест обновления дефекта
    def test_update_defect(self, tasks_client):
        """Тест обновления информации о дефекте"""
        # Сначала создаем дефект
        defect_data = {
            'title': 'Дефект для обновления',
            'description': 'Описание дефекта',
            'severity': 'medium'
        }
        headers = {
            'X-User-ID': 'engineer@system.com'
        }
        create_response = tasks_client.post('/v1/defects', json=defect_data, headers=headers)
        defect_id = json.loads(create_response.data)['data']['defect_id']
        
        # Обновляем дефект
        update_data = {
            'status': 'in_progress',
            'assigned_to': 'specialist@system.com',
            'severity': 'high'
        }
        response = tasks_client.put(f'/v1/defects/{defect_id}', json=update_data)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] == True
        assert data['data']['message'] == 'Defect updated successfully'
    
    # 25. Тест удаления отчета
    def test_delete_report(self, tasks_client):
        """Тест удаления отчета"""
        # Сначала создаем отчет
        report_data = {
            'title': 'Отчет для удаления',
            'content': 'Временный отчет, который будет удален',
            'report_type': 'general'
        }
        headers = {
            'X-User-ID': 'manager@system.com'
        }
        create_response = tasks_client.post('/v1/reports', json=report_data, headers=headers)
        report_id = json.loads(create_response.data)['data']['report_id']
        
        # Удаляем отчет
        response = tasks_client.delete(f'/v1/reports/{report_id}', headers=headers)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] == True
        assert data['data']['message'] == 'Report deleted successfully'

if __name__ == '__main__':
    # Запуск тестов
    pytest.main([__file__, '-v'])