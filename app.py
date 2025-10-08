from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_apscheduler import APScheduler
import sqlite3
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import os
import config

# -------------------- Flask Setup --------------------
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# APScheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Ensure reports folder exists
os.makedirs('reports', exist_ok=True)

# -------------------- User Class --------------------
class User(UserMixin):
    def __init__(self, id, name, email, password):
        self.id = id
        self.name = name
        self.email = email
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    with sqlite3.connect(config.DATABASE) as conn:
        cur = conn.execute("SELECT id, name, email, password FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        if row:
            return User(*row)
    return None

# -------------------- DB Initialization --------------------
def init_db():
    with sqlite3.connect(config.DATABASE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                date TEXT NOT NULL,
                time TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
init_db()

# -------------------- Routes --------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        with sqlite3.connect(config.DATABASE) as conn:
            try:
                conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, password))
                conn.commit()
                flash('Registered successfully! Please login.')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('Email already exists!')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        with sqlite3.connect(config.DATABASE) as conn:
            cur = conn.execute("SELECT id, name, email, password FROM users WHERE email=? AND password=?", (email, password))
            row = cur.fetchone()
            if row:
                user = User(*row)
                login_user(user)
                return redirect(url_for('index'))
            else:
                flash("Invalid email/password")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

# -------------------- Event APIs --------------------
@app.route('/events')
@login_required
def get_events():
    user_id = current_user.id
    with sqlite3.connect(config.DATABASE) as conn:
        cursor = conn.execute("SELECT id, title, description, date, time FROM events WHERE user_id=? ORDER BY date", (user_id,))
        events = [
            {"id": row[0], "title": row[1], "description": row[2], "start": f"{row[3]}T{row[4] or '00:00'}"}
            for row in cursor.fetchall()
        ]
    return jsonify(events)

@app.route('/add', methods=['POST'])
@login_required
def add_event():
    data = request.json
    user_id = current_user.id
    with sqlite3.connect(config.DATABASE) as conn:
        conn.execute(
            "INSERT INTO events (user_id, title, description, date, time) VALUES (?, ?, ?, ?, ?)",
            (user_id, data['title'], data['description'], data['date'], data['time'])
        )
        conn.commit()
        event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Schedule email
    if data['time']:
        event_datetime = datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M")
        job_id = f"event_{event_id}"
        scheduler.add_job(
            id=job_id,
            func=send_email,
            trigger='date',
            run_date=event_datetime,
            args=[current_user.email, f"Reminder: {data['title']}", f"Your event '{data['title']}' is happening now!"]
        )
    return jsonify({"status": "success"})

@app.route('/delete/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event_route(event_id):
    user_id = current_user.id
    try:
        with sqlite3.connect(config.DATABASE) as conn:
            cur = conn.execute("DELETE FROM events WHERE id=? AND user_id=?", (event_id, user_id))
            conn.commit()
            if cur.rowcount == 0:
                return jsonify({"status": "fail", "message": "Event not found"})

        # Remove scheduled job if exists
        try:
            scheduler.remove_job(f"event_{event_id}")
        except:
            pass

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "fail", "message": str(e)})

@app.route('/generate-pdf')
@login_required
def generate_pdf():
    user_id = current_user.id
    pdf_path = os.path.join('reports', f"event_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    with sqlite3.connect(config.DATABASE) as conn:
        cursor = conn.execute("SELECT title, description, date, time FROM events WHERE user_id=? ORDER BY date", (user_id,))
        events = cursor.fetchall()

    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(200, 750, "Event Report")
    c.setFont("Helvetica", 12)
    y = 720
    for event in events:
        title, desc, date, time = event
        c.drawString(50, y, f"Title: {title}")
        c.drawString(50, y-15, f"Date: {date}  Time: {time or 'N/A'}")
        c.drawString(50, y-30, f"Description: {desc}")
        c.line(50, y-40, 550, y-40)
        y -= 60
        if y < 100:
            c.showPage()
            y = 720
    c.save()
    return send_file(pdf_path, as_attachment=True)

# -------------------- View & Edit Event --------------------
@app.route('/event/<int:event_id>')
@login_required
def view_event(event_id):
    user_id = current_user.id
    with sqlite3.connect(config.DATABASE) as conn:
        cur = conn.execute(
            "SELECT id, title, description, date, time FROM events WHERE id=? AND user_id=?",
            (event_id, user_id)
        )
        event = cur.fetchone()
        if not event:
            flash("Event not found!")
            return redirect(url_for('index'))
        event_dict = {"id": event[0], "title": event[1], "description": event[2], "date": event[3], "time": event[4]}
    return render_template('view_event.html', event=event_dict)

@app.route('/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    user_id = current_user.id
    with sqlite3.connect(config.DATABASE) as conn:
        if request.method == 'POST':
            title = request.form['title']
            description = request.form['description']
            date = request.form['date']
            time = request.form['time']
            conn.execute(
                "UPDATE events SET title=?, description=?, date=?, time=? WHERE id=? AND user_id=?",
                (title, description, date, time, event_id, user_id)
            )
            conn.commit()
            flash("Event updated successfully!")
            return redirect(url_for('index'))

        cur = conn.execute("SELECT id, title, description, date, time FROM events WHERE id=? AND user_id=?", (event_id, user_id))
        event = cur.fetchone()
        if not event:
            flash("Event not found!")
            return redirect(url_for('index'))
        event_dict = {"id": event[0], "title": event[1], "description": event[2], "date": event[3], "time": event[4]}
    return render_template('edit_event.html', event=event_dict)

@app.route('/view-events')
@login_required
def view_events_page():
    user_id = current_user.id
    with sqlite3.connect(config.DATABASE) as conn:
        cursor = conn.execute("SELECT id, title, description, date, time FROM events WHERE user_id=? ORDER BY date", (user_id,))
        events = cursor.fetchall()
    return render_template('view_events.html', events=events)

# -------------------- Email Function --------------------
def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = config.EMAIL_USER
    msg['To'] = to_email
    with smtplib.SMTP_SSL(config.EMAIL_HOST, config.EMAIL_PORT) as server:
        server.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
        server.send_message(msg)

# -------------------- Run --------------------
if __name__ == "__main__":
    app.run(debug=True)
