from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import hashlib
import datetime
import os
import threading
import time
import openai
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Configure SocketIO with compatible async driver
try:
    # Try to use eventlet first
    import eventlet
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
except (ImportError, AttributeError):
    try:
        # Fallback to threading mode
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    except Exception:
        # Final fallback - disable SocketIO
        socketio = None
        print("Warning: SocketIO disabled due to compatibility issues")

# Database initialization
def init_db():
    conn = sqlite3.connect('coachedual.db')
    c = conn.cursor()

    # Drop existing users table if it exists to recreate with correct schema
    c.execute('DROP TABLE IF EXISTS users')

    # Users table
    c.execute('''CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT NOT NULL,
        birth_date TEXT,
        school TEXT,
        city TEXT,
        avatar TEXT DEFAULT 'default-avatar.png',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_admin BOOLEAN DEFAULT FALSE
    )''')

    # Contests table
    c.execute('''CREATE TABLE IF NOT EXISTS contests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        subject TEXT NOT NULL,
        created_by INTEGER,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        duration INTEGER,
        is_unlimited_time BOOLEAN DEFAULT FALSE,
        is_public BOOLEAN DEFAULT TRUE,
        is_official BOOLEAN DEFAULT FALSE,
        status TEXT DEFAULT 'upcoming',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users (id)
    )''')

    # Contest exercises table
    c.execute('''CREATE TABLE IF NOT EXISTS contest_exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contest_id INTEGER,
        exercise_id INTEGER,
        order_index INTEGER DEFAULT 0,
        points INTEGER DEFAULT 10,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (contest_id) REFERENCES contests (id),
        FOREIGN KEY (exercise_id) REFERENCES exercises (id),
        UNIQUE(contest_id, exercise_id)
    )''')

    # Exercises table
    c.execute('''CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        answer TEXT,
        detailed_solution TEXT,
        hints TEXT,
        subject TEXT NOT NULL,
        difficulty TEXT DEFAULT 'medium',
        points INTEGER DEFAULT 10,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users (id)
    )''')

    # Groups table
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        created_by INTEGER,
        is_private BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users (id)
    )''')

    # Chat messages table
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT NOT NULL,
        response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')

    # User scores table for ranking
    c.execute('''CREATE TABLE IF NOT EXISTS user_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT DEFAULT 'overall',
        score INTEGER DEFAULT 0,
        exercises_solved INTEGER DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        UNIQUE(user_id, subject)
    )''')

    # Exercise submissions table
    c.execute('''CREATE TABLE IF NOT EXISTS exercise_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        exercise_id INTEGER,
        answer TEXT,
        score INTEGER DEFAULT 0,
        is_correct BOOLEAN DEFAULT FALSE,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (exercise_id) REFERENCES exercises (id)
    )''')

    # Contest participants table
    c.execute('''CREATE TABLE IF NOT EXISTS contest_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        contest_id INTEGER,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        score INTEGER DEFAULT 0,
        completed BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (contest_id) REFERENCES contests (id),
        UNIQUE(user_id, contest_id)
    )''')

    # Group members table
    c.execute('''CREATE TABLE IF NOT EXISTS group_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        user_id INTEGER,
        role TEXT DEFAULT 'member',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES groups (id),
        FOREIGN KEY (user_id) REFERENCES users (id),
        UNIQUE(group_id, user_id)
    )''')

    # Group exercises table
    c.execute('''CREATE TABLE IF NOT EXISTS group_exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        exercise_id INTEGER,
        added_by INTEGER,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES groups (id),
        FOREIGN KEY (exercise_id) REFERENCES exercises (id),
        FOREIGN KEY (added_by) REFERENCES users (id),
        UNIQUE(group_id, exercise_id)
    )''')

    # Notifications table
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'info',
        is_read BOOLEAN DEFAULT FALSE,
        data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')

    # Insert default scores for existing users
    c.execute('''INSERT OR IGNORE INTO user_scores (user_id, subject, score, exercises_solved)
                 SELECT id, 'overall', 0, 0 FROM users''')

    conn.commit()
    conn.close()

# Helper functions
def get_db_connection():
    conn = sqlite3.connect('coachedual.db')
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Global variables for real-time updates
ranking_cache = {}
last_update_time = time.time()

# Real-time ranking functions
def get_current_rankings(subject='overall'):
    """Get current rankings for a subject"""
    conn = get_db_connection()

    # First ensure all users have entries in user_scores for the requested subject
    conn.execute('''
        INSERT OR IGNORE INTO user_scores (user_id, subject, score, exercises_solved)
        SELECT id, ?, 0, 0 FROM users
    ''', (subject,))

    if subject == 'overall':
        # For overall, also ensure overall entries exist
        conn.execute('''
            INSERT OR IGNORE INTO user_scores (user_id, subject, score, exercises_solved)
            SELECT id, 'overall', 0, 0 FROM users
        ''')

        rankings = conn.execute('''
            SELECT u.*, COALESCE(us.score, 0) as total_score, 
                   COALESCE(us.exercises_solved, 0) as exercises_solved,
                   ROW_NUMBER() OVER (ORDER BY COALESCE(us.score, 0) DESC, u.created_at ASC) as rank
            FROM users u
            LEFT JOIN user_scores us ON u.id = us.user_id AND us.subject = 'overall'
            ORDER BY COALESCE(us.score, 0) DESC, u.created_at ASC
        ''').fetchall()
    else:
        rankings = conn.execute('''
            SELECT u.*, COALESCE(us.score, 0) as total_score,
                   COALESCE(us.exercises_solved, 0) as exercises_solved,
                   ROW_NUMBER() OVER (ORDER BY COALESCE(us.score, 0) DESC, u.created_at ASC) as rank
            FROM users u
            LEFT JOIN user_scores us ON u.id = us.user_id AND us.subject = ?
            ORDER BY COALESCE(us.score, 0) DESC, u.created_at ASC
        ''', (subject,)).fetchall()

    conn.commit()
    conn.close()
    return rankings

def auto_save_data():
    """Auto save ranking data to database every second"""
    global last_update_time
    while True:
        try:
            current_time = time.time()

            # Update timestamp in database
            conn = get_db_connection()
            conn.execute('''
                UPDATE user_scores 
                SET last_updated = CURRENT_TIMESTAMP 
                WHERE last_updated < datetime('now', '-1 seconds')
            ''')
            conn.commit()
            conn.close()

            # Broadcast ranking updates
            broadcast_ranking_update()

            last_update_time = current_time

        except Exception as e:
            print(f"Auto save error: {e}")

        time.sleep(1)  # Update every second

def start_background_tasks():
    """Start background tasks for real-time updates"""
    # Start auto-save thread
    save_thread = threading.Thread(target=auto_save_data, daemon=True)
    save_thread.start()

    # Start periodic ranking broadcast
    broadcast_thread = threading.Thread(target=periodic_ranking_broadcast, daemon=True)
    broadcast_thread.start()

def periodic_ranking_broadcast():
    """Broadcast ranking updates every second"""
    while True:
        try:
            broadcast_ranking_update()
            time.sleep(1)
        except Exception as e:
            print(f"Broadcast error: {e}")
            time.sleep(1)

def update_user_score(user_id, subject, score_change, exercises_change=0):
    """Update user score and broadcast to all clients"""
    conn = get_db_connection()

    # Update or insert user score
    conn.execute('''
        INSERT OR REPLACE INTO user_scores (user_id, subject, score, exercises_solved, last_updated)
        VALUES (?, ?, 
                COALESCE((SELECT score FROM user_scores WHERE user_id = ? AND subject = ?), 0) + ?,
                COALESCE((SELECT exercises_solved FROM user_scores WHERE user_id = ? AND subject = ?), 0) + ?,
                CURRENT_TIMESTAMP)
    ''', (user_id, subject, user_id, subject, score_change, user_id, subject, exercises_change))

    # Also update overall score
    if subject != 'overall':
        conn.execute('''
            INSERT OR REPLACE INTO user_scores (user_id, subject, score, exercises_solved, last_updated)
            VALUES (?, 'overall', 
                    COALESCE((SELECT score FROM user_scores WHERE user_id = ? AND subject = 'overall'), 0) + ?,
                    COALESCE((SELECT exercises_solved FROM user_scores WHERE user_id = ? AND subject = 'overall'), 0) + ?,
                    CURRENT_TIMESTAMP)
        ''', (user_id, user_id, score_change, user_id, exercises_change))

    conn.commit()
    conn.close()

    # Broadcast updated rankings to all clients
    broadcast_ranking_update()

def broadcast_ranking_update():
    """Broadcast ranking updates to all connected clients"""
    if not socketio:
        return  # Skip if SocketIO is disabled

    subjects = ['overall', 'math', 'physics', 'chemistry', 'biology', 'literature', 'english']

    for subject in subjects:
        rankings = get_current_rankings(subject)
        ranking_data = []

        for ranking in rankings:
            ranking_data.append({
                'rank': ranking['rank'],
                'username': ranking['username'],
                'full_name': ranking['full_name'],
                'school': ranking['school'],
                'city': ranking['city'],
                'score': ranking['total_score'],
                'exercises_solved': ranking['exercises_solved']
            })

        socketio.emit('ranking_update', {
            'subject': subject,
            'rankings': ranking_data
        }, room='ranking_room')

# SocketIO Events
if socketio:
    @socketio.on('connect')
    def handle_connect():
        if 'user_id' in session:
            join_room('ranking_room')
            emit('connected', {'data': 'Connected to ranking updates'})

    @socketio.on('disconnect')
    def handle_disconnect():
        if 'user_id' in session:
            leave_room('ranking_room')

    @socketio.on('join_ranking')
    def handle_join_ranking():
        if 'user_id' in session:
            join_room('ranking_room')
            # Send current rankings
            broadcast_ranking_update()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form['username_or_email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE (username = ? OR email = ?) AND password = ?',
            (username_or_email, username_or_email, hash_password(password))
        ).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng!', 'error')

    return render_template('login.html')

@app.route('/register/step1', methods=['GET', 'POST'])
def register_step1():
    if request.method == 'POST':
        session['reg_full_name'] = request.form['full_name']
        session['reg_email'] = request.form['email']
        session['reg_birth_date'] = request.form['birth_date']
        return redirect(url_for('register_step2'))

    return render_template('register_step1.html')

@app.route('/register/step2', methods=['GET', 'POST'])
def register_step2():
    if request.method == 'POST':
        session['reg_username'] = request.form['username']
        session['reg_password'] = request.form['password']
        session['reg_school'] = request.form['school_name']  # Fixed field name
        session['reg_city'] = request.form['city']
        return redirect(url_for('register_step3'))

    return render_template('register_step2.html')

@app.route('/register/step3', methods=['GET', 'POST'])
def register_step3():
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO users (username, email, password, full_name, birth_date, school, city) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (session['reg_username'], session['reg_email'], hash_password(session['reg_password']),
                 session['reg_full_name'], session['reg_birth_date'], session['reg_school'], session['reg_city'])
            )
            conn.commit()
            conn.close()

            # Clear registration session data
            for key in list(session.keys()):
                if key.startswith('reg_'):
                    session.pop(key)

            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Tên đăng nhập hoặc email đã tồn tại!', 'error')

    return render_template('register_step3.html')

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        message = request.form['message']

        try:
            # Configure OpenAI
            openai.api_key = os.getenv('OPENAI_API_KEY')

            if openai.api_key:
                # Call OpenAI API
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Bạn là CoachAI, một trợ lý giáo dục thông minh. Hãy trả lời các câu hỏi về giáo dục, học tập và tạo bài tập bằng tiếng Việt một cách chi tiết và hữu ích."},
                        {"role": "user", "content": message}
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )
                ai_response = response.choices[0].message.content
            else:
                # Fallback response nếu không có API key
                ai_response = generate_fallback_response(message)
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            ai_response = generate_fallback_response(message)

        # Save to database
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO chat_messages (user_id, message, response) VALUES (?, ?, ?)',
            (session['user_id'], message, ai_response)
        )
        conn.commit()
        conn.close()

        return jsonify({'response': ai_response})

    # Get chat history
    conn = get_db_connection()
    messages = conn.execute(
        'SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 10',
        (session['user_id'],)
    ).fetchall()
    conn.close()

    return render_template('chatbot.html', messages=messages)

def generate_fallback_response(message):
    """Generate fallback response when OpenAI is not available"""
    message_lower = message.lower()

    if 'toán' in message_lower or 'math' in message_lower:
        return """Tôi có thể giúp bạn với các bài toán:

**Ví dụ bài tập Toán:**
- Giải phương trình bậc hai: x² - 5x + 6 = 0
- Tính đạo hàm của hàm số y = 2x³ + 3x - 1
- Bài toán hình học: Tính diện tích tam giác có ba cạnh 3, 4, 5

Bạn muốn tôi giải thích chi tiết bài nào không?"""

    elif 'văn' in message_lower or 'literature' in message_lower:
        return """Tôi có thể hỗ trợ bạn về Văn học:

**Phân tích tác phẩm:**
- Chí Phèo (Nam Cao): Phản ánh hiện thực xã hội
- Tắt đèn (Ngô Tất Tố): Tình yêu và gia đình
- Vợ nhặt (Kim Lân): Lòng nhân ái

**Kỹ năng viết:**
- Cách viết bài văn nghị luận
- Phương pháp phân tích nhân vật
- Cách làm bài thi văn

Bạn cần hỗ trợ gì cụ thể?"""

    else:
        return f"""Tôi hiểu bạn muốn hỏi về: "{message}"

Tôi có thể giúp bạn:
• **Tạo bài tập** cho các môn Toán, Văn, Hóa, Lý, Sinh, Anh
• **Giải thích khái niệm** khó hiểu  
• **Soạn đề thi** theo yêu cầu
• **Hướng dẫn phương pháp học**

Hãy cho tôi biết cụ thể hơn về môn học và nội dung bạn quan tâm!"""

@app.route('/contests')
def contests():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    status_filter = request.args.get('status', 'all')
    subject_filter = request.args.get('subject', '')

    conn = get_db_connection()

    # Base query
    query = '''
        SELECT c.*, u.username as creator_name,
               CASE 
                   WHEN datetime('now') < c.start_time THEN 'upcoming'
                   WHEN datetime('now') BETWEEN c.start_time AND c.end_time THEN 'ongoing'
                   ELSE 'finished'
               END as current_status,
               COUNT(cp.user_id) as participant_count
        FROM contests c 
        JOIN users u ON c.created_by = u.id
        LEFT JOIN contest_participants cp ON c.id = cp.contest_id
    '''

    conditions = []
    params = []

    if status_filter != 'all':
        if status_filter == 'upcoming':
            conditions.append("datetime('now') < c.start_time")
        elif status_filter == 'ongoing':
            conditions.append("datetime('now') BETWEEN c.start_time AND c.end_time")
        elif status_filter == 'finished':
            conditions.append("datetime('now') > c.end_time")

    if subject_filter:
        conditions.append("c.subject = ?")
        params.append(subject_filter)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " GROUP BY c.id ORDER BY c.created_at DESC"

    contests = conn.execute(query, params).fetchall()

    # Get subject list for filter
    subjects = [
        {'id': 'math', 'name': 'Toán học'},
        {'id': 'physics', 'name': 'Vật lý'},
        {'id': 'chemistry', 'name': 'Hóa học'},
        {'id': 'biology', 'name': 'Sinh học'},
        {'id': 'literature', 'name': 'Văn học'},
        {'id': 'english', 'name': 'Tiếng Anh'}
    ]

    conn.close()

    return render_template('contests.html', contests=contests, subjects=subjects, 
                         current_status=status_filter, current_subject=subject_filter)

@app.route('/create_contest', methods=['GET', 'POST'])
def create_contest():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        is_unlimited = 'is_unlimited_time' in request.form
        duration = None if is_unlimited else request.form.get('duration')

        conn = get_db_connection()
        cursor = conn.cursor() # Use cursor for lastrowid
        cursor.execute(
            '''INSERT INTO contests 
               (title, description, subject, created_by, start_time, end_time, 
                duration, is_unlimited_time, is_public, is_official) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (request.form['title'], request.form['description'], request.form['subject'],
             session['user_id'], request.form['start_time'], request.form['end_time'],
             duration, is_unlimited, 'is_public' in request.form, 'is_official' in request.form)
        )
        contest_id = cursor.lastrowid

        # Add selected exercises to contest
        selected_exercises = request.form.getlist('exercises[]')
        for i, exercise_id in enumerate(selected_exercises):
            cursor.execute(
                'INSERT INTO contest_exercises (contest_id, exercise_id, order_index) VALUES (?, ?, ?)',
                (contest_id, exercise_id, i + 1)
            )

        conn.commit()
        conn.close()

        flash('Tạo cuộc thi thành công!', 'success')
        return redirect(url_for('contests'))

    # Get exercises for selection
    conn = get_db_connection()
    exercises = conn.execute(
        'SELECT e.*, u.username as author_name FROM exercises e JOIN users u ON e.created_by = u.id ORDER BY e.created_at DESC'
    ).fetchall()
    conn.close()

    subjects = [
        {'id': 'math', 'name': 'Toán học'},
        {'id': 'physics', 'name': 'Vật lý'},
        {'id': 'chemistry', 'name': 'Hóa học'},
        {'id': 'biology', 'name': 'Sinh học'},
        {'id': 'literature', 'name': 'Văn học'},
        {'id': 'english', 'name': 'Tiếng Anh'}
    ]

    return render_template('create_contest.html', exercises=exercises, subjects=subjects)

@app.route('/exercises')
def exercises():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    exercises = conn.execute(
        'SELECT e.*, u.username FROM exercises e JOIN users u ON e.created_by = u.id ORDER BY e.created_at DESC'
    ).fetchall()
    conn.close()

    return render_template('exercises.html', exercises=exercises)

@app.route('/create_exercise', methods=['GET', 'POST'])
def create_exercise():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor() # Use cursor for lastrowid and other operations

        title = request.form['title']
        content = request.form['content']
        answer = request.form['answer']
        detailed_solution = request.form.get('detailed_solution', '')
        hints = request.form.get('hints', '')
        subject = request.form['subject']
        difficulty = request.form['difficulty']
        points = int(request.form['points'])

        try:
            # Check if columns exist and add them if they don't
            cursor.execute("PRAGMA table_info(exercises)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'detailed_solution' not in columns:
                cursor.execute('ALTER TABLE exercises ADD COLUMN detailed_solution TEXT')
            if 'hints' not in columns:
                cursor.execute('ALTER TABLE exercises ADD COLUMN hints TEXT')
            
            # Ensure created_by is also present
            if 'created_by' not in columns:
                 cursor.execute('ALTER TABLE exercises ADD COLUMN created_by INTEGER')
                 cursor.execute('UPDATE exercises SET created_by = -1 WHERE created_by IS NULL') # Set default for existing rows if necessary

            # Ensure user_id is not used in the INSERT statement, use created_by instead.
            # Correcting the column name in the INSERT statement to match the schema.
            cursor.execute('''
                INSERT INTO exercises (title, content, answer, detailed_solution, hints, subject, difficulty, points, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, content, answer, detailed_solution, hints, subject, difficulty, points, session['user_id'], datetime.datetime.now()))

            conn.commit()
            flash('Bài tập đã được tạo thành công!', 'success')
            return redirect(url_for('exercises'))
        except Exception as e:
            conn.rollback() # Rollback on error
            flash(f'Có lỗi xảy ra khi tạo bài tập: {str(e)}', 'error')
            # Re-render the form to show the error
            return render_template('create_exercise.html')

    # If GET request, render the form
    return render_template('create_exercise.html')

@app.route('/groups')
def groups():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    groups = conn.execute('''
        SELECT g.*, u.username as creator_name, 
               COUNT(gm.user_id) as member_count
        FROM groups g 
        LEFT JOIN users u ON g.created_by = u.id 
        LEFT JOIN group_members gm ON g.id = gm.group_id
        GROUP BY g.id, u.username
        ORDER BY g.created_at DESC
    ''').fetchall()
    conn.close()

    return render_template('groups.html', groups=groups)

@app.route('/create_group', methods=['GET', 'POST'])
def create_group():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        is_private = request.form.get('privacy_type') == 'private'

        conn = get_db_connection()
        cursor = conn.cursor() # Use cursor for lastrowid
        cursor.execute(
            'INSERT INTO groups (name, description, created_by, is_private) VALUES (?, ?, ?, ?)',
            (request.form['name'], request.form['description'], session['user_id'], is_private)
        )
        group_id = cursor.lastrowid

        # Add creator as first member
        cursor.execute(
            'INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
            (group_id, session['user_id'], 'owner')
        )
        conn.commit()
        conn.close()

        flash('Tạo nhóm thành công!', 'success')
        return redirect(url_for('groups'))

    return render_template('create_group.html')

@app.route('/ranking')
def ranking():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    subject = request.args.get('subject', 'overall')

    # Get rankings for selected subject
    rankings = get_current_rankings(subject)

    # Create subjects list for filter
    subjects = [
        {'id': 'math', 'name': 'Toán học'},
        {'id': 'physics', 'name': 'Vật lý'},
        {'id': 'chemistry', 'name': 'Hóa học'},
        {'id': 'biology', 'name': 'Sinh học'},
        {'id': 'literature', 'name': 'Văn học'},
        {'id': 'english', 'name': 'Tiếng Anh'}
    ]

    return render_template('ranking.html', overall_ranking=rankings, subjects=subjects, current_subject=subject)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

    # Get user scores by subject
    user_scores = conn.execute('''
        SELECT subject, score, exercises_solved FROM user_scores 
        WHERE user_id = ? AND subject != 'overall'
    ''', (session['user_id'],)).fetchall()

    # Get user's exercises
    user_exercises = conn.execute('''
        SELECT * FROM exercises WHERE created_by = ? ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()

    # Get user ranking
    user_ranking = conn.execute('''
        SELECT rank FROM (
            SELECT u.id, ROW_NUMBER() OVER (ORDER BY COALESCE(us.score, 0) DESC, u.created_at ASC) as rank
            FROM users u
            LEFT JOIN user_scores us ON u.id = us.user_id AND us.subject = 'overall'
        ) WHERE id = ?
    ''', (session['user_id'],)).fetchone()

    conn.close()

    return render_template('profile.html', user=user, user_scores=user_scores, 
                         user_exercises=user_exercises, user_ranking=user_ranking)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

    if request.method == 'POST':
        try:
            conn.execute('''
                UPDATE users SET 
                full_name = ?, email = ?, birth_date = ?, school = ?, city = ?
                WHERE id = ?
            ''', (
                request.form['full_name'],
                request.form['email'], 
                request.form['birth_date'],
                request.form['school'],
                request.form['city'],
                session['user_id']
            ))
            conn.commit()
            flash('Cập nhật thông tin thành công!', 'success')
            return redirect(url_for('profile'))
        except sqlite3.IntegrityError:
            flash('Email đã tồn tại!', 'error')

    conn.close()
    return render_template('edit_profile.html', user=user)

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})

    if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        # Create avatars directory if it doesn't exist
        avatar_dir = os.path.join('static', 'img', 'avatars')
        os.makedirs(avatar_dir, exist_ok=True)

        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        avatar_filename = f"avatar_{session['user_id']}_{int(time.time())}.{file_extension}"
        file_path = os.path.join(avatar_dir, avatar_filename)

        try:
            # Save the file
            file.save(file_path)

            # Update database with new avatar filename
            conn = get_db_connection()
            conn.execute('UPDATE users SET avatar = ? WHERE id = ?', 
                        (f'avatars/{avatar_filename}', session['user_id']))
            conn.commit()
            conn.close()

            return jsonify({
                'success': True, 
                'message': 'Avatar uploaded successfully',
                'avatar_url': url_for('static', filename=f'img/avatars/{avatar_filename}')
            })
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error saving file: {str(e)}'})

    return jsonify({'success': False, 'message': 'Invalid file type'})

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html')

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    # Get all notifications for user
    all_notifications = conn.execute('''
        SELECT * FROM notifications 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()

    # Get unread notifications
    unread_notifications = conn.execute('''
        SELECT * FROM notifications 
        WHERE user_id = ? AND is_read = FALSE 
        ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()

    # Get notifications by type
    contest_notifications = conn.execute('''
        SELECT * FROM notifications 
        WHERE user_id = ? AND type = 'contest' 
        ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()

    group_notifications = conn.execute('''
        SELECT * FROM notifications 
        WHERE user_id = ? AND type = 'group' 
        ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()

    conn.close()

    return render_template('notifications.html', 
                         all_notifications=all_notifications,
                         unread_notifications=unread_notifications,
                         contest_notifications=contest_notifications,
                         group_notifications=group_notifications)

@app.route('/api/notification/<int:notification_id>')
def get_notification(notification_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    conn = get_db_connection()
    notification = conn.execute('''
        SELECT * FROM notifications 
        WHERE id = ? AND user_id = ?
    ''', (notification_id, session['user_id'])).fetchone()
    conn.close()

    if not notification:
        return jsonify({'success': False, 'message': 'Notification not found'})

    return jsonify({
        'success': True,
        'notification': {
            'id': notification['id'],
            'title': notification['title'],
            'message': notification['message'],
            'type': notification['type'],
            'is_read': notification['is_read'],
            'data': json.loads(notification['data']) if notification['data'] else None,
            'created_at': notification['created_at']
        }
    })

@app.route('/api/mark_notification_read', methods=['POST'])
def mark_notification_read():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    data = request.json
    notification_id = data.get('notification_id')

    conn = get_db_connection()
    conn.execute('''
        UPDATE notifications 
        SET is_read = TRUE 
        WHERE id = ? AND user_id = ?
    ''', (notification_id, session['user_id']))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Notification marked as read'})

@app.route('/api/mark_all_notifications_read', methods=['POST'])
def mark_all_notifications_read():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    conn = get_db_connection()
    conn.execute('''
        UPDATE notifications 
        SET is_read = TRUE 
        WHERE user_id = ?
    ''', (session['user_id'],))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'All notifications marked as read'})

def create_notification(user_id, title, message, notification_type='info', data=None):
    """Create a new notification for a user"""
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO notifications (user_id, title, message, type, data)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, title, message, notification_type, json.dumps(data) if data else None))
    conn.commit()
    conn.close()

    # Emit to user via SocketIO if available
    if socketio:
        socketio.emit('new_notification', {
            'title': title,
            'message': message,
            'type': notification_type
        }, room=f'user_{user_id}')

@app.route('/search')
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    query = request.args.get('q', '')
    results = []

    if query:
        conn = get_db_connection()
        # Search in contests, exercises, and groups
        contests = conn.execute(
            'SELECT "contest" as type, id, title as name, description FROM contests WHERE title LIKE ? OR description LIKE ?',
            (f'%{query}%', f'%{query}%')
        ).fetchall()

        exercises = conn.execute(
            'SELECT "exercise" as type, id, title as name, content as description FROM exercises WHERE title LIKE ? OR content LIKE ?',
            (f'%{query}%', f'%{query}%')
        ).fetchall()

        groups = conn.execute(
            'SELECT "group" as type, id, name, description FROM groups WHERE name LIKE ? OR description LIKE ?',
            (f'%{query}%', f'%{query}%')
        ).fetchall()

        results = list(contests) + list(exercises) + list(groups)
        conn.close()

    return render_template('search_results.html', results=results, query=query)

@app.route('/contest/<int:contest_id>')
def contest_detail(contest_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    contest = conn.execute(
        'SELECT c.*, u.username as creator_name FROM contests c JOIN users u ON c.created_by = u.id WHERE c.id = ?',
        (contest_id,)
    ).fetchone()
    conn.close()

    if not contest:
        return render_template('404.html'), 404

    return render_template('contest_detail.html', contest=contest)

@app.route('/exercise/<int:exercise_id>')
def exercise_detail(exercise_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    exercise = conn.execute(
        'SELECT e.*, u.username as author_name FROM exercises e JOIN users u ON e.created_by = u.id WHERE e.id = ?',
        (exercise_id,)
    ).fetchone()
    conn.close()

    if not exercise:
        return render_template('404.html'), 404

    return render_template('exercise_detail.html', exercise=exercise)

@app.route('/group/<int:group_id>')
def group_detail(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    # Get group info with creator name
    group = conn.execute('''
        SELECT g.*, u.username as creator_name, u.full_name as creator_full_name
        FROM groups g 
        JOIN users u ON g.created_by = u.id 
        WHERE g.id = ?
    ''', (group_id,)).fetchone()

    if not group:
        conn.close()
        return render_template('404.html'), 404

    # Get group members
    members = conn.execute('''
        SELECT u.*, gm.role, gm.joined_at,
               COALESCE(us.score, 0) as total_score
        FROM group_members gm
        JOIN users u ON gm.user_id = u.id
        LEFT JOIN user_scores us ON u.id = us.user_id AND us.subject = 'overall'
        WHERE gm.group_id = ?
        ORDER BY 
            CASE gm.role 
                WHEN 'owner' THEN 1 
                WHEN 'admin' THEN 2 
                ELSE 3 
            END,
            COALESCE(us.score, 0) DESC
    ''', (group_id,)).fetchall()

    # Get group exercises
    group_exercises = conn.execute('''
        SELECT e.*, u.username as author_name
        FROM exercises e
        JOIN users u ON e.created_by = u.id
        JOIN group_exercises ge ON e.id = ge.exercise_id
        WHERE ge.group_id = ?
        ORDER BY e.created_at DESC
    ''', (group_id,)).fetchall()

    # Check if current user is member
    is_member = conn.execute('''
        SELECT 1 FROM group_members 
        WHERE group_id = ? AND user_id = ?
    ''', (group_id, session['user_id'])).fetchone()

    # Get member count
    member_count = len(members)

    conn.close()

    return render_template('group_detail.html', 
                         group=group, 
                         members=members, 
                         group_exercises=group_exercises,
                         is_member=is_member,
                         member_count=member_count)

@app.route('/api/exercise/<int:exercise_id>')
def api_exercise_detail(exercise_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    conn = get_db_connection()
    exercise = conn.execute(
        'SELECT * FROM exercises WHERE id = ?', (exercise_id,)
    ).fetchone()
    conn.close()

    if not exercise:
        return jsonify({'success': False, 'message': 'Exercise not found'})

    return jsonify({
        'success': True,
        'id': exercise['id'],
        'title': exercise['title'],
        'content': exercise['content'],
        'answer': exercise['answer'],
        'detailed_solution': exercise['detailed_solution'],
        'hints': exercise['hints'],
        'subject': exercise['subject'],
        'difficulty': exercise['difficulty'],
        'points': exercise['points']
    })

@app.route('/api/submit_exercise', methods=['POST'])
def submit_exercise():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    data = request.json
    exercise_id = data.get('exercise_id')
    answer = data.get('answer', '')

    if not exercise_id:
        return jsonify({'success': False, 'message': 'Exercise ID required'})

    conn = get_db_connection()
    exercise = conn.execute('SELECT * FROM exercises WHERE id = ?', (exercise_id,)).fetchone()

    if not exercise:
        conn.close()
        return jsonify({'success': False, 'message': 'Exercise not found'})

    # Simple scoring logic - in real app, this would be more sophisticated
    # Compare submitted answer with the correct answer from the database
    is_correct = answer.strip().lower() == exercise['answer'].strip().lower()
    score = exercise['points'] if is_correct else 0

    # Update user's score
    if is_correct:
        update_user_score(session['user_id'], exercise['subject'], score, 1)

    # Save submission
    conn.execute('''
        INSERT INTO exercise_submissions (user_id, exercise_id, answer, score, is_correct)
        VALUES (?, ?, ?, ?, ?)
    ''', (session['user_id'], exercise_id, answer, score, is_correct))
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'is_correct': is_correct,
        'score': score,
        'message': 'Chính xác! Bạn được {} điểm!'.format(score) if is_correct else 'Chưa đúng, hãy thử lại!',
        'exercise': dict(exercise) # Include exercise details for frontend to display solution
    })

@app.route('/api/join_contest', methods=['POST'])
def join_contest():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    data = request.json
    contest_id = data.get('contest_id')

    if not contest_id:
        return jsonify({'success': False, 'message': 'Contest ID required'})

    conn = get_db_connection()

    # Check if user already joined
    existing = conn.execute(
        'SELECT * FROM contest_participants WHERE user_id = ? AND contest_id = ?',
        (session['user_id'], contest_id)
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({'success': False, 'message': 'Bạn đã tham gia cuộc thi này rồi'})

    # Add user to contest
    conn.execute(
        'INSERT INTO contest_participants (user_id, contest_id, joined_at) VALUES (?, ?, CURRENT_TIMESTAMP)',
        (session['user_id'], contest_id)
    )
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Tham gia cuộc thi thành công!'})

@app.route('/api/add_score', methods=['POST'])
def add_score():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    data = request.json
    subject = data.get('subject', 'overall')
    score = data.get('score', 10)

    update_user_score(session['user_id'], subject, score, 1)

    return jsonify({'success': True, 'message': f'Added {score} points'})

@app.route('/api/join_group', methods=['POST'])
def join_group():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    data = request.json
    group_id = data.get('group_id')

    if not group_id:
        return jsonify({'success': False, 'message': 'Group ID required'})

    conn = get_db_connection()

    # Check if group exists
    group = conn.execute('SELECT * FROM groups WHERE id = ?', (group_id,)).fetchone()
    if not group:
        conn.close()
        return jsonify({'success': False, 'message': 'Nhóm không tồn tại'})

    # Check if user already joined
    existing = conn.execute(
        'SELECT * FROM group_members WHERE group_id = ? AND user_id = ?',
        (group_id, session['user_id'])
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({'success': False, 'message': 'Bạn đã là thành viên của nhóm này'})

    # Add user to group
    try:
        conn.execute(
            'INSERT INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)',
            (group_id, session['user_id'], 'member')
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Tham gia nhóm thành công!'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': 'Có lỗi xảy ra'})

@app.route('/api/leave_group', methods=['POST'])
def leave_group():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    data = request.json
    group_id = data.get('group_id')

    if not group_id:
        return jsonify({'success': False, 'message': 'Group ID required'})

    conn = get_db_connection()

    # Check if user is the owner
    group = conn.execute(
        'SELECT created_by FROM groups WHERE id = ?', (group_id,)
    ).fetchone()

    if group and group['created_by'] == session['user_id']:
        conn.close()
        return jsonify({'success': False, 'message': 'Chủ nhóm không thể rời nhóm'})

    # Remove user from group
    conn.execute(
        'DELETE FROM group_members WHERE group_id = ? AND user_id = ?',
        (group_id, session['user_id'])
    )
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Đã rời nhóm thành công'})

@app.route('/api/auto_save', methods=['POST'])
def auto_save():
    """API endpoint for auto-saving data"""
    try:
        conn = get_db_connection()

        # Update all user scores timestamps
        conn.execute('''
            UPDATE user_scores 
            SET last_updated = CURRENT_TIMESTAMP
        ''')

        # Save any pending changes
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'timestamp': datetime.datetime.now().isoformat()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/delete_exercise/<int:exercise_id>', methods=['DELETE'])
def delete_exercise(exercise_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    conn = get_db_connection()
    exercise = conn.execute(
        'SELECT created_by FROM exercises WHERE id = ?', (exercise_id,)
    ).fetchone()

    if not exercise:
        conn.close()
        return jsonify({'success': False, 'message': 'Exercise not found'})

    if exercise['created_by'] != session['user_id'] and not session.get('is_admin'):
        conn.close()
        return jsonify({'success': False, 'message': 'Permission denied'})

    # Delete exercise and related data
    conn.execute('DELETE FROM exercise_submissions WHERE exercise_id = ?', (exercise_id,))
    conn.execute('DELETE FROM contest_exercises WHERE exercise_id = ?', (exercise_id,))
    conn.execute('DELETE FROM group_exercises WHERE exercise_id = ?', (exercise_id,))
    conn.execute('DELETE FROM exercises WHERE id = ?', (exercise_id,))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Exercise deleted successfully'})

@app.route('/api/edit_exercise/<int:exercise_id>', methods=['PUT'])
def edit_exercise(exercise_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    data = request.json

    conn = get_db_connection()
    exercise = conn.execute(
        'SELECT created_by FROM exercises WHERE id = ?', (exercise_id,)
    ).fetchone()

    if not exercise:
        conn.close()
        return jsonify({'success': False, 'message': 'Exercise not found'})

    if exercise['created_by'] != session['user_id'] and not session.get('is_admin'):
        conn.close()
        return jsonify({'success': False, 'message': 'Permission denied'})

    conn.execute('''
        UPDATE exercises 
        SET title = ?, content = ?, answer = ?, detailed_solution = ?, hints = ?, subject = ?, difficulty = ?, points = ?
        WHERE id = ?
    ''', (data['title'], data['content'], data['answer'], data['detailed_solution'], data['hints'], 
          data['subject'], data['difficulty'], data['points'], exercise_id))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Exercise updated successfully'})

@app.route('/api/delete_contest/<int:contest_id>', methods=['DELETE'])
def delete_contest(contest_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})

    conn = get_db_connection()
    contest = conn.execute(
        'SELECT created_by FROM contests WHERE id = ?', (contest_id,)
    ).fetchone()

    if not contest:
        conn.close()
        return jsonify({'success': False, 'message': 'Contest not found'})

    if contest['created_by'] != session['user_id'] and not session.get('is_admin'):
        conn.close()
        return jsonify({'success': False, 'message': 'Permission denied'})

    # Delete contest and related data
    conn.execute('DELETE FROM contest_participants WHERE contest_id = ?', (contest_id,))
    conn.execute('DELETE FROM contest_exercises WHERE contest_id = ?', (contest_id,))
    conn.execute('DELETE FROM contests WHERE id = ?', (contest_id,))

    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Contest deleted successfully'})

@app.route('/logout')
def logout():
    session.clear()
    flash('Đã đăng xuất thành công!', 'success')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    init_db()
    start_background_tasks()
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    print(f"Starting CoachEduAI server on {host}:{port}")
    print(f"Debug mode: {debug}")

    if socketio:
        try:
            socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
        except Exception as e:
            print(f"SocketIO error: {e}")
            print("Falling back to regular Flask server...")
            app.run(host=host, port=port, debug=debug)
    else:
        print("Starting regular Flask server (SocketIO disabled)...")
        app.run(host=host, port=port, debug=debug)