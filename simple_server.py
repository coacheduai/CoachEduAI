#!/usr/bin/env python3
"""
CoachEduAI Simple Server - Basic Flask server without SocketIO
This version works reliably across different Python versions
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import hashlib
import datetime
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

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
        is_public BOOLEAN DEFAULT TRUE,
        is_official BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users (id)
    )''')
    
    # Exercises table
    c.execute('''CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
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
        session['reg_school'] = request.form['school_name']
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
        # Simulate AI response
        response = f"Đây là phản hồi AI cho câu hỏi: {message}"
        
        # Save to database
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO chat_messages (user_id, message, response) VALUES (?, ?, ?)',
            (session['user_id'], message, response)
        )
        conn.commit()
        conn.close()
        
        return jsonify({'response': response})
    
    # Get chat history
    conn = get_db_connection()
    messages = conn.execute(
        'SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 10',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    
    return render_template('chatbot.html', messages=messages)

@app.route('/contests')
def contests():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    contests = conn.execute(
        'SELECT c.*, u.username FROM contests c JOIN users u ON c.created_by = u.id ORDER BY c.created_at DESC'
    ).fetchall()
    conn.close()
    
    return render_template('contests.html', contests=contests)

@app.route('/create_contest', methods=['GET', 'POST'])
def create_contest():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO contests (title, description, subject, created_by, start_time, end_time, duration, is_public) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (request.form['title'], request.form['description'], request.form['subject'],
             session['user_id'], request.form['start_time'], request.form['end_time'],
             request.form['duration'], 'is_public' in request.form)
        )
        conn.commit()
        conn.close()
        
        flash('Tạo cuộc thi thành công!', 'success')
        return redirect(url_for('contests'))
    
    return render_template('create_contest.html')

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
        conn.execute(
            'INSERT INTO exercises (title, content, subject, difficulty, points, created_by) VALUES (?, ?, ?, ?, ?, ?)',
            (request.form['title'], request.form['content'], request.form['subject'],
             request.form['difficulty'], request.form['points'], session['user_id'])
        )
        conn.commit()
        conn.close()
        
        flash('Tạo bài tập thành công!', 'success')
        return redirect(url_for('exercises'))
    
    return render_template('create_exercise.html')

@app.route('/groups')
def groups():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    groups = conn.execute(
        'SELECT g.*, u.username FROM groups g JOIN users u ON g.created_by = u.id ORDER BY g.created_at DESC'
    ).fetchall()
    conn.close()
    
    return render_template('groups.html', groups=groups)

@app.route('/create_group', methods=['GET', 'POST'])
def create_group():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO groups (name, description, created_by, is_private) VALUES (?, ?, ?, ?)',
            (request.form['name'], request.form['description'], session['user_id'], 'is_private' in request.form)
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

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html')

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('notifications.html')

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
        'SELECT c.*, u.username FROM contests c JOIN users u ON c.created_by = u.id WHERE c.id = ?',
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
        'SELECT e.*, u.username FROM exercises e JOIN users u ON e.created_by = u.id WHERE e.id = ?',
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
    group = conn.execute(
        'SELECT g.*, u.username FROM groups g JOIN users u ON g.created_by = u.id WHERE g.id = ?',
        (group_id,)
    ).fetchone()
    conn.close()
    
    if not group:
        return render_template('404.html'), 404
    
    return render_template('group_detail.html', group=group)

@app.route('/api/add_score', methods=['POST'])
def add_score():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    data = request.json
    subject = data.get('subject', 'overall')
    score = data.get('score', 10)
    
    conn = get_db_connection()
    
    # Update or insert user score
    conn.execute('''
        INSERT OR REPLACE INTO user_scores (user_id, subject, score, exercises_solved, last_updated)
        VALUES (?, ?, 
                COALESCE((SELECT score FROM user_scores WHERE user_id = ? AND subject = ?), 0) + ?,
                COALESCE((SELECT exercises_solved FROM user_scores WHERE user_id = ? AND subject = ?), 0) + 1,
                CURRENT_TIMESTAMP)
    ''', (session['user_id'], subject, session['user_id'], subject, score, session['user_id'], subject))
    
    # Also update overall score
    if subject != 'overall':
        conn.execute('''
            INSERT OR REPLACE INTO user_scores (user_id, subject, score, exercises_solved, last_updated)
            VALUES (?, 'overall', 
                    COALESCE((SELECT score FROM user_scores WHERE user_id = ? AND subject = 'overall'), 0) + ?,
                    COALESCE((SELECT exercises_solved FROM user_scores WHERE user_id = ? AND subject = 'overall'), 0) + 1,
                    CURRENT_TIMESTAMP)
        ''', (session['user_id'], session['user_id'], score, session['user_id']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': f'Added {score} points'})

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
        # For demo purposes, we'll just use the default avatar
        # In a real app, you'd save the file and update the database
        return jsonify({'success': True, 'message': 'Avatar uploaded successfully'})
    
    return jsonify({'success': False, 'message': 'Invalid file type'})

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
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print(f"🚀 Starting CoachEduAI Simple Server on {host}:{port}")
    print(f"🔧 Debug mode: {debug}")
    print(f"🌐 Open your browser and go to: http://localhost:{port}")
    print("⏹️  Press Ctrl+C to stop the server")
    
    app.run(host=host, port=port, debug=debug) 