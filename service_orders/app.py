from flask import Flask, request, jsonify
import sqlite3
import uuid
import logging
from datetime import datetime
import time
import json

app = Flask(__name__)
DATABASE = 'orders.db'

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def log_request():
    """Логирование входящего запроса"""
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    user_role = request.headers.get('X-User-Role', 'unknown')
    
    logger.info(f"Request {request_id} - User: {user_id}, Role: {user_role}, "
                f"Method: {request.method}, Path: {request.path}")

@app.before_request
def before_request():
    log_request()
    request.start_time = time.time()

@app.after_request
def after_request(response):
    request_id = request.headers.get('X-Request-ID', 'default')
    processing_time = time.time() - request.start_time
    
    logger.info(f"Request {request_id} - Processing time: {processing_time:.3f}s, "
                f"Status: {response.status_code}")
    
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Processing-Time'] = f'{processing_time:.3f}'
    
    return response

def init_db():
    conn = get_db()
    
    # Таблица заказов
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'created',
            total_amount DECIMAL(10,2) DEFAULT 0,
            items TEXT NOT NULL, -- JSON строка с составом заказа
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Индексы для улучшения производительности
    conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)')
    
    # Добавляем демо данные
    orders_count = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    
    if orders_count == 0:
        demo_orders = [
            ('Заказ строительных материалов', 
             'Поставка цемента, песка и кирпича для объекта А',
             'in_progress', 150000.00,
             '[{"product": "Цемент М500", "quantity": 100, "unit_price": 500}, {"product": "Песок", "quantity": 50, "unit_price": 1000}, {"product": "Кирпич", "quantity": 5000, "unit_price": 20}]',
             'engineer@system.com'),
             
            ('Заказ отделочных материалов',
             'Краска, шпатлевка, обои для внутренней отделки',
             'completed', 75000.50,
             '[{"product": "Краска белая", "quantity": 20, "unit_price": 1500}, {"product": "Шпатлевка", "quantity": 50, "unit_price": 800}, {"product": "Обои", "quantity": 30, "unit_price": 1200}]',
             'manager@system.com'),
             
            ('Заказ оборудования',
             'Строительное оборудование для монтажных работ',
             'created', 300000.00,
             '[{"product": "Бетономешалка", "quantity": 2, "unit_price": 25000}, {"product": "Леса строительные", "quantity": 10, "unit_price": 15000}, {"product": "Инструменты", "quantity": 1, "unit_price": 50000}]',
             'director@system.com')
        ]
        
        for title, description, status, total_amount, items, user_email in demo_orders:
            order_id = str(uuid.uuid4())
            # Получаем user_id по email (в реальной системе нужно получить из users service)
            user_id = str(uuid.uuid4())  # Временное решение для демо
            
            conn.execute('''
                INSERT INTO orders (id, user_id, title, description, status, total_amount, items)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (order_id, user_id, title, description, status, total_amount, items))
        
        logger.info("Added demo orders")
    
    conn.commit()
    conn.close()

# Вспомогательные функции
def has_permission(user_role, required_roles):
    """Проверка прав доступа"""
    return user_role in required_roles

def can_modify_order(order_user_id, current_user_id, user_role):
    """Проверка возможности модификации заказа"""
    return order_user_id == current_user_id or user_role in ['manager', 'admin']

# Эндпоинты для заказов
@app.route('/v1/orders', methods=['POST'])
def create_order():
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    user_role = request.headers.get('X-User-Role', 'unknown')
    
    try:
        data = request.get_json()
        logger.info(f"Request {request_id} - Creating order by user {user_id}")
        
        title = data.get('title')
        description = data.get('description', '')
        items = data.get('items', [])
        
        if not title:
            return jsonify({
                'success': False,
                'error': {'code': 'VALIDATION_ERROR', 'message': 'Title required'}
            }), 400
        
        if not items or not isinstance(items, list):
            return jsonify({
                'success': False,
                'error': {'code': 'VALIDATION_ERROR', 'message': 'Items must be a non-empty array'}
            }), 400
        
        # Валидация items
        for item in items:
            if not all(key in item for key in ['product', 'quantity', 'unit_price']):
                return jsonify({
                    'success': False,
                    'error': {'code': 'VALIDATION_ERROR', 'message': 'Each item must have product, quantity and unit_price'}
                }), 400
        
        # Расчет общей суммы
        total_amount = sum(item['quantity'] * item['unit_price'] for item in items)
        
        order_id = str(uuid.uuid4())
        
        conn = get_db()
        conn.execute('''
            INSERT INTO orders (id, user_id, title, description, total_amount, items)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (order_id, user_id, title, description, total_amount, json.dumps(items)))
        conn.commit()
        conn.close()
        
        logger.info(f"Request {request_id} - Order created: {order_id}")
        
        return jsonify({
            'success': True, 
            'data': {
                'order_id': order_id,
                'total_amount': total_amount,
                'message': 'Order created successfully'
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Request {request_id} - Order creation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/orders', methods=['GET'])
def get_orders():
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    user_role = request.headers.get('X-User-Role', 'unknown')
    
    try:
        # Параметры пагинации
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        status_filter = request.args.get('status', '')
        
        offset = (page - 1) * limit
        
        conn = get_db()
        
        # Базовый запрос
        query = 'SELECT * FROM orders'
        count_query = 'SELECT COUNT(*) FROM orders'
        params = []
        
        # Фильтрация по пользователю (если не админ/менеджер)
        if user_role not in ['manager', 'admin']:
            query += ' WHERE user_id = ?'
            count_query += ' WHERE user_id = ?'
            params.append(user_id)
        
        # Фильтрация по статусу
        if status_filter:
            if 'WHERE' in query:
                query += ' AND status = ?'
                count_query += ' AND status = ?'
            else:
                query += ' WHERE status = ?'
                count_query += ' WHERE status = ?'
            params.append(status_filter)
        
        # Сортировка и пагинация
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        # Получаем заказы
        orders = conn.execute(query, params).fetchall()
        
        # Получаем общее количество для пагинации
        count_params = params[:-2]  # Убираем LIMIT и OFFSET
        total_count = conn.execute(count_query, count_params).fetchone()[0]
        
        conn.close()
        
        # Преобразуем в словари
        orders_list = []
        for order in orders:
            orders_list.append({
                'id': order['id'],
                'title': order['title'],
                'description': order['description'],
                'status': order['status'],
                'total_amount': float(order['total_amount']),
                'items': json.loads(order['items']) if order['items'] else [],
                'user_id': order['user_id'],
                'created_at': order['created_at'],
                'updated_at': order['updated_at']
            })
        
        logger.info(f"Request {request_id} - Sent {len(orders_list)} orders")
        
        return jsonify({
            'success': True,
            'data': {
                'orders': orders_list,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total_count,
                    'pages': (total_count + limit - 1) // limit
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Get orders error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    user_role = request.headers.get('X-User-Role', 'unknown')
    
    try:
        conn = get_db()
        order = conn.execute(
            'SELECT * FROM orders WHERE id = ?', (order_id,)
        ).fetchone()
        conn.close()
        
        if not order:
            return jsonify({
                'success': False,
                'error': {'code': 'NOT_FOUND', 'message': 'Order not found'}
            }), 404
        
        # Проверка прав доступа
        if order['user_id'] != user_id and user_role not in ['manager', 'admin']:
            return jsonify({
                'success': False,
                'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}
            }), 403
        
        order_data = {
            'id': order['id'],
            'title': order['title'],
            'description': order['description'],
            'status': order['status'],
            'total_amount': float(order['total_amount']),
            'items': json.loads(order['items']) if order['items'] else [],
            'user_id': order['user_id'],
            'created_at': order['created_at'],
            'updated_at': order['updated_at']
        }
        
        logger.info(f"Request {request_id} - Order retrieved: {order_id}")
        
        return jsonify({
            'success': True,
            'data': order_data
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Get order error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/orders/<order_id>', methods=['PUT'])
def update_order(order_id):
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    user_role = request.headers.get('X-User-Role', 'unknown')
    
    try:
        data = request.get_json()
        logger.info(f"Request {request_id} - Updating order {order_id}")
        
        conn = get_db()
        
        # Проверяем существование заказа
        existing_order = conn.execute(
            'SELECT * FROM orders WHERE id = ?', (order_id,)
        ).fetchone()
        
        if not existing_order:
            conn.close()
            return jsonify({
                'success': False,
                'error': {'code': 'NOT_FOUND', 'message': 'Order not found'}
            }), 404
        
        # Проверка прав доступа
        if not can_modify_order(existing_order['user_id'], user_id, user_role):
            conn.close()
            return jsonify({
                'success': False,
                'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}
            }), 403
        
        updates = []
        params = []
        
        title = data.get('title')
        description = data.get('description')
        status = data.get('status')
        items = data.get('items')
        
        if title:
            updates.append('title = ?')
            params.append(title)
        if description is not None:
            updates.append('description = ?')
            params.append(description)
        if status:
            # Валидация статуса
            valid_statuses = ['created', 'in_progress', 'completed', 'cancelled']
            if status not in valid_statuses:
                conn.close()
                return jsonify({
                    'success': False,
                    'error': {'code': 'VALIDATION_ERROR', 'message': f'Invalid status. Must be one of: {valid_statuses}'}
                }), 400
            updates.append('status = ?')
            params.append(status)
        if items:
            # Пересчет суммы при изменении items
            total_amount = sum(item['quantity'] * item['unit_price'] for item in items)
            updates.append('items = ?')
            updates.append('total_amount = ?')
            params.append(json.dumps(items))
            params.append(total_amount)
            
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            query = f'UPDATE orders SET {", ".join(updates)} WHERE id = ?'
            params.append(order_id)
            conn.execute(query, params)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Request {request_id} - Order updated: {order_id}")
        
        return jsonify({
            'success': True,
            'data': {'message': 'Order updated successfully'}
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Order update error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/orders/<order_id>/cancel', methods=['POST'])
def cancel_order(order_id):
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    user_role = request.headers.get('X-User-Role', 'unknown')
    
    try:
        conn = get_db()
        
        # Проверяем существование заказа
        existing_order = conn.execute(
            'SELECT * FROM orders WHERE id = ?', (order_id,)
        ).fetchone()
        
        if not existing_order:
            conn.close()
            return jsonify({
                'success': False,
                'error': {'code': 'NOT_FOUND', 'message': 'Order not found'}
            }), 404
        
        # Проверка прав доступа
        if not can_modify_order(existing_order['user_id'], user_id, user_role):
            conn.close()
            return jsonify({
                'success': False,
                'error': {'code': 'FORBIDDEN', 'message': 'Access denied'}
            }), 403
        
        # Проверяем, можно ли отменить заказ
        if existing_order['status'] in ['completed', 'cancelled']:
            conn.close()
            return jsonify({
                'success': False,
                'error': {'code': 'INVALID_OPERATION', 'message': f'Cannot cancel order with status: {existing_order["status"]}'}
            }), 400
        
        # Обновляем статус
        conn.execute(
            'UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            ('cancelled', order_id)
        )
        conn.commit()
        conn.close()
        
        logger.info(f"Request {request_id} - Order cancelled: {order_id}")
        
        return jsonify({
            'success': True,
            'data': {'message': 'Order cancelled successfully'}
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Order cancellation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    request_id = request.headers.get('X-Request-ID', 'default')
    logger.info(f"Request {request_id} - Health check")
    
    return jsonify({
        'status': 'healthy', 
        'service': 'orders',
        'timestamp': datetime.now().isoformat()
    })

# Добавляем обработчик для корневого пути
@app.route('/')
def root():
    return jsonify({
        'service': 'orders-service',
        'version': '1.0',
        'status': 'running'
    })

if __name__ == '__main__':
    logger.info("🚀 Запуск сервиса заказов...")
    init_db()
    app.run(host='0.0.0.0', port=5004, debug=True)