from flask import Flask, request, jsonify
import sqlite3
import uuid
import logging
from datetime import datetime

app = Flask(__name__)
DATABASE = 'tasks.db'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

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
    
    conn.commit()
    conn.close()

# Функции для инженеров
@app.route('/v1/defects', methods=['POST'])
def create_defect():
    try:
        data = request.get_json()
        logger.info(f"📨 Получен запрос на создание дефекта: {data}")
        
        title = data.get('title')
        description = data.get('description', '')
        severity = data.get('severity', 'medium')
        
        if not title:
            return jsonify({'error': 'Title required'}), 400
        
        defect_id = str(uuid.uuid4())
        
        conn = get_db()
        conn.execute('''
            INSERT INTO defects (id, title, description, severity, reported_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (defect_id, title, description, severity, 'demo-user'))
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Дефект создан: {defect_id} - {title}")
        
        return jsonify({
            'success': True, 
            'data': {'defect_id': defect_id}
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания дефекта: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/v1/defects', methods=['GET'])
def get_defects():
    try:
        conn = get_db()
        defects = conn.execute('SELECT * FROM defects ORDER BY created_at DESC').fetchall()
        conn.close()
        
        # Преобразуем в словари
        defects_list = []
        for defect in defects:
            defects_list.append({
                'id': defect['id'],
                'title': defect['title'],
                'description': defect['description'],
                'severity': defect['severity'],
                'status': defect['status'],
                'reported_by': defect['reported_by'],
                'created_at': defect['created_at']
            })
        
        logger.info(f"📊 Отправлено дефектов: {len(defects_list)}")
        
        return jsonify({
            'success': True,
            'data': {
                'defects': defects_list
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения дефектов: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/v1/defects/<defect_id>', methods=['PUT'])
def update_defect(defect_id):
    try:
        data = request.get_json()
        status = data.get('status')
        description = data.get('description')
        
        conn = get_db()
        
        if status:
            conn.execute('UPDATE defects SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', 
                        (status, defect_id))
        if description:
            conn.execute('UPDATE defects SET description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', 
                        (description, defect_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Дефект обновлен: {defect_id}")
        
        return jsonify({
            'success': True,
            'data': {'message': 'Defect updated successfully'}
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления дефекта: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

# Функции для менеджеров
@app.route('/v1/tasks', methods=['POST'])
def create_task():
    try:
        data = request.get_json()
        logger.info(f"📨 Получен запрос на создание задачи: {data}")
        
        title = data.get('title')
        description = data.get('description', '')
        priority = data.get('priority', 'medium')
        assigned_to = data.get('assigned_to', '')
        due_date = data.get('due_date', '')
        
        if not title:
            logger.error("❌ Отсутствует название задачи")
            return jsonify({'error': 'Title required'}), 400
        
        task_id = str(uuid.uuid4())
        
        conn = get_db()
        conn.execute('''
            INSERT INTO tasks (id, title, description, priority, assigned_to, due_date, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, title, description, priority, assigned_to, due_date, 'system'))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Задача создана: {task_id} - {title}")
        
        return jsonify({
            'success': True, 
            'data': {
                'task_id': task_id,
                'message': 'Task created successfully'
            }
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания задачи: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/v1/tasks', methods=['GET'])
def get_tasks():
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
                'due_date': task['due_date']
            })
        
        logger.info(f"📊 Отправлено задач: {len(tasks_list)}")
        
        return jsonify({
            'success': True,
            'data': {
                'tasks': tasks_list
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения задач: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/v1/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    try:
        data = request.get_json()
        logger.info(f"📨 Обновление задачи {task_id}: {data}")
        
        status = data.get('status')
        assigned_to = data.get('assigned_to')
        due_date = data.get('due_date')
        
        conn = get_db()
        
        updates = []
        params = []
        
        if status:
            updates.append('status = ?')
            params.append(status)
        if assigned_to:
            updates.append('assigned_to = ?')
            params.append(assigned_to)
        if due_date:
            updates.append('due_date = ?')
            params.append(due_date)
            
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            query = f'UPDATE tasks SET {", ".join(updates)} WHERE id = ?'
            params.append(task_id)
            conn.execute(query, params)
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Задача обновлена: {task_id}")
        
        return jsonify({
            'success': True,
            'data': {'message': 'Task updated successfully'}
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления задачи: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

# Функции для отчетов (менеджеры)
@app.route('/v1/reports', methods=['POST'])
def create_report():
    try:
        data = request.get_json()
        logger.info(f"📨 Получен запрос на создание отчета: {data}")
        
        title = data.get('title')
        content = data.get('content', '')
        report_type = data.get('report_type', 'general')
        
        if not title:
            return jsonify({'error': 'Title required'}), 400
        
        report_id = str(uuid.uuid4())
        
        conn = get_db()
        conn.execute('''
            INSERT INTO reports (id, title, content, created_by, report_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (report_id, title, content, 'system', report_type))
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Отчет создан: {report_id} - {title}")
        
        return jsonify({
            'success': True, 
            'data': {'report_id': report_id}
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания отчета: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/v1/reports', methods=['GET'])
def get_reports():
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
        
        logger.info(f"📊 Отправлено отчетов: {len(reports_list)}")
        
        return jsonify({
            'success': True,
            'data': {
                'reports': reports_list
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения отчетов: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

# Статистика для руководителей
@app.route('/v1/statistics', methods=['GET'])
def get_statistics():
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
            WHERE due_date < DATE('now') AND status != 'completed'
        ''').fetchone()[0]
        
        # Статистика по дефектам
        high_severity_defects = conn.execute('SELECT COUNT(*) FROM defects WHERE severity = "high"').fetchone()[0]
        
        conn.close()
        
        stats = {
            'tasks': {
                'total': tasks_count,
                'completed': completed_tasks,
                'high_priority': high_priority_tasks,
                'overdue': overdue_tasks
            },
            'defects': {
                'total': defects_count,
                'open': open_defects,
                'high_severity': high_severity_defects
            },
            'sites': {
                'active': 3,
                'completed': 1
            }
        }
        
        logger.info(f"📈 Статистика: {stats}")
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка статистики: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'tasks'})

if __name__ == '__main__':
    logger.info("🚀 Запуск сервиса задач...")
    init_db()
    app.run(host='0.0.0.0', port=5002, debug=True)