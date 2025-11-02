from flask import Flask, render_template, request, session, redirect, url_for
import requests
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'demo-secret-key'
API_BASE_URL = 'http://api-gateway:5000/v1'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            
            print(f"🔄 Попытка входа: {email}")
            
            response = requests.post(
                f'{API_BASE_URL}/auth/login', 
                json={'email': email, 'password': password},
                timeout=5
            )
            
            print(f"📡 Ответ сервера: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                session['token'] = data['data']['token']
                session['user'] = data['data']['user']
                print(f"✅ Успешный вход: {session['user']['name']} как {session['user']['role']}")
                return redirect(url_for('dashboard'))
            else:
                error_data = response.json()
                error_msg = error_data.get('error', 'Login failed')
                print(f"❌ Ошибка входа: {error_msg}")
                return render_template('login.html', error=error_msg)
                
        except requests.exceptions.ConnectionError:
            print("❌ Ошибка подключения к API")
            return render_template('login.html', error='Сервис недоступен. Попробуйте позже.')
        except requests.exceptions.Timeout:
            print("❌ Таймаут подключения к API")
            return render_template('login.html', error='Таймаут подключения. Попробуйте позже.')
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}")
            return render_template('login.html', error='Произошла ошибка. Попробуйте позже.')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            name = request.form.get('name')
            role = request.form.get('role', 'engineer')
            
            print(f"🔄 Попытка регистрации: {email} как {role}")
            
            response = requests.post(
                f'{API_BASE_URL}/auth/register', 
                json={'email': email, 'password': password, 'name': name, 'role': role},
                timeout=5
            )
            
            print(f"📡 Ответ регистрации: {response.status_code}")
            
            if response.status_code == 201:
                print(f"✅ Успешная регистрация: {email}")
                return redirect(url_for('login'))
            else:
                error_data = response.json()
                error_msg = error_data.get('error', 'Registration failed')
                print(f"❌ Ошибка регистрации: {error_msg}")
                return render_template('register.html', error=error_msg)
                
        except requests.exceptions.ConnectionError:
            print("❌ Ошибка подключения к API при регистрации")
            return render_template('register.html', error='Сервис недоступен. Попробуйте позже.')
        except Exception as e:
            print(f"❌ Ошибка регистрации: {e}")
            return render_template('register.html', error='Произошла ошибка. Попробуйте позже.')
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'token' not in session:
        print("🚫 Нет токена в сессии - редирект на логин")
        return redirect(url_for('login'))
    
    user = session['user']
    print(f"📊 Доступ к дашборду: {user['name']} (роль: {user['role']})")
    
    # Инициализация данных
    defects = []
    tasks = []
    statistics = {}
    
    try:
        # Получение дефектов (для инженеров и менеджеров)
        if user['role'] in ['engineer', 'manager', 'admin']:
            print("🔧 Запрос дефектов...")
            defects_response = requests.get(f'{API_BASE_URL}/defects', timeout=10)
            print(f"📡 Ответ дефектов: {defects_response.status_code}")
            
            if defects_response.status_code == 200:
                defects_data = defects_response.json()
                print(f"📦 Данные дефектов: {json.dumps(defects_data, indent=2, ensure_ascii=False)}")
                
                if defects_data.get('success'):
                    defects = defects_data.get('data', {}).get('defects', [])
                    print(f"✅ Загружено дефектов: {len(defects)}")
                else:
                    print(f"⚠️  API вернул success=false: {defects_data.get('error')}")
            else:
                print(f"❌ Ошибка получения дефектов: {defects_response.status_code} - {defects_response.text}")
        
        # Получение задач (для всех ролей)
        print("📝 Запрос задач...")
        tasks_response = requests.get(f'{API_BASE_URL}/tasks', timeout=10)
        print(f"📡 Ответ задач: {tasks_response.status_code}")
        
        if tasks_response.status_code == 200:
            tasks_data = tasks_response.json()
            if tasks_data.get('success'):
                tasks = tasks_data.get('data', {}).get('tasks', [])
                print(f"✅ Загружено задач: {len(tasks)}")
            else:
                print(f"⚠️  API вернул success=false для задач: {tasks_data.get('error')}")
        else:
            print(f"❌ Ошибка получения задач: {tasks_response.status_code} - {tasks_response.text}")
        
        # Получение статистики (для руководителей и админов)
        if user['role'] in ['director', 'admin']:
            print("📈 Запрос статистики...")
            stats_response = requests.get(f'{API_BASE_URL}/statistics', timeout=10)
            print(f"📡 Ответ статистики: {stats_response.status_code}")
            
            if stats_response.status_code == 200:
                statistics_data = stats_response.json()
                if statistics_data.get('success'):
                    statistics = statistics_data.get('data', {})
                    print(f"✅ Статистика загружена: {statistics}")
                else:
                    print(f"⚠️  API вернул success=false для статистики: {statistics_data.get('error')}")
            else:
                print(f"❌ Ошибка получения статистики: {stats_response.status_code}")
                
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Ошибка подключения при загрузке данных: {e}")
    except requests.exceptions.Timeout as e:
        print(f"❌ Таймаут при загрузке данных: {e}")
    except Exception as e:
        print(f"❌ Неожиданная ошибка при загрузке данных: {e}")
    
    print(f"🎯 Итоговые данные для рендеринга: {len(defects)} дефектов, {len(tasks)} задач")
    
    return render_template('dashboard.html', 
                         user=user, 
                         defects=defects[:5],
                         tasks=tasks[:5],
                         statistics=statistics)

@app.route('/admin')
def admin_panel():
    if 'token' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    if user['role'] not in ['admin', 'director']:
        print(f"🚫 Доступ запрещен: {user['role']} пытается получить доступ к админке")
        return redirect(url_for('dashboard'))
    
    print(f"🛠️  Доступ к админке: {user['name']}")
    
    users = []
    statistics = {}
    
    try:
        # Получение статистики
        stats_response = requests.get(f'{API_BASE_URL}/statistics', timeout=10)
        if stats_response.status_code == 200:
            stats_data = stats_response.json()
            if stats_data.get('success'):
                statistics = stats_data.get('data', {})
        
        # Получение списка пользователей
        users_response = requests.get(f'{API_BASE_URL}/users', timeout=10)
        if users_response.status_code == 200:
            users_data = users_response.json()
            if users_data.get('success'):
                users = users_data.get('data', {}).get('users', [])
                print(f"✅ Загружено пользователей: {len(users)}")
            else:
                print(f"⚠️  API вернул success=false для пользователей")
        else:
            print(f"❌ Ошибка получения пользователей: {users_response.status_code}")
            
        # Fallback к mock пользователям если API недоступно
        if not users:
            print("🔄 Используем mock пользователей")
            users = [
                {'id': '1', 'name': 'Администратор', 'email': 'admin@system.com', 'role': 'admin', 'created_at': '2025-01-01'},
                {'id': '2', 'name': 'Менеджер Петров', 'email': 'manager@system.com', 'role': 'manager', 'created_at': '2025-01-01'},
                {'id': '3', 'name': 'Инженер Иванов', 'email': 'engineer@system.com', 'role': 'engineer', 'created_at': '2025-01-01'},
                {'id': '4', 'name': 'Директор Сидоров', 'email': 'director@system.com', 'role': 'director', 'created_at': '2025-01-01'}
            ]
        
    except Exception as e:
        print(f"❌ Ошибка загрузки админских данных: {e}")
    
    return render_template('admin.html', 
                         user=user, 
                         users=users,
                         statistics=statistics)

@app.route('/create_defect', methods=['POST'])
def create_defect():
    if 'token' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    # Проверка прав - только инженеры и менеджеры
    if user['role'] not in ['engineer', 'manager', 'admin']:
        print(f"🚫 Нет прав на создание дефектов: {user['role']}")
        return redirect(url_for('dashboard'))
    
    try:
        title = request.form.get('title')
        description = request.form.get('description')
        severity = request.form.get('severity', 'medium')
        
        print(f"🔄 Создание дефекта: {title} пользователем {user['name']}")
        
        response = requests.post(
            f'{API_BASE_URL}/defects',
            json={
                'title': title,
                'description': description,
                'severity': severity
            },
            timeout=10
        )
        
        print(f"📡 Ответ создания дефекта: {response.status_code}")
        
        if response.status_code == 201:
            print("✅ Дефект успешно создан")
        else:
            error_data = response.json()
            print(f"❌ Ошибка создания дефекта: {error_data.get('error', 'Unknown error')}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка подключения при создании дефекта")
    except Exception as e:
        print(f"❌ Ошибка запроса создания дефекта: {e}")
    
    return redirect(url_for('defects_page'))

@app.route('/create_task', methods=['POST'])
def create_task():
    if 'token' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    # Проверка прав - только менеджеры
    if user['role'] not in ['manager', 'admin']:
        print(f"🚫 Нет прав на создание задач: {user['role']}")
        return redirect(url_for('dashboard'))
    
    try:
        # Получаем данные из формы
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority', 'medium')
        assigned_to = request.form.get('assigned_to', '')
        due_date = request.form.get('due_date', '')
        
        print(f"🔄 Создание задачи пользователем {user['name']}")
        print(f"📋 Данные формы:")
        print(f"  - title: {title}")
        print(f"  - description: {description}")
        print(f"  - priority: {priority}")
        print(f"  - assigned_to: {assigned_to}")
        print(f"  - due_date: {due_date}")
        
        # Проверяем обязательные поля
        if not title or not title.strip():
            print("❌ Ошибка: название задачи обязательно")
            return redirect(url_for('tasks_page'))
        
        # Подготовка данных для API
        task_data = {
            'title': title.strip(),
            'description': description.strip() if description else '',
            'priority': priority
        }
        
        # Добавляем опциональные поля
        if assigned_to and assigned_to.strip():
            task_data['assigned_to'] = assigned_to.strip()
        
        if due_date and due_date.strip():
            task_data['due_date'] = due_date.strip()
        
        print(f"📨 Отправка данных в API:")
        print(f"  URL: {API_BASE_URL}/tasks")
        print(f"  Данные: {json.dumps(task_data, indent=2, ensure_ascii=False)}")
        
        # Отправляем запрос
        response = requests.post(
            f'{API_BASE_URL}/tasks',
            json=task_data,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"📡 Ответ от API:")
        print(f"  Статус: {response.status_code}")
        print(f"  Заголовки: {dict(response.headers)}")
        print(f"  Тело ответа: {response.text}")
        
        if response.status_code == 201:
            response_data = response.json()
            print(f"✅ Задача успешно создана!")
            print(f"   ID задачи: {response_data.get('data', {}).get('task_id')}")
            print(f"   Сообщение: {response_data.get('data', {}).get('message')}")
        elif response.status_code == 400:
            error_data = response.json()
            print(f"❌ Ошибка валидации: {error_data.get('error')}")
        elif response.status_code == 500:
            error_data = response.json()
            print(f"❌ Ошибка сервера: {error_data.get('error')}")
        else:
            print(f"❌ Неожиданный статус ответа: {response.status_code}")
            print(f"   Тело ответа: {response.text}")
            
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Ошибка подключения к API: {e}")
    except requests.exceptions.Timeout as e:
        print(f"❌ Таймаут при подключении к API: {e}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка запроса: {e}")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
    
    return redirect(url_for('tasks_page'))

@app.route('/defects')
def defects_page():
    if 'token' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    # Проверка прав - только инженеры и менеджеры
    if user['role'] not in ['engineer', 'manager', 'admin']:
        print(f"🚫 Нет прав на просмотр дефектов: {user['role']}")
        return redirect(url_for('dashboard'))
    
    print(f"🔧 Страница дефектов для: {user['name']}")
    
    defects = []
    try:
        response = requests.get(f'{API_BASE_URL}/defects', timeout=10)
        print(f"📡 Ответ дефектов на странице: {response.status_code}")
        
        if response.status_code == 200:
            defects_data = response.json()
            print(f"📦 Данные дефектов на странице: {json.dumps(defects_data, indent=2, ensure_ascii=False)}")
            
            if defects_data.get('success'):
                defects = defects_data.get('data', {}).get('defects', [])
                print(f"✅ Найдено дефектов на странице дефектов: {len(defects)}")
            else:
                print(f"⚠️  API вернул success=false на странице дефектов: {defects_data.get('error')}")
        else:
            print(f"❌ Ошибка получения дефектов на странице: {response.status_code} - {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка подключения на странице дефектов")
    except Exception as e:
        print(f"❌ Ошибка при загрузке дефектов: {e}")
    
    return render_template('defects.html', user=user, defects=defects)

@app.route('/tasks')
def tasks_page():
    if 'token' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    print(f"📝 Страница задач для: {user['name']}")
    
    tasks = []
    try:
        response = requests.get(f'{API_BASE_URL}/tasks', timeout=10)
        print(f"📡 Ответ задач на странице: {response.status_code}")
        
        if response.status_code == 200:
            tasks_data = response.json()
            print(f"📦 Данные задач: {json.dumps(tasks_data, indent=2, ensure_ascii=False)}")
            
            if tasks_data.get('success'):
                tasks = tasks_data.get('data', {}).get('tasks', [])
                print(f"✅ Найдено задач на странице задач: {len(tasks)}")
            else:
                print(f"⚠️  API вернул success=false на странице задач: {tasks_data.get('error')}")
        else:
            print(f"❌ Ошибка получения задач на странице: {response.status_code} - {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка подключения на странице задач")
    except Exception as e:
        print(f"❌ Ошибка при загрузке задач: {e}")
    
    return render_template('tasks.html', user=user, tasks=tasks, now=datetime.now())

@app.route('/reports')
def reports_page():
    if 'token' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    # Проверка прав - только менеджеры и руководители
    if user['role'] not in ['manager', 'director', 'admin']:
        print(f"🚫 Нет прав на просмотр отчетов: {user['role']}")
        return redirect(url_for('dashboard'))
    
    print(f"📊 Страница отчетов для: {user['name']}")
    
    reports = []
    try:
        response = requests.get(f'{API_BASE_URL}/reports', timeout=10)
        print(f"📡 Ответ отчетов: {response.status_code}")
        
        if response.status_code == 200:
            reports_data = response.json()
            if reports_data.get('success'):
                reports = reports_data.get('data', {}).get('reports', [])
                print(f"✅ Найдено отчетов: {len(reports)}")
            else:
                print(f"⚠️  API вернул success=false для отчетов: {reports_data.get('error')}")
        else:
            print(f"❌ Ошибка получения отчетов: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка подключения на странице отчетов")
    except Exception as e:
        print(f"❌ Ошибка при загрузке отчетов: {e}")
    
    return render_template('reports.html', user=user, reports=reports)

@app.route('/create_report', methods=['POST'])
def create_report():
    if 'token' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    # Проверка прав - только менеджеры
    if user['role'] not in ['manager', 'admin']:
        print(f"🚫 Нет прав на создание отчетов: {user['role']}")
        return redirect(url_for('dashboard'))
    
    try:
        title = request.form.get('title')
        content = request.form.get('content')
        report_type = request.form.get('report_type', 'general')
        
        print(f"🔄 Создание отчета: {title} пользователем {user['name']}")
        
        response = requests.post(
            f'{API_BASE_URL}/reports',
            json={
                'title': title,
                'content': content,
                'report_type': report_type
            },
            timeout=10
        )
        
        print(f"📡 Ответ создания отчета: {response.status_code}")
        
        if response.status_code == 201:
            print("✅ Отчет успешно создан")
        else:
            error_data = response.json()
            print(f"❌ Ошибка создания отчета: {error_data.get('error', 'Unknown error')}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка подключения при создании отчета")
    except Exception as e:
        print(f"❌ Ошибка запроса создания отчета: {e}")
    
    return redirect(url_for('reports_page'))

@app.route('/update_defect/<defect_id>', methods=['POST'])
def update_defect(defect_id):
    if 'token' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    if user['role'] not in ['engineer', 'manager', 'admin']:
        return redirect(url_for('dashboard'))
    
    try:
        status = request.form.get('status')
        
        print(f"🔄 Обновление дефекта {defect_id} на статус {status}")
        
        response = requests.put(
            f'{API_BASE_URL}/defects/{defect_id}',
            json={'status': status},
            timeout=10
        )
        
        print(f"📡 Ответ обновления дефекта: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Статус дефекта успешно обновлен")
        else:
            error_data = response.json()
            print(f"❌ Ошибка обновления дефекта: {error_data.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Ошибка обновления дефекта: {e}")
    
    return redirect(url_for('defects_page'))

@app.route('/update_task/<task_id>', methods=['POST'])
def update_task(task_id):
    if 'token' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    if user['role'] not in ['manager', 'admin']:
        return redirect(url_for('dashboard'))
    
    try:
        status = request.form.get('status')
        assigned_to = request.form.get('assigned_to', '')
        due_date = request.form.get('due_date', '')
        
        print(f"🔄 Обновление задачи {task_id}: status={status}, assigned_to={assigned_to}, due_date={due_date}")
        
        update_data = {}
        if status:
            update_data['status'] = status
        if assigned_to:
            update_data['assigned_to'] = assigned_to
        if due_date:
            update_data['due_date'] = due_date
        
        response = requests.put(
            f'{API_BASE_URL}/tasks/{task_id}',
            json=update_data,
            timeout=10
        )
        
        print(f"📡 Ответ обновления задачи: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Задача успешно обновлена")
        else:
            error_data = response.json()
            print(f"❌ Ошибка обновления задачи: {error_data.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Ошибка обновления задачи: {e}")
    
    return redirect(url_for('tasks_page'))

@app.route('/logout')
def logout():
    user_name = session.get('user', {}).get('name', 'Unknown')
    print(f"🚪 Выход пользователя: {user_name}")
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    print("🚀 Запуск фронтенд приложения...")
    app.run(host='0.0.0.0', port=5003, debug=True)