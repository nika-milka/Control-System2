from flask import Flask, request, jsonify, Response
import requests
import logging
from flask_cors import CORS
import jwt
import datetime
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import uuid

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=24)

# Настройка Rate Limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window",
)

SERVICES = {
    'users': 'http://users-service:5001',
    'tasks': 'http://tasks-service:5002'
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Список публичных эндпоинтов (не требуют JWT)
PUBLIC_ENDPOINTS = [
    '/v1/auth/login',
    '/v1/auth/register',
    '/health'
]

# Более строгие лимиты для аутентификации
AUTH_LIMITS = "5 per minute"
DEFAULT_LIMITS = "100 per hour"
HIGH_LIMITS = "60 per minute"
MEDIUM_LIMITS = "30 per minute"

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                return jsonify({
                    'success': False,
                    'error': {'code': 'INVALID_TOKEN', 'message': 'Invalid token format'}
                }), 401
        
        if not token:
            return jsonify({
                'success': False,
                'error': {'code': 'TOKEN_REQUIRED', 'message': 'Token is required'}
            }), 401
        
        try:
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            current_user = {
                'user_id': data['user_id'],
                'email': data['email'],
                'role': data['role']
            }
            request.current_user = current_user
            
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': {'code': 'TOKEN_EXPIRED', 'message': 'Token has expired'}
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'error': {'code': 'INVALID_TOKEN', 'message': 'Token is invalid'}
            }), 401
        
        return f(*args, **kwargs)
    return decorated

def forward_request(service, path, method='GET', data=None):
    try:
        url = f"{SERVICES[service]}/{path}"
        headers = {
            'Content-Type': 'application/json',
            'X-Request-ID': request.headers.get('X-Request-ID', str(uuid.uuid4()))
        }
        
        if hasattr(request, 'current_user'):
            headers['X-User-ID'] = request.current_user['user_id']
            headers['X-User-Email'] = request.current_user['email']
            headers['X-User-Role'] = request.current_user['role']
        
        if method.upper() == 'GET':
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                timeout=30
            )
        else:
            response = requests.request(
                method=method.upper(),
                url=url,
                json=data,
                headers=headers,
                timeout=30
            )
        
        return Response(
            response=response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
    except Exception as e:
        logger.error(f"Service error: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVICE_UNAVAILABLE', 'message': 'Service unavailable'}
        }), 503

@app.before_request
def check_authentication():
    if request.path in PUBLIC_ENDPOINTS or request.path == '/health':
        return
    return token_required(lambda: None)()

# Auth routes - с строгими лимитами
@app.route('/v1/auth/<path:path>', methods=['POST'])
@limiter.limit(AUTH_LIMITS)
def auth_proxy(path):
    return forward_request('users', f'v1/auth/{path}', 'POST', request.get_json())

# Users routes
@app.route('/v1/users', methods=['GET'])
@token_required
@limiter.limit(DEFAULT_LIMITS)
def users_proxy():
    return forward_request('users', 'v1/users', 'GET')

# Defects routes
@app.route('/v1/defects', methods=['GET', 'POST'])
@token_required
@limiter.limit(HIGH_LIMITS)
def defects_proxy():
    if request.method == 'GET':
        return forward_request('tasks', 'v1/defects', 'GET')
    else:
        return forward_request('tasks', 'v1/defects', 'POST', request.get_json())

@app.route('/v1/defects/<path:path>', methods=['GET'])
@token_required
@limiter.limit(MEDIUM_LIMITS)
def defects_get_proxy(path):
    return forward_request('tasks', f'v1/defects/{path}', 'GET')

@app.route('/v1/defects/<path:path>', methods=['PUT'])
@token_required
@limiter.limit(MEDIUM_LIMITS)
def defects_update_proxy(path):
    return forward_request('tasks', f'v1/defects/{path}', 'PUT', request.get_json())

# Tasks routes
@app.route('/v1/tasks', methods=['GET', 'POST'])
@token_required
@limiter.limit(HIGH_LIMITS)
def tasks_proxy():
    if request.method == 'GET':
        return forward_request('tasks', 'v1/tasks', 'GET')
    else:
        return forward_request('tasks', 'v1/tasks', 'POST', request.get_json())

@app.route('/v1/tasks/<path:path>', methods=['GET'])
@token_required
@limiter.limit(MEDIUM_LIMITS)
def tasks_get_proxy(path):
    return forward_request('tasks', f'v1/tasks/{path}', 'GET')

@app.route('/v1/tasks/<path:path>', methods=['PUT'])
@token_required
@limiter.limit(MEDIUM_LIMITS)
def tasks_update_proxy(path):
    return forward_request('tasks', f'v1/tasks/{path}', 'PUT', request.get_json())

# Reports routes - требуют аутентификации
@app.route('/v1/reports', methods=['GET', 'POST'])
@token_required
@limiter.limit("40 per minute")
def reports_proxy():
    if request.method == 'GET':
        return forward_request('tasks', 'v1/reports', 'GET')
    else:
        return forward_request('tasks', 'v1/reports', 'POST', request.get_json())

# Reports management routes
@app.route('/v1/reports/<path:path>', methods=['GET', 'PUT', 'DELETE'])
@token_required
@limiter.limit("40 per minute")
def reports_management_proxy(path):
    if request.method == 'GET':
        return forward_request('tasks', f'v1/reports/{path}', 'GET')
    elif request.method == 'PUT':
        return forward_request('tasks', f'v1/reports/{path}', 'PUT', request.get_json())
    elif request.method == 'DELETE':
        return forward_request('tasks', f'v1/reports/{path}', 'DELETE')

# Reports generation routes
@app.route('/v1/reports/generate/statistics', methods=['POST'])
@token_required
@limiter.limit("10 per hour")
def reports_generate_statistics_proxy():
    return forward_request('tasks', 'v1/reports/generate/statistics', 'POST', request.get_json())

# Statistics route
@app.route('/v1/statistics', methods=['GET'])
@token_required
@limiter.limit(MEDIUM_LIMITS)
def statistics_proxy():
    return forward_request('tasks', 'v1/statistics', 'GET')

# Health check
@app.route('/health', methods=['GET'])
@limiter.exempt
def health():
    return jsonify({'status': 'healthy', 'service': 'api-gateway'})

# Обработка ошибок rate limiting
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'success': False,
        'error': {
            'code': 'RATE_LIMIT_EXCEEDED',
            'message': 'Rate limit exceeded',
            'details': f'Too many requests. Please try again later.'
        }
    }), 429

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)