from flask import Flask, request, jsonify, Response
import requests
import logging
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SERVICES = {
    'users': 'http://users-service:5001',
    'tasks': 'http://tasks-service:5002'
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def forward_request(service, path, method='GET', data=None):
    try:
        url = f"{SERVICES[service]}/{path}"
        headers = {'Content-Type': 'application/json'}
        
        # Для GET запросов не передаем data, для остальных передаем
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
        return jsonify({'error': 'Service unavailable'}), 503

# Auth routes
@app.route('/v1/auth/<path:path>', methods=['POST'])
def auth_proxy(path):
    return forward_request('users', f'v1/auth/{path}', 'POST', request.get_json())

# Users routes
@app.route('/v1/users', methods=['GET'])
def users_proxy():
    return forward_request('users', 'v1/users', 'GET')

# Defects routes
@app.route('/v1/defects', methods=['GET', 'POST'])
def defects_proxy():
    if request.method == 'GET':
        return forward_request('tasks', 'v1/defects', 'GET')
    else:
        return forward_request('tasks', 'v1/defects', 'POST', request.get_json())

@app.route('/v1/defects/<path:path>', methods=['PUT'])
def defects_update_proxy(path):
    return forward_request('tasks', f'v1/defects/{path}', 'PUT', request.get_json())

# Tasks routes
@app.route('/v1/tasks', methods=['GET', 'POST'])
def tasks_proxy():
    if request.method == 'GET':
        return forward_request('tasks', 'v1/tasks', 'GET')
    else:
        return forward_request('tasks', 'v1/tasks', 'POST', request.get_json())

@app.route('/v1/tasks/<path:path>', methods=['PUT'])
def tasks_update_proxy(path):
    return forward_request('tasks', f'v1/tasks/{path}', 'PUT', request.get_json())

# Reports routes
@app.route('/v1/reports', methods=['GET', 'POST'])
def reports_proxy():
    if request.method == 'GET':
        return forward_request('tasks', 'v1/reports', 'GET')
    else:
        return forward_request('tasks', 'v1/reports', 'POST', request.get_json())

# Statistics route
@app.route('/v1/statistics', methods=['GET'])
def statistics_proxy():
    return forward_request('tasks', 'v1/statistics', 'GET')

# Health check
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'api-gateway'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)