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
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=24)

# Настройка Swagger UI
SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.json'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Construction Control System API"
    }
)

app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

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
    'tasks': 'http://tasks-service:5002',
    'orders': 'http://orders-service:5004'
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Список публичных эндпоинтов (не требуют JWT)
PUBLIC_ENDPOINTS = [
    '/v1/auth/login',
    '/v1/auth/register',
    '/health',
    '/health/all',
    '/api/docs',
    '/static/swagger.json',
    '/favicon.ico'
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

        logger.info(f"Forwarding request to {url} with method {method}")

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

        logger.info(f"Response from {service} service: {response.status_code}")

        return Response(
            response=response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error to {service} service: {url}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVICE_UNAVAILABLE', 'message': f'{service.capitalize()} service unavailable'}
        }), 503
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error to {service} service: {url}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVICE_TIMEOUT', 'message': f'{service.capitalize()} service timeout'}
        }), 503
    except Exception as e:
        logger.error(f"Service error to {service}: {str(e)}")
        return jsonify({
            'success': False,
            'error': {'code': 'SERVICE_ERROR', 'message': 'Service error'}
        }), 503

@app.before_request
def check_authentication():
    # Разрешаем доступ к публичным эндпоинтам и Swagger без аутентификации
    if (request.path in PUBLIC_ENDPOINTS or 
        request.path.startswith('/static/') or 
        request.path.startswith('/api/docs') or
        request.path == '/favicon.ico'):
        return
    return token_required(lambda: None)()

# Swagger JSON endpoint
@app.route('/static/swagger.json')
@limiter.exempt
def swagger_json():
    swagger_doc = {
        "openapi": "3.0.0",
        "info": {
            "title": "Construction Control System API",
            "description": "API для системы контроля строительных объектов - управление задачами, заказами, дефектами и отчетами",
            "version": "1.0.0",
            "contact": {
                "name": "API Support",
                "email": "support@constructionsystem.com"
            }
        },
        "servers": [
            {
                "url": "http://localhost:5000",
                "description": "Development server"
            },
            {
                "url": "http://api-gateway:5000",
                "description": "Docker container"
            }
        ],
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            },
            "schemas": {
                "Error": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": False},
                        "error": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "example": "VALIDATION_ERROR"},
                                "message": {"type": "string", "example": "Validation failed"}
                            }
                        }
                    }
                },
                "Success": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                        "data": {"type": "object"}
                    }
                },
                "LoginRequest": {
                    "type": "object",
                    "required": ["email", "password"],
                    "properties": {
                        "email": {"type": "string", "example": "user@example.com"},
                        "password": {"type": "string", "example": "password123"}
                    }
                },
                "RegisterRequest": {
                    "type": "object",
                    "required": ["email", "password", "name"],
                    "properties": {
                        "email": {"type": "string", "example": "user@example.com"},
                        "password": {"type": "string", "example": "password123"},
                        "name": {"type": "string", "example": "John Doe"},
                        "role": {"type": "string", "enum": ["engineer", "manager", "director"], "example": "engineer"}
                    }
                },
                "Defect": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        "status": {"type": "string", "enum": ["open", "in_progress", "closed"]},
                        "reported_by": {"type": "string"},
                        "assigned_to": {"type": "string"},
                        "created_at": {"type": "string", "format": "date-time"},
                        "updated_at": {"type": "string", "format": "date-time"}
                    }
                },
                "Task": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                        "assigned_to": {"type": "string"},
                        "due_date": {"type": "string", "format": "date"},
                        "created_at": {"type": "string", "format": "date-time"},
                        "updated_at": {"type": "string", "format": "date-time"}
                    }
                },
                "Order": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "status": {"type": "string", "enum": ["created", "in_progress", "completed", "cancelled"]},
                        "total_amount": {"type": "number", "format": "float"},
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "product": {"type": "string"},
                                    "quantity": {"type": "integer"},
                                    "unit_price": {"type": "number", "format": "float"}
                                }
                            }
                        },
                        "created_at": {"type": "string", "format": "date-time"},
                        "updated_at": {"type": "string", "format": "date-time"}
                    }
                }
            }
        },
        "paths": {
            "/v1/auth/login": {
                "post": {
                    "tags": ["Authentication"],
                    "summary": "User login",
                    "description": "Authenticate user and return JWT token",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/LoginRequest"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Successful login",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "token": {"type": "string"},
                                                    "user": {
                                                        "type": "object",
                                                        "properties": {
                                                            "id": {"type": "string"},
                                                            "email": {"type": "string"},
                                                            "name": {"type": "string"},
                                                            "role": {"type": "string"}
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/schemas/Error"},
                        "401": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "/v1/auth/register": {
                "post": {
                    "tags": ["Authentication"],
                    "summary": "User registration",
                    "description": "Register new user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RegisterRequest"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "User created successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "user_id": {"type": "string"},
                                                    "token": {"type": "string"},
                                                    "user": {
                                                        "type": "object",
                                                        "properties": {
                                                            "id": {"type": "string"},
                                                            "email": {"type": "string"},
                                                            "name": {"type": "string"},
                                                            "role": {"type": "string"}
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/schemas/Error"},
                        "409": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "/v1/defects": {
                "get": {
                    "tags": ["Defects"],
                    "summary": "Get all defects",
                    "description": "Retrieve list of all defects (requires authentication)",
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "List of defects",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "defects": {
                                                        "type": "array",
                                                        "items": {"$ref": "#/components/schemas/Defect"}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "401": {"$ref": "#/components/schemas/Error"}
                    }
                },
                "post": {
                    "tags": ["Defects"],
                    "summary": "Create new defect",
                    "description": "Create a new defect report (requires authentication)",
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["title"],
                                    "properties": {
                                        "title": {"type": "string"},
                                        "description": {"type": "string"},
                                        "severity": {"type": "string", "enum": ["low", "medium", "high"]}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {"$ref": "#/components/schemas/Success"},
                        "400": {"$ref": "#/components/schemas/Error"},
                        "401": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "/v1/tasks": {
                "get": {
                    "tags": ["Tasks"],
                    "summary": "Get all tasks",
                    "description": "Retrieve list of all tasks (requires authentication)",
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "List of tasks",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "tasks": {
                                                        "type": "array",
                                                        "items": {"$ref": "#/components/schemas/Task"}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "401": {"$ref": "#/components/schemas/Error"}
                    }
                },
                "post": {
                    "tags": ["Tasks"],
                    "summary": "Create new task",
                    "description": "Create a new task (requires manager role)",
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["title"],
                                    "properties": {
                                        "title": {"type": "string"},
                                        "description": {"type": "string"},
                                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                                        "assigned_to": {"type": "string"},
                                        "due_date": {"type": "string", "format": "date"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {"$ref": "#/components/schemas/Success"},
                        "400": {"$ref": "#/components/schemas/Error"},
                        "401": {"$ref": "#/components/schemas/Error"},
                        "403": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "/v1/orders": {
                "get": {
                    "tags": ["Orders"],
                    "summary": "Get all orders",
                    "description": "Retrieve list of orders with pagination and filtering",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "page",
                            "in": "query",
                            "schema": {"type": "integer", "default": 1},
                            "description": "Page number"
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 10},
                            "description": "Items per page"
                        },
                        {
                            "name": "status",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["created", "in_progress", "completed", "cancelled"]},
                            "description": "Filter by status"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of orders with pagination",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "orders": {
                                                        "type": "array",
                                                        "items": {"$ref": "#/components/schemas/Order"}
                                                    },
                                                    "pagination": {
                                                        "type": "object",
                                                        "properties": {
                                                            "page": {"type": "integer"},
                                                            "limit": {"type": "integer"},
                                                            "total": {"type": "integer"},
                                                            "pages": {"type": "integer"}
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "401": {"$ref": "#/components/schemas/Error"}
                    }
                },
                "post": {
                    "tags": ["Orders"],
                    "summary": "Create new order",
                    "description": "Create a new order with items",
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["title", "items"],
                                    "properties": {
                                        "title": {"type": "string"},
                                        "description": {"type": "string"},
                                        "items": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": ["product", "quantity", "unit_price"],
                                                "properties": {
                                                    "product": {"type": "string"},
                                                    "quantity": {"type": "integer"},
                                                    "unit_price": {"type": "number", "format": "float"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {"$ref": "#/components/schemas/Success"},
                        "400": {"$ref": "#/components/schemas/Error"},
                        "401": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "/v1/statistics": {
                "get": {
                    "tags": ["Statistics"],
                    "summary": "Get system statistics",
                    "description": "Retrieve system statistics (requires director or admin role)",
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "System statistics",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "tasks_total": {"type": "integer"},
                                                    "defects_total": {"type": "integer"},
                                                    "defects_open": {"type": "integer"},
                                                    "tasks_completed": {"type": "integer"},
                                                    "tasks_high_priority": {"type": "integer"},
                                                    "tasks_overdue": {"type": "integer"},
                                                    "defects_high_severity": {"type": "integer"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "401": {"$ref": "#/components/schemas/Error"},
                        "403": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "/health": {
                "get": {
                    "tags": ["System"],
                    "summary": "Health check",
                    "description": "Check if API gateway is healthy",
                    "responses": {
                        "200": {
                            "description": "Service is healthy",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string", "example": "healthy"},
                                            "service": {"type": "string", "example": "api-gateway"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    return jsonify(swagger_doc)

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

# Orders routes
@app.route('/v1/orders', methods=['GET', 'POST'])
@token_required
@limiter.limit(HIGH_LIMITS)
def orders_proxy():
    if request.method == 'GET':
        return forward_request('orders', 'v1/orders', 'GET')
    else:
        return forward_request('orders', 'v1/orders', 'POST', request.get_json())

@app.route('/v1/orders/<path:path>', methods=['GET', 'PUT', 'DELETE'])
@token_required
@limiter.limit(MEDIUM_LIMITS)
def orders_management_proxy(path):
    if request.method == 'GET':
        return forward_request('orders', f'v1/orders/{path}', 'GET')
    elif request.method == 'PUT':
        return forward_request('orders', f'v1/orders/{path}', 'PUT', request.get_json())
    elif request.method == 'DELETE':
        return forward_request('orders', f'v1/orders/{path}', 'DELETE')

@app.route('/v1/orders/<path:path>/cancel', methods=['POST'])
@token_required
@limiter.limit(MEDIUM_LIMITS)
def orders_cancel_proxy(path):
    return forward_request('orders', f'v1/orders/{path}/cancel', 'POST', request.get_json())

# Reports routes
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

# Health checks для всех сервисов
@app.route('/health/all', methods=['GET'])
@limiter.exempt
def health_all():
    services_status = {}

    # Проверка сервиса пользователей
    try:
        response = requests.get(f"{SERVICES['users']}/health", timeout=5)
        services_status['users'] = {
            'status': 'healthy' if response.status_code == 200 else 'unhealthy',
            'status_code': response.status_code
        }
    except Exception as e:
        services_status['users'] = {
            'status': 'unavailable',
            'error': str(e)
        }

    # Проверка сервиса задач
    try:
        response = requests.get(f"{SERVICES['tasks']}/health", timeout=5)
        services_status['tasks'] = {
            'status': 'healthy' if response.status_code == 200 else 'unhealthy',
            'status_code': response.status_code
        }
    except Exception as e:
        services_status['tasks'] = {
            'status': 'unavailable',
            'error': str(e)
        }

    # Проверка сервиса заказов
    try:
        response = requests.get(f"{SERVICES['orders']}/health", timeout=5)
        services_status['orders'] = {
            'status': 'healthy' if response.status_code == 200 else 'unhealthy',
            'status_code': response.status_code
        }
    except Exception as e:
        services_status['orders'] = {
            'status': 'unavailable',
            'error': str(e)
        }

    all_healthy = all(
        service['status'] == 'healthy'
        for service in services_status.values()
        if 'status' in service
    )

    return jsonify({
        'status': 'healthy' if all_healthy else 'degraded',
        'services': services_status,
        'timestamp': datetime.datetime.now().isoformat()
    })

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

# Обработка 404 ошибок
@app.errorhandler(404)
def not_found_handler(e):
    return jsonify({
        'success': False,
        'error': {
            'code': 'ENDPOINT_NOT_FOUND',
            'message': 'Endpoint not found',
            'details': f'The requested endpoint {request.path} was not found.'
        }
    }), 404

# Обработка 405 ошибок
@app.errorhandler(405)
def method_not_allowed_handler(e):
    return jsonify({
        'success': False,
        'error': {
            'code': 'METHOD_NOT_ALLOWED',
            'message': 'Method not allowed',
            'details': f'The method {request.method} is not allowed for this endpoint.'
        }
    }), 405

# CORS настройки
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Request-ID')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# OPTIONS обработчик для CORS preflight
@app.route('/v1/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return '', 200

if __name__ == '__main__':
    logger.info("🚀 Запуск API Gateway с Swagger...")
    logger.info(f"📚 Swagger UI доступен по адресу: http://localhost:5000/api/docs")
    logger.info(f"📖 Swagger JSON доступен по адресу: http://localhost:5000/static/swagger.json")
    app.run(host='0.0.0.0', port=5000, debug=True)