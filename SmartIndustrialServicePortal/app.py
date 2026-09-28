from flask import Flask, render_template, request, redirect, session, flash, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
from functools import wraps
import os
from datetime import datetime
import mysql.connector as mysql_connector
from flask_socketio import SocketIO

app = Flask(__name__)
app.config.from_pyfile('config.py')
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins=[])

# Ensure upload directory exists
os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)


class ConnectionProxy:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self, *args, **kwargs):
        kwargs.setdefault('dictionary', True)
        return self._connection.cursor(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._connection, name)


class MySQL:
    def __init__(self, app=None):
        self.app = app
        self._connection = None
        self._proxy = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app

    @property
    def connection(self):
        if self._connection is None or not self._connection.is_connected():
            self._connection = mysql_connector.connect(
                host=self.app.config.get('MYSQL_HOST', 'localhost'),
                user=self.app.config.get('MYSQL_USER', 'root'),
                password=self.app.config.get('MYSQL_PASSWORD', ''),
                database=self.app.config.get('MYSQL_DB', 'smart_industrial_portal'),
                port=self.app.config.get('MYSQL_PORT', 3306),
                autocommit=False,
                use_pure=True,
            )
            self._proxy = ConnectionProxy(self._connection)
        return self._proxy


mysql = MySQL(app)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _verify_password(stored_password: str, password: str) -> bool:
    if stored_password.startswith('scrypt:') or stored_password.startswith('pbkdf2:'):
        return check_password_hash(stored_password, password)
    return stored_password == _hash_password(password)


def initialize_database():
    db_name = app.config.get('MYSQL_DB', 'smart_industrial_portal')
    try:
        admin_conn = mysql_connector.connect(
            host=app.config.get('MYSQL_HOST', 'localhost'),
            user=app.config.get('MYSQL_USER', 'root'),
            password=app.config.get('MYSQL_PASSWORD', ''),
            port=app.config.get('MYSQL_PORT', 3306),
            autocommit=True,
            use_pure=True,
        )
        cursor = admin_conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
        cursor.close()
        admin_conn.close()
    except Exception as exc:
        raise RuntimeError(f"Unable to initialize MySQL database: {exc}") from exc

    try:
        conn = mysql_connector.connect(
            host=app.config.get('MYSQL_HOST', 'localhost'),
            user=app.config.get('MYSQL_USER', 'root'),
            password=app.config.get('MYSQL_PASSWORD', ''),
            database=db_name,
            port=app.config.get('MYSQL_PORT', 3306),
            autocommit=False,
            use_pure=True,
        )
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(100),
            department VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            password VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            complaint_id INT AUTO_INCREMENT PRIMARY KEY,
            employee_id INT,
            title VARCHAR(255),
            description TEXT,
            category VARCHAR(100),
            priority VARCHAR(50),
            status VARCHAR(50) DEFAULT 'Pending',
            image_path VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100),
            password VARCHAR(255)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            assignment_id INT AUTO_INCREMENT PRIMARY KEY,
            complaint_id INT UNIQUE,
            assigned_to VARCHAR(100),
            assigned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completion_date TIMESTAMP NULL,
            FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id) ON DELETE CASCADE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS technicians (
            technician_id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            phone VARCHAR(30),
            department VARCHAR(100) NOT NULL,
            skills TEXT,
            availability VARCHAR(20) NOT NULL DEFAULT 'Available',
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignment_history (
            history_id INT AUTO_INCREMENT PRIMARY KEY,
            complaint_id INT NOT NULL,
            technician_id INT NULL,
            assigned_by INT NOT NULL,
            action VARCHAR(30) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id) ON DELETE CASCADE,
            FOREIGN KEY (technician_id) REFERENCES technicians(technician_id) ON DELETE SET NULL,
            FOREIGN KEY (assigned_by) REFERENCES admin(id) ON DELETE CASCADE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id INT AUTO_INCREMENT PRIMARY KEY,
            employee_id INT NOT NULL,
            employee_name VARCHAR(100) NOT NULL,
            rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
            feedback TEXT NOT NULL,
            is_reviewed TINYINT(1) NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
        )
        """)

        admin_password = _hash_password('admin123')
        cursor.execute("SELECT COUNT(*) FROM admin WHERE username = %s", ('admin',))
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO admin(username, password) VALUES (%s, %s)", ('admin', admin_password))

        employee_password = _hash_password('pwd123')
        for employee in [
            ('Rajesh Kumar', 'IT Support', 'rajesh.k@nlc.com', employee_password),
            ('Amit Patel', 'Electrical', 'amit.p@nlc.com', employee_password),
            ('Suresh Sharma', 'Mining Infrastructure', 'suresh.s@nlc.com', employee_password),
        ]:
            cursor.execute("SELECT COUNT(*) FROM employees WHERE email = %s", (employee[2],))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO employees(full_name, department, email, password) VALUES (%s, %s, %s, %s)",
                    employee,
                )

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as exc:
        raise RuntimeError(f"Unable to create database schema: {exc}") from exc


initialize_database()

# Authentication wrappers
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'employee_id' not in session or session.get('role') != 'employee':
            flash("Please login to access the Employee Dashboard.", "danger")
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session or session.get('role') != 'admin':
            flash("Admin verification required.", "danger")
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated_function

# Public Routes
@app.route('/')
def home():
    if session.get('role') == 'employee':
        return redirect('/dashboard')
    elif session.get('role') == 'admin':
        return redirect('/admin/dashboard')
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# Employee Auth
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM employees WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()

        if user and _verify_password(user['password'], password):
            session['employee_id'] = user['employee_id']
            session['employee_name'] = user['full_name']
            session['employee_dept'] = user['department']
            session['role'] = 'employee'
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect('/dashboard')

        flash("Invalid email or password. Please try again.", "danger")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        department = request.form['department']
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        try:
            hashed_password = _hash_password(password)
            cur.execute(
                "INSERT INTO employees(full_name, department, email, password) VALUES(%s, %s, %s, %s)",
                (full_name, department, email, hashed_password)
            )
            mysql.connection.commit()
            flash("Registration successful! You can now log in.", "success")
            return redirect('/login')
        except Exception as e:
            flash("Registration failed. Email might already be in use.", "danger")
        finally:
            cur.close()

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have logged out successfully.", "success")
    return redirect('/')

# Employee Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    employee_id = session['employee_id']
    cur = mysql.connection.cursor()
    
    # Get stats count
    cur.execute("""
        SELECT 
            SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='Assigned' THEN 1 ELSE 0 END) as assigned,
            SUM(CASE WHEN status='In Progress' THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN status='Resolved' THEN 1 ELSE 0 END) as resolved,
            SUM(CASE WHEN status='Rejected' THEN 1 ELSE 0 END) as rejected,
            COUNT(*) as total
        FROM complaints 
        WHERE employee_id = %s
    """, (employee_id,))
    stats_data = cur.fetchone()
    
    # Handle case where there are no complaints yet
    stats = {
        'total': stats_data['total'] if stats_data and stats_data['total'] else 0,
        'pending': stats_data['pending'] if stats_data and stats_data['pending'] else 0,
        'assigned': stats_data['assigned'] if stats_data and stats_data['assigned'] else 0,
        'in_progress': stats_data['in_progress'] if stats_data and stats_data['in_progress'] else 0,
        'resolved': stats_data['resolved'] if stats_data and stats_data['resolved'] else 0,
        'rejected': stats_data['rejected'] if stats_data and stats_data['rejected'] else 0
    }

    # Get recent complaints
    cur.execute("""
        SELECT c.*, a.assigned_to 
        FROM complaints c 
        LEFT JOIN assignments a ON c.complaint_id = a.complaint_id 
        WHERE c.employee_id = %s 
        ORDER BY c.created_at DESC 
        LIMIT 5
    """, (employee_id,))
    recent_complaints = cur.fetchall()
    cur.close()

    return render_template('employee_dashboard.html', stats=stats, recent_complaints=recent_complaints)

# Raise Complaint
@app.route('/raise_complaint', methods=['GET', 'POST'])
@login_required
def raise_complaint():
    if request.method == 'POST':
        employee_id = session['employee_id']
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        priority = request.form['priority']

        image = request.files.get('image')
        filename = ''

        if image and image.filename != '':
            filename = secure_filename(image.filename)
            # Make filename unique
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cur = mysql.connection.cursor()
        cur.execute(
            """
            INSERT INTO complaints (employee_id, title, description, category, priority, image_path)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (employee_id, title, description, category, priority, filename)
        )
        mysql.connection.commit()
        cur.close()
        
        flash("Complaint submitted successfully!", "success")
        return redirect('/history')

    return render_template('raise_complaint.html')

# Complaint History
@app.route('/history')
@login_required
def history():
    employee_id = session['employee_id']
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT c.*, a.assigned_to, a.assigned_date, a.completion_date 
        FROM complaints c 
        LEFT JOIN assignments a ON c.complaint_id = a.complaint_id 
        WHERE c.employee_id = %s 
        ORDER BY c.created_at DESC
    """, (employee_id,))
    complaints = cur.fetchall()
    cur.close()
    return render_template('complaint_history.html', complaints=complaints)

# Employee Profile
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    employee_id = session['employee_id']
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        full_name = request.form['full_name']
        password = request.form.get('password')

        if password and password.strip() != '':
            hashed_password = _hash_password(password)
            cur.execute("UPDATE employees SET full_name=%s, password=%s WHERE employee_id=%s", (full_name, hashed_password, employee_id))
        else:
            cur.execute("UPDATE employees SET full_name=%s WHERE employee_id=%s", (full_name, employee_id))
        
        mysql.connection.commit()
        session['employee_name'] = full_name
        flash("Profile updated successfully!", "success")

    cur.execute("SELECT * FROM employees WHERE employee_id=%s", (employee_id,))
    employee = cur.fetchone()
    cur.close()

    return render_template('profile.html', employee=employee)

# Employee Feedback
@app.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():
    if request.method == 'POST':
        employee_id = session['employee_id']
        employee_name = session['employee_name']
        rating = request.form.get('rating')
        feedback_text = request.form.get('feedback')

        # Server-side validation
        if not rating or not feedback_text or rating not in ['1', '2', '3', '4', '5'] or feedback_text.strip() == '':
            flash("Invalid input. Rating must be 1-5 and comments cannot be empty.", "danger")
            return redirect('/feedback')

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO feedback (employee_id, employee_name, rating, feedback) VALUES (%s, %s, %s, %s)",
            (employee_id, employee_name, int(rating), feedback_text.strip())
        )
        mysql.connection.commit()
        cur.close()

        flash("Feedback submitted successfully!", "success")
        return redirect('/dashboard')

    return render_template('submit_feedback.html')


# Admin Auth
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM admin WHERE username=%s", (username,))
        admin_user = cur.fetchone()
        cur.close()

        if admin_user and _verify_password(admin_user['password'], password):
            session['admin_id'] = admin_user['id']
            session['admin_username'] = admin_user['username']
            session['role'] = 'admin'
            flash("Welcome to the Admin Command Center!", "success")
            return redirect('/admin/dashboard')

        flash("Invalid administrator credentials.", "danger")

    return render_template('admin_login.html')

# Admin Dashboard
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    cur = mysql.connection.cursor()

    # Admin dashboard stats
    cur.execute("""
        SELECT 
            SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='Assigned' THEN 1 ELSE 0 END) as assigned,
            SUM(CASE WHEN status='In Progress' THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN status='Resolved' THEN 1 ELSE 0 END) as resolved,
            COUNT(*) as total
        FROM complaints
    """)
    stats_data = cur.fetchone()

    cur.execute("SELECT COUNT(*) as critical_count FROM complaints WHERE status='Pending' AND priority='Critical'")
    crit_pending = cur.fetchone()

    stats = {
        'total': stats_data['total'] if stats_data and stats_data['total'] else 0,
        'pending': stats_data['pending'] if stats_data and stats_data['pending'] else 0,
        'assigned': stats_data['assigned'] if stats_data and stats_data['assigned'] else 0,
        'in_progress': stats_data['in_progress'] if stats_data and stats_data['in_progress'] else 0,
        'resolved': stats_data['resolved'] if stats_data and stats_data['resolved'] else 0,
        'critical_pending': crit_pending['critical_count'] if crit_pending else 0
    }

    # Urgent complaints (High or Critical and not resolved/rejected)
    cur.execute("""
        SELECT c.*, e.full_name 
        FROM complaints c
        JOIN employees e ON c.employee_id = e.employee_id
        WHERE c.priority IN ('High', 'Critical') AND c.status IN ('Pending', 'Assigned')
        ORDER BY c.created_at DESC LIMIT 5
    """)
    critical_tickets = cur.fetchall()

    # Active work orders (status is Assigned or In Progress)
    cur.execute("""
        SELECT c.*, a.assigned_to, a.assigned_date 
        FROM complaints c
        JOIN assignments a ON c.complaint_id = a.complaint_id
        WHERE c.status IN ('Assigned', 'In Progress')
        ORDER BY a.assigned_date DESC LIMIT 5
    """)
    active_assignments = cur.fetchall()
    cur.close()

    return render_template('admin_dashboard.html', stats=stats, critical_tickets=critical_tickets, active_assignments=active_assignments)

# Admin Ticket Management
@app.route('/admin/complaints')
@admin_required
def admin_complaints():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT c.*, e.full_name, e.department, a.assigned_to 
        FROM complaints c
        JOIN employees e ON c.employee_id = e.employee_id
        LEFT JOIN assignments a ON c.complaint_id = a.complaint_id
        ORDER BY c.created_at DESC
    """)
    complaints = cur.fetchall()
    cur.close()
    return render_template('admin_complaints.html', complaints=complaints)

# Update Complaint Status and Assignee
@app.route('/admin/update_ticket', methods=['POST'])
@admin_required
def admin_update_ticket():
    complaint_id = request.form['complaint_id']
    status = request.form['status']
    assigned_to = request.form.get('assigned_to', '').strip()

    cur = mysql.connection.cursor()
    
    # Update status in complaints table
    cur.execute("UPDATE complaints SET status=%s WHERE complaint_id=%s", (status, complaint_id))
    
    # Handle assignment logic
    if status in ['Assigned', 'In Progress', 'Resolved']:
        # Check if assignment row exists
        cur.execute("SELECT * FROM assignments WHERE complaint_id=%s", (complaint_id,))
        existing_assignment = cur.fetchone()
        
        comp_date = None
        if status == 'Resolved':
            comp_date = datetime.now()

        if existing_assignment:
            # Update existing
            if status == 'Resolved':
                cur.execute(
                    "UPDATE assignments SET assigned_to=%s, completion_date=%s WHERE complaint_id=%s",
                    (assigned_to, comp_date, complaint_id)
                )
            else:
                cur.execute(
                    "UPDATE assignments SET assigned_to=%s WHERE complaint_id=%s",
                    (assigned_to, complaint_id)
                )
        else:
            # Create new
            cur.execute(
                "INSERT INTO assignments (complaint_id, assigned_to, completion_date) VALUES (%s, %s, %s)",
                (complaint_id, assigned_to, comp_date)
            )
    else:
        # If status is Pending or Rejected, we clear any assignment records
        cur.execute("DELETE FROM assignments WHERE complaint_id=%s", (complaint_id,))

    mysql.connection.commit()
    cur.close()
    socketio.emit('dashboard_refresh', {'complaint_id': complaint_id})
    
    flash(f"Ticket #{complaint_id} updated successfully.", "success")
    return redirect('/admin/complaints')

# Delete Complaint
@app.route('/admin/delete_complaint/<int:complaint_id>', methods=['POST'])
@admin_required
def admin_delete_complaint(complaint_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM complaints WHERE complaint_id=%s", (complaint_id,))
    mysql.connection.commit()
    cur.close()
    socketio.emit('dashboard_refresh', {'complaint_id': complaint_id, 'deleted': True})
    flash(f"Ticket #{complaint_id} deleted successfully.", "success")
    return redirect('/admin/complaints')

# Admin Analytics view & API
@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    return render_template('admin_analytics.html')

@app.route('/admin/analytics_data')
@admin_required
def admin_analytics_data():
    cur = mysql.connection.cursor()
    
    # Status count
    cur.execute("SELECT status, COUNT(*) as count FROM complaints GROUP BY status")
    statuses_data = cur.fetchall()
    statuses = {'Pending': 0, 'Assigned': 0, 'In Progress': 0, 'Resolved': 0, 'Rejected': 0}
    for row in statuses_data:
        statuses[row['status']] = row['count']

    # Priority count
    cur.execute("SELECT priority, COUNT(*) as count FROM complaints GROUP BY priority")
    priorities_data = cur.fetchall()
    priorities = {'Low': 0, 'Medium': 0, 'High': 0, 'Critical': 0}
    for row in priorities_data:
        priorities[row['priority']] = row['count']

    # Category count
    cur.execute("SELECT category, COUNT(*) as count FROM complaints GROUP BY category")
    categories_data = cur.fetchall()
    categories = {}
    for row in categories_data:
        categories[row['category']] = row['count']

    # Department-wise counts
    cur.execute("""
        SELECT e.department, COUNT(c.complaint_id) as count 
        FROM employees e 
        LEFT JOIN complaints c ON e.employee_id = c.employee_id 
        GROUP BY e.department
    """)
    departments_data = cur.fetchall()
    departments = {}
    for row in departments_data:
        departments[row['department']] = row['count']

    cur.close()
    
    return jsonify({
        'statuses': statuses,
        'priorities': priorities,
        'categories': categories,
        'departments': departments
    })

# Employee Directory
@app.route('/admin/employees')
@admin_required
def admin_employees():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT e.*, COUNT(c.complaint_id) AS complaints_count 
        FROM employees e 
        LEFT JOIN complaints c ON e.employee_id = c.employee_id 
        GROUP BY e.employee_id 
        ORDER BY e.employee_id ASC
    """)
    employees = cur.fetchall()
    cur.close()
    return render_template('admin_employees.html', employees=employees)

# Admin Feedback Management
@app.route('/admin/feedback')
@admin_required
def admin_feedback():
    cur = mysql.connection.cursor()
    
    # Calculate statistics
    cur.execute("SELECT AVG(rating) as avg_rating, COUNT(*) as total_feedback FROM feedback")
    stats = cur.fetchone()
    
    avg_rating = round(stats['avg_rating'], 1) if stats and stats['avg_rating'] is not None else 0.0
    total_feedback = stats['total_feedback'] if stats else 0
    
    # Get feedback records
    cur.execute("SELECT * FROM feedback ORDER BY created_at DESC")
    feedback_list = cur.fetchall()
    cur.close()
    
    return render_template('admin_feedback.html', feedback_list=feedback_list, avg_rating=avg_rating, total_feedback=total_feedback)

@app.route('/admin/review_feedback/<int:feedback_id>', methods=['POST'])
@admin_required
def admin_review_feedback(feedback_id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE feedback SET is_reviewed=1 WHERE feedback_id=%s", (feedback_id,))
    mysql.connection.commit()
    cur.close()
    flash(f"Feedback #{feedback_id} marked as reviewed.", "success")
    return redirect('/admin/feedback')

@app.route('/admin/delete_feedback/<int:feedback_id>', methods=['POST'])
@admin_required
def admin_delete_feedback(feedback_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM feedback WHERE feedback_id=%s", (feedback_id,))
    mysql.connection.commit()
    cur.close()
    flash(f"Feedback #{feedback_id} deleted successfully.", "success")
    return redirect('/admin/feedback')


# Report Generation
@app.route('/admin/reports')
@admin_required
def admin_reports():
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    dept = request.args.get('dept', '')
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    priority = request.args.get('priority', '')

    cur = mysql.connection.cursor()
    
    # Get distinct departments for filter dropdown
    cur.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != ''")
    depts = [row['department'] for row in cur.fetchall()]

    # Build reports query dynamically
    query = """
        SELECT c.*, e.full_name, e.department, a.assigned_to 
        FROM complaints c
        JOIN employees e ON c.employee_id = e.employee_id
        LEFT JOIN assignments a ON c.complaint_id = a.complaint_id
        WHERE 1=1
    """
    params = []

    if start_date:
        query += " AND c.created_at >= %s"
        params.append(f"{start_date} 00:00:00")
    if end_date:
        query += " AND c.created_at <= %s"
        params.append(f"{end_date} 23:59:59")
    if dept:
        query += " AND e.department = %s"
        params.append(dept)
    if category:
        query += " AND c.category = %s"
        params.append(category)
    if status:
        query += " AND c.status = %s"
        params.append(status)
    if priority:
        query += " AND c.priority = %s"
        params.append(priority)

    query += " ORDER BY c.created_at DESC"
    
    cur.execute(query, tuple(params))
    reports = cur.fetchall()
    cur.close()

    filters = {
        'start_date': start_date,
        'end_date': end_date,
        'dept': dept,
        'category': category,
        'status': status,
        'priority': priority
    }

    return render_template('admin_reports.html', reports=reports, departments=depts, filters=filters)

if __name__ == '__main__':
    app.run(debug=True)

