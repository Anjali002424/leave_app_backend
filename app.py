import os
import cx_Oracle
from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
from werkzeug.utils import quote as url_quote  # updated for newer Werkzeug

# Initialize the Flask app
app = Flask(__name__)

# Set up session management
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mapra042473')  # Set from environment variable
app.config['SESSION_TYPE'] = 'filesystem'  # Can also use 'redis' for scaling
Session(app)

# Function to get database connection using TNS
def get_db_connection():
    # Path to your TNS file
    tns_path = r'C:\Program Files\Oracle Client for Microsoft Tools\network\admin'  # Use raw string for Windows path

    # Set TNS_ADMIN environment variable to TNS file path
    os.environ['TNS_ADMIN'] = tns_path

    # Oracle DB credentials
    username = 'perfect'
    password = 'perfect'

    # Use the TNS configuration
    dsn = cx_Oracle.makedsn('192.168.0.224', '1521', service_name='ho')

    # Create a connection using the TNS configuration
    connection = cx_Oracle.connect(username, password, dsn)
    return connection

# Home route (redirect to login)
@app.route('/')
def index():
    return redirect(url_for('login'))

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        emp_code = request.form['emp_code']
        password = request.form['password']

        emp_name = check_credentials(emp_code, password)
        
        if emp_name:
            session['emp_code'] = emp_code
            session['emp_name'] = emp_name
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials", 401

    return render_template('login.html')

# Function to check user credentials
def check_credentials(emp_code, password):
    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute("SELECT emp_name FROM employee_mas WHERE emp_code = :emp_code AND password = :password", 
                   {'emp_code': emp_code, 'password': password})
    
    result = cursor.fetchone()
    connection.close()
    
    return result[0] if result else None

# Dashboard route
@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))

    return render_template('dashboard.html', emp_name=session['emp_name'])

# Leave application route
@app.route('/apply_leave', methods=['GET', 'POST'])
def apply_leave():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))

    if request.method == 'POST':
        leave_start = request.form['leave_start']
        leave_end = request.form['leave_end']
        leave_reason = request.form['leave_reason']
        leave_type = request.form['leave_type']

        save_leave_application(session['emp_code'], leave_start, leave_end, leave_reason, leave_type)

        return "Leave application submitted successfully!"

    return render_template('apply_leave.html')

# Save leave application to DB
def save_leave_application(emp_code, leave_start, leave_end, leave_reason, leave_type):
    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute("""
        INSERT INTO leave_application_emp 
        (emp_code, leave_start, leave_end, leave_reason, leave_type) 
        VALUES (:emp_code, :leave_start, :leave_end, :leave_reason, :leave_type)
    """, {
        'emp_code': emp_code,
        'leave_start': leave_start,
        'leave_end': leave_end,
        'leave_reason': leave_reason,
        'leave_type': leave_type
    })
    connection.commit()
    connection.close()

# Run locally
if __name__ == '__main__':
    app.run(debug=True)
