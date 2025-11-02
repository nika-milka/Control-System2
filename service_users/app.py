from flask import Flask, request, jsonify
import sqlite3
import uuid
import hashlib
import logging
import jwt
import datetime

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=24)

DATABASE = 'users.db'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'engineer',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create default users
    default_users = [
        ('admin@system.com', 'admin123', 'Администратор Системы', 'admin'),
        ('manager@system.com', 'manager123', 'Менеджер Петров', 'manager'),
        ('engineer@system.com', 'engineer123', 'Инженер Иванов', 'engineer'),
        ('director@system.com', 'director123', 'Директор Сидоров', 'director')
    ]
    
    for email, password, name, role in default_users:
        user_exists = conn.execute(
            'SELECT id FROM users WHERE email = ?', (email,)
        ).fetchone()
        
        if not user_exists:
            password_hash = hashlib.md5(password.encode()).hexdigest()
            user_id = str(uuid.uuid4())
            conn.execute(
                'INSERT INTO users (id, email, password_hash, name, role) VALUES (?, ?, ?, ?, ?)',
                (user_id, email, password_hash, name, role)
            )
            logger.info(f"Created default user: {email} as {role}")
    
    conn.commit()
    conn.close()

def create_jwt_token(user_data):
    """Создание JWT токена"""
    payload = {
        'user_id': user_data['id'],
        'email': user_data['email'],
        'role': user_data['role'],
        'exp': datetime.datetime.utcnow() + app.config['JWT_ACCESS_TOKEN_EXPIRES'],
        'iat': datetime.datetime.utcnow()
    }
    return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')

@app.route('/v1/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': {'code': 'NO_DATA', 'message': 'No JSON data provided'}
            }), 400
            
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')
        role = data.get('role', 'engineer')
        
        # Проверка допустимых ролей
        valid_roles = ['engineer', 'manager', 'director']
        if role not in valid_roles:
            return jsonify({
                'success': False,
                'error': {'code': 'INVALID_ROLE', 'message': 'Invalid role. Must be engineer, manager, or director'}
            }), 400
        
        if not all([email, password, name]):
            return jsonify({
                'success': False,
                'error': {'code': 'MISSING_FIELDS', 'message': 'Missing required fields'}
            }), 400
        
        conn = get_db()
        
        existing = conn.execute(
            'SELECT id FROM users WHERE email = ?', (email,)
        ).fetchone()
        
        if existing:
            conn.close()
            return jsonify({
                'success': False,
                'error': {'code': 'USER_EXISTS', 'message': 'User already exists'}
            }), 409
        
        user_id = str(uuid.uuid4())
        password_hash = hashlib.md5(password.encode()).hexdigest()
        
        conn.execute(
            'INSERT INTO users (id, email, password_hash, name, role) VALUES (?, ?, ?, ?, ?)',
            (user_id, email, password_hash, name, role)
        )
        conn.commit()
        
        # Получаем созданного пользователя
        user = conn.execute(
            'SELECT * FROM users WHERE id = ?', (user_id,)
        ).fetchone()
        conn.close()
        
        # Создаем JWT токен
        token = create_jwt_token(dict(user))
        
        logger.info(f"New user registered: {email} as {role}")
        
        return jsonify({
            'success': True, 
            'data': {
                'user_id': user_id,
                'token': token,
                'user': {
                    'id': user_id,
                    'email': email,
                    'name': name,
                    'role': role
                }
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Register error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': {'code': 'NO_DATA', 'message': 'No JSON data provided'}
            }), 400
            
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({
                'success': False,
                'error': {'code': 'MISSING_CREDENTIALS', 'message': 'Email and password required'}
            }), 400
        
        conn = get_db()
        user = conn.execute(
            'SELECT * FROM users WHERE email = ?', (email,)
        ).fetchone()
        conn.close()
        
        if not user:
            logger.warning(f"Login failed: user {email} not found")
            return jsonify({
                'success': False,
                'error': {'code': 'INVALID_CREDENTIALS', 'message': 'Invalid credentials'}
            }), 401
        
        password_hash = hashlib.md5(password.encode()).hexdigest()
        if user['password_hash'] != password_hash:
            logger.warning(f"Login failed: invalid password for {email}")
            return jsonify({
                'success': False,
                'error': {'code': 'INVALID_CREDENTIALS', 'message': 'Invalid credentials'}
            }), 401
        
        # Создаем JWT токен
        token = create_jwt_token(dict(user))
        
        logger.info(f"User logged in: {email} as {user['role']}")
        
        return jsonify({
            'success': True,
            'data': {
                'token': token,
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'name': user['name'],
                    'role': user['role']
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/v1/users', methods=['GET'])
def get_users():
    try:
        # Логируем информацию о запросе
        request_id = request.headers.get('X-Request-ID', 'default')
        user_id = request.headers.get('X-User-ID')
        user_role = request.headers.get('X-User-Role')
        
        logger.info(f"Users list request - RequestID: {request_id}, User: {user_id}, Role: {user_role}")
        
        conn = get_db()
        users = conn.execute(
            'SELECT id, email, name, role, created_at FROM users'
        ).fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'users': [dict(user) for user in users]
            }
        })
        
    except Exception as e:
        logger.error(f"Get users error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVER_ERROR', 'message': 'Server error'}
        }), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'users'})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)