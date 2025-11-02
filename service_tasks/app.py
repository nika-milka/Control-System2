from flask import Flask, request, jsonify
import sqlite3
import uuid
import logging
from datetime import datetime
import time

app = Flask(__name__)
DATABASE = 'tasks.db'

# Настройка структурированного логирования
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
    """Логирование входящего запроса с трассировкой"""
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    user_role = request.headers.get('X-User-Role', 'unknown')
    
    logger.info(f"Request {request_id} - User: {user_id}, Role: {user_role}, "
                f"Method: {request.method}, Path: {request.path}")

@app.before_request
def before_request():
    # Логируем начало обработки запроса
    log_request()
    request.start_time = time.time()

@app.after_request
def after_request(response):
    # Логируем завершение обработки запроса
    request_id = request.headers.get('X-Request-ID', 'default')
    processing_time = time.time() - request.start_time
    
    logger.info(f"Request {request_id} - Processing time: {processing_time:.3f}s, "
                f"Status: {response.status_code}")
    
    # Добавляем заголовки для трассировки
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Processing-Time'] = f'{processing_time:.3f}'
    
    return response

def init_db():
    conn = get_db()
    
    # Таблица дефектов
    conn.execute('''
        CREATE TABLE IF NOT EXISTS defects (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            severity TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            reported_by TEXT NOT NULL,
            assigned_to TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица задач
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'medium',
            assigned_to TEXT,
            created_by TEXT NOT NULL,
            due_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица отчетов
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT,
            created_by TEXT NOT NULL,
            report_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Проверяем, есть ли уже демо данные
    defects_count = conn.execute('SELECT COUNT(*) FROM defects').fetchone()[0]
    tasks_count = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    reports_count = conn.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
    
    if defects_count == 0:
        # Добавляем демо дефекты
        demo_defects = [
            ('Трещина в фундаменте', 'Обнаружена трещина в северной части фундамента', 'high', 'open', 'engineer@system.com'),
            ('Протечка кровли', 'Протечка в районе вентиляционной шахты', 'medium', 'in_progress', 'engineer@system.com'),
            ('Неисправность электропроводки', 'Короткое замыкание в щитовой', 'high', 'open', 'engineer@system.com'),
            ('Повреждение штукатурки', 'Отслоение штукатурки на фасаде', 'low', 'open', 'engineer@system.com'),
            ('Не работает кондиционер', 'Кондиционер в офисе не включается', 'medium', 'open', 'manager@system.com')
        ]
        
        for title, description, severity, status, reported_by in demo_defects:
            defect_id = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO defects (id, title, description, severity, status, reported_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (defect_id, title, description, severity, status, reported_by))
        logger.info("Added demo defects")
    
    if tasks_count == 0:
        # Демо задачи
        demo_tasks = [
            ('Устранение трещины', 'Необходимо устранить трещину в фундаменте', 'in_progress', 'high', 'engineer@system.com', '2025-01-15'),
            ('Ремонт кровли', 'Ликвидировать протечку кровли', 'pending', 'medium', 'engineer@system.com', '2025-01-20'),
            ('Замена электропроводки', 'Полная замена проводки в щитовой', 'pending', 'high', 'engineer@system.com', '2025-01-25'),
            ('Восстановление штукатурки', 'Ремонт фасадной штукатурки', 'completed', 'low', 'engineer@system.com', '2025-01-10'),
            ('Обслуживание кондиционера', 'Диагностика и ремонт кондиционера', 'in_progress', 'medium', 'engineer@system.com', '2025-01-18')
        ]
        
        for title, description, status, priority, assigned_to, due_date in demo_tasks:
            task_id = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO tasks (id, title, description, status, priority, assigned_to, due_date, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (task_id, title, description, status, priority, assigned_to, due_date, 'manager@system.com'))
        logger.info("Added demo tasks")
    
    if reports_count == 0:
        # Добавляем демо отчеты
        demo_reports = [
            ('Еженедельный отчет о прогрессе', 
             'За прошедшую неделю выполнено 15 задач, открыто 3 новых дефекта. Основные достижения: завершен ремонт кровли, начата замена электропроводки.', 
             'progress', 'manager@system.com'),
            ('Финансовый отчет за квартал', 
             'Общие затраты на проекты: 1,200,000 руб. Выполнено 85% запланированных работ. Остаток бюджета: 150,000 руб.', 
             'financial', 'manager@system.com'),
            ('Технический отчет по объекту А', 
             'Состояние объекта: удовлетворительное. Выявлены незначительные дефекты отделки. Рекомендуется провести плановое обслуживание систем.', 
             'technical', 'engineer@system.com')
        ]
        
        for title, content, report_type, created_by in demo_reports:
            report_id = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO reports (id, title, content, report_type, created_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (report_id, title, content, report_type, created_by))
        logger.info("Added demo reports")
    
    conn.commit()
    conn.close()

# Функции для инженеров - ДЕФЕКТЫ
@app.route('/v1/defects', methods=['POST'])
def create_defect():
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    
    try:
        data = request.get_json()
        logger.info(f"Request {request_id} - Creating defect by user {user_id}: {data.get('title')}")
        
        title = data.get('title')
        description = data.get('description', '')
        severity = data.get('severity', 'medium')
        
        if not title:
            return jsonify({
                'success': False,
                'error': {'code': 'VALIDATION_ERROR', 'message': 'Title required'}
            }), 400
        
        defect_id = str(uuid.uuid4())
        
        conn = get_db()
        conn.execute('''
            INSERT INTO defects (id, title, description, severity, reported_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (defect_id, title, description, severity, user_id))
        conn.commit()
        conn.close()
        
        logger.info(f"Request {request_id} - Defect created: {defect_id}")
        
        return jsonify({
            'success': True, 
            'data': {'defect_id': defect_id}
        }), 201
        
    except Exception as e:
        logger.error(f"Request {request_id} - Defect creation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/defects', methods=['GET'])
def get_defects():
    request_id = request.headers.get('X-Request-ID', 'default')
    
    try:
        conn = get_db()
        defects = conn.execute('SELECT * FROM defects ORDER BY created_at DESC').fetchall()
        conn.close()
        
        defects_list = []
        for defect in defects:
            defects_list.append({
                'id': defect['id'],
                'title': defect['title'],
                'description': defect['description'],
                'severity': defect['severity'],
                'status': defect['status'],
                'reported_by': defect['reported_by'],
                'assigned_to': defect['assigned_to'],
                'created_at': defect['created_at'],
                'updated_at': defect['updated_at']
            })
        
        logger.info(f"Request {request_id} - Sent {len(defects_list)} defects")
        
        return jsonify({
            'success': True,
            'data': {
                'defects': defects_list
            }
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Get defects error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/defects/<defect_id>', methods=['GET'])
def get_defect(defect_id):
    request_id = request.headers.get('X-Request-ID', 'default')
    
    try:
        conn = get_db()
        defect = conn.execute(
            'SELECT * FROM defects WHERE id = ?', (defect_id,)
        ).fetchone()
        conn.close()
        
        if not defect:
            return jsonify({
                'success': False,
                'error': {'code': 'NOT_FOUND', 'message': 'Defect not found'}
            }), 404
        
        defect_data = {
            'id': defect['id'],
            'title': defect['title'],
            'description': defect['description'],
            'severity': defect['severity'],
            'status': defect['status'],
            'reported_by': defect['reported_by'],
            'assigned_to': defect['assigned_to'],
            'created_at': defect['created_at'],
            'updated_at': defect['updated_at']
        }
        
        logger.info(f"Request {request_id} - Defect retrieved: {defect_id}")
        
        return jsonify({
            'success': True,
            'data': defect_data
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Get defect error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/defects/<defect_id>', methods=['PUT'])
def update_defect(defect_id):
    request_id = request.headers.get('X-Request-ID', 'default')
    
    try:
        data = request.get_json()
        logger.info(f"Request {request_id} - Updating defect {defect_id}: {data}")
        
        title = data.get('title')
        description = data.get('description')
        severity = data.get('severity')
        status = data.get('status')
        assigned_to = data.get('assigned_to')
        
        conn = get_db()
        
        # Проверяем существование дефекта
        existing_defect = conn.execute(
            'SELECT * FROM defects WHERE id = ?', (defect_id,)
        ).fetchone()
        
        if not existing_defect:
            conn.close()
            return jsonify({
                'success': False,
                'error': {'code': 'NOT_FOUND', 'message': 'Defect not found'}
            }), 404
        
        updates = []
        params = []
        
        if title:
            updates.append('title = ?')
            params.append(title)
        if description is not None:
            updates.append('description = ?')
            params.append(description)
        if severity:
            updates.append('severity = ?')
            params.append(severity)
        if status:
            updates.append('status = ?')
            params.append(status)
        if assigned_to is not None:
            updates.append('assigned_to = ?')
            params.append(assigned_to)
            
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            query = f'UPDATE defects SET {", ".join(updates)} WHERE id = ?'
            params.append(defect_id)
            conn.execute(query, params)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Request {request_id} - Defect updated: {defect_id}")
        
        return jsonify({
            'success': True,
            'data': {'message': 'Defect updated successfully'}
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Defect update error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

# Функции для менеджеров - ЗАДАЧИ
@app.route('/v1/tasks', methods=['POST'])
def create_task():
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    
    try:
        data = request.get_json()
        logger.info(f"Request {request_id} - Creating task by user {user_id}: {data.get('title')}")
        
        title = data.get('title')
        description = data.get('description', '')
        priority = data.get('priority', 'medium')
        assigned_to = data.get('assigned_to', '')
        due_date = data.get('due_date', '')
        
        if not title:
            logger.error("❌ Отсутствует название задачи")
            return jsonify({
                'success': False,
                'error': {'code': 'VALIDATION_ERROR', 'message': 'Title required'}
            }), 400
        
        task_id = str(uuid.uuid4())
        
        conn = get_db()
        conn.execute('''
            INSERT INTO tasks (id, title, description, priority, assigned_to, due_date, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, title, description, priority, assigned_to, due_date, user_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Request {request_id} - Task created: {task_id}")
        
        return jsonify({
            'success': True, 
            'data': {
                'task_id': task_id,
                'message': 'Task created successfully'
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Request {request_id} - Task creation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': f'Server error: {str(e)}'}
        }), 500

@app.route('/v1/tasks', methods=['GET'])
def get_tasks():
    request_id = request.headers.get('X-Request-ID', 'default')
    
    try:
        conn = get_db()
        tasks = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC').fetchall()
        conn.close()
        
        # Преобразуем в словари
        tasks_list = []
        for task in tasks:
            tasks_list.append({
                'id': task['id'],
                'title': task['title'],
                'description': task['description'],
                'status': task['status'],
                'priority': task['priority'],
                'assigned_to': task['assigned_to'],
                'created_at': task['created_at'],
                'due_date': task['due_date'],
                'updated_at': task['updated_at']
            })
        
        logger.info(f"Request {request_id} - Sent {len(tasks_list)} tasks")
        
        return jsonify({
            'success': True,
            'data': {
                'tasks': tasks_list
            }
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Get tasks error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    request_id = request.headers.get('X-Request-ID', 'default')
    
    try:
        conn = get_db()
        task = conn.execute(
            'SELECT * FROM tasks WHERE id = ?', (task_id,)
        ).fetchone()
        conn.close()
        
        if not task:
            return jsonify({
                'success': False,
                'error': {'code': 'NOT_FOUND', 'message': 'Task not found'}
            }), 404
        
        task_data = {
            'id': task['id'],
            'title': task['title'],
            'description': task['description'],
            'status': task['status'],
            'priority': task['priority'],
            'assigned_to': task['assigned_to'],
            'due_date': task['due_date'],
            'created_by': task['created_by'],
            'created_at': task['created_at'],
            'updated_at': task['updated_at']
        }
        
        logger.info(f"Request {request_id} - Task retrieved: {task_id}")
        
        return jsonify({
            'success': True,
            'data': task_data
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Get task error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    request_id = request.headers.get('X-Request-ID', 'default')
    
    try:
        data = request.get_json()
        logger.info(f"Request {request_id} - Updating task {task_id}: {data}")
        
        title = data.get('title')
        description = data.get('description')
        status = data.get('status')
        priority = data.get('priority')
        assigned_to = data.get('assigned_to')
        due_date = data.get('due_date')
        
        conn = get_db()
        
        # Проверяем существование задачи
        existing_task = conn.execute(
            'SELECT * FROM tasks WHERE id = ?', (task_id,)
        ).fetchone()
        
        if not existing_task:
            conn.close()
            return jsonify({
                'success': False,
                'error': {'code': 'NOT_FOUND', 'message': 'Task not found'}
            }), 404
        
        updates = []
        params = []
        
        if title:
            updates.append('title = ?')
            params.append(title)
        if description is not None:
            updates.append('description = ?')
            params.append(description)
        if status:
            updates.append('status = ?')
            params.append(status)
        if priority:
            updates.append('priority = ?')
            params.append(priority)
        if assigned_to is not None:
            updates.append('assigned_to = ?')
            params.append(assigned_to)
        if due_date is not None:
            updates.append('due_date = ?')
            params.append(due_date)
            
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            query = f'UPDATE tasks SET {", ".join(updates)} WHERE id = ?'
            params.append(task_id)
            conn.execute(query, params)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Request {request_id} - Task updated: {task_id}")
        
        return jsonify({
            'success': True,
            'data': {'message': 'Task updated successfully'}
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Task update error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

# Функции для отчетов (менеджеры)
@app.route('/v1/reports', methods=['POST'])
def create_report():
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    
    try:
        data = request.get_json()
        logger.info(f"Request {request_id} - Creating report by user {user_id}: {data.get('title')}")
        
        title = data.get('title')
        content = data.get('content', '')
        report_type = data.get('report_type', 'general')
        
        if not title:
            return jsonify({
                'success': False,
                'error': {'code': 'VALIDATION_ERROR', 'message': 'Title required'}
            }), 400
        
        report_id = str(uuid.uuid4())
        
        conn = get_db()
        conn.execute('''
            INSERT INTO reports (id, title, content, created_by, report_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (report_id, title, content, user_id, report_type))
        conn.commit()
        conn.close()
        
        logger.info(f"Request {request_id} - Report created: {report_id}")
        
        return jsonify({
            'success': True, 
            'data': {'report_id': report_id}
        }), 201
        
    except Exception as e:
        logger.error(f"Request {request_id} - Report creation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/reports', methods=['GET'])
def get_reports():
    request_id = request.headers.get('X-Request-ID', 'default')
    
    try:
        conn = get_db()
        reports = conn.execute('SELECT * FROM reports ORDER BY created_at DESC').fetchall()
        conn.close()
        
        reports_list = []
        for report in reports:
            reports_list.append({
                'id': report['id'],
                'title': report['title'],
                'content': report['content'],
                'report_type': report['report_type'],
                'created_at': report['created_at']
            })
        
        logger.info(f"Request {request_id} - Sent {len(reports_list)} reports")
        
        return jsonify({
            'success': True,
            'data': {
                'reports': reports_list
            }
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Get reports error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/reports/<report_id>', methods=['GET'])
def get_report(report_id):
    request_id = request.headers.get('X-Request-ID', 'default')
    
    try:
        conn = get_db()
        report = conn.execute(
            'SELECT * FROM reports WHERE id = ?', (report_id,)
        ).fetchone()
        conn.close()
        
        if not report:
            return jsonify({
                'success': False,
                'error': {'code': 'NOT_FOUND', 'message': 'Report not found'}
            }), 404
        
        report_data = {
            'id': report['id'],
            'title': report['title'],
            'content': report['content'],
            'report_type': report['report_type'],
            'created_by': report['created_by'],
            'created_at': report['created_at']
        }
        
        logger.info(f"Request {request_id} - Report retrieved: {report_id}")
        
        return jsonify({
            'success': True,
            'data': report_data
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Get report error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/reports/<report_id>', methods=['PUT'])
def update_report(report_id):
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    
    try:
        data = request.get_json()
        logger.info(f"Request {request_id} - Updating report {report_id} by user {user_id}")
        
        title = data.get('title')
        content = data.get('content')
        report_type = data.get('report_type')
        
        conn = get_db()
        
        # Проверяем существование отчета
        existing_report = conn.execute(
            'SELECT * FROM reports WHERE id = ?', (report_id,)
        ).fetchone()
        
        if not existing_report:
            conn.close()
            return jsonify({
                'success': False,
                'error': {'code': 'NOT_FOUND', 'message': 'Report not found'}
            }), 404
        
        updates = []
        params = []
        
        if title:
            updates.append('title = ?')
            params.append(title)
        if content:
            updates.append('content = ?')
            params.append(content)
        if report_type:
            updates.append('report_type = ?')
            params.append(report_type)
            
        if updates:
            query = f'UPDATE reports SET {", ".join(updates)} WHERE id = ?'
            params.append(report_id)
            conn.execute(query, params)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Request {request_id} - Report updated: {report_id}")
        
        return jsonify({
            'success': True,
            'data': {'message': 'Report updated successfully'}
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Report update error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/reports/<report_id>', methods=['DELETE'])
def delete_report(report_id):
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    
    try:
        conn = get_db()
        
        # Проверяем существование отчета
        existing_report = conn.execute(
            'SELECT * FROM reports WHERE id = ?', (report_id,)
        ).fetchone()
        
        if not existing_report:
            conn.close()
            return jsonify({
                'success': False,
                'error': {'code': 'NOT_FOUND', 'message': 'Report not found'}
            }), 404
        
        # Удаляем отчет
        conn.execute('DELETE FROM reports WHERE id = ?', (report_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Request {request_id} - Report deleted: {report_id} by user {user_id}")
        
        return jsonify({
            'success': True,
            'data': {'message': 'Report deleted successfully'}
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Report deletion error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

# Новый эндпоинт для генерации отчетов по статистике
@app.route('/v1/reports/generate/statistics', methods=['POST'])
def generate_statistics_report():
    request_id = request.headers.get('X-Request-ID', 'default')
    user_id = request.headers.get('X-User-ID', 'anonymous')
    
    try:
        data = request.get_json() or {}
        report_type = data.get('report_type', 'statistics')
        title = data.get('title', 'Статистический отчет')
        
        conn = get_db()
        
        # Получаем статистику
        defects_count = conn.execute('SELECT COUNT(*) FROM defects').fetchone()[0]
        tasks_count = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
        open_defects = conn.execute('SELECT COUNT(*) FROM defects WHERE status = "open"').fetchone()[0]
        completed_tasks = conn.execute('SELECT COUNT(*) FROM tasks WHERE status = "completed"').fetchone()[0]
        high_priority_tasks = conn.execute('SELECT COUNT(*) FROM tasks WHERE priority = "high"').fetchone()[0]
        overdue_tasks = conn.execute('SELECT COUNT(*) FROM tasks WHERE due_date < DATE("now") AND status != "completed"').fetchone()[0]
        
        # Генерируем содержание отчета
        content = f"""
СТАТИСТИЧЕСКИЙ ОТЧЕТ
Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Пользователь: {user_id}

ОБЩАЯ СТАТИСТИКА:
- Всего задач: {tasks_count}
- Всего дефектов: {defects_count}
- Выполненных задач: {completed_tasks}
- Открытых дефектов: {open_defects}

АНАЛИТИКА:
- Задач с высоким приоритетом: {high_priority_tasks}
- Просроченных задач: {overdue_tasks}
- Процент выполнения: {(completed_tasks / tasks_count * 100) if tasks_count > 0 else 0:.1f}%

РЕКОМЕНДАЦИИ:
1. Обратить внимание на {overdue_tasks} просроченных задач
2. Приоритетно решить {high_priority_tasks} важных задач
3. Обработать {open_defects} открытых дефектов
"""
        
        report_id = str(uuid.uuid4())
        
        conn.execute('''
            INSERT INTO reports (id, title, content, created_by, report_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (report_id, title, content.strip(), user_id, report_type))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Request {request_id} - Statistics report generated: {report_id}")
        
        return jsonify({
            'success': True, 
            'data': {
                'report_id': report_id,
                'message': 'Statistics report generated successfully'
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Request {request_id} - Statistics report generation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

# Статистика для руководителей
@app.route('/v1/statistics', methods=['GET'])
def get_statistics():
    request_id = request.headers.get('X-Request-ID', 'default')
    
    try:
        conn = get_db()
        
        # Общая статистика
        defects_count = conn.execute('SELECT COUNT(*) FROM defects').fetchone()[0]
        tasks_count = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
        open_defects = conn.execute('SELECT COUNT(*) FROM defects WHERE status = "open"').fetchone()[0]
        completed_tasks = conn.execute('SELECT COUNT(*) FROM tasks WHERE status = "completed"').fetchone()[0]
        
        # Статистика по приоритетам
        high_priority_tasks = conn.execute('SELECT COUNT(*) FROM tasks WHERE priority = "high"').fetchone()[0]
        
        # Просроченные задачи
        overdue_tasks = conn.execute('''
            SELECT COUNT(*) FROM tasks 
            WHERE due_date < DATE("now") AND status != "completed"
        ''').fetchone()[0]
        
        # Статистика по дефектам
        high_severity_defects = conn.execute('SELECT COUNT(*) FROM defects WHERE severity = "high"').fetchone()[0]
        
        conn.close()
        
        stats = {
            'tasks_total': tasks_count,
            'defects_total': defects_count,
            'defects_open': open_defects,
            'tasks_completed': completed_tasks,
            'tasks_high_priority': high_priority_tasks,
            'tasks_overdue': overdue_tasks,
            'defects_high_severity': high_severity_defects
        }
        
        logger.info(f"Request {request_id} - Statistics: {stats}")
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"Request {request_id} - Statistics error: {str(e)}")
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
        'service': 'tasks',
        'timestamp': datetime.now().isoformat()
    })

# Добавляем обработчик для корневого пути
@app.route('/')
def root():
    return jsonify({
        'service': 'tasks-service',
        'version': '1.0',
        'status': 'running'
    })

if __name__ == '__main__':
    logger.info("🚀 Запуск сервиса задач с трассировкой...")
    init_db()
    app.run(host='0.0.0.0', port=5002, debug=True)