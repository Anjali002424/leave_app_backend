import os
import cx_Oracle
from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session

# Initialize Flask app
app = Flask(__name__)

# Set up session management
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mapra042473')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Function to get DB connection
def get_db_connection():
    tns_path = r'C:\Program Files\Oracle Client for Microsoft Tools\network\admin'  # Update this if needed
    os.environ['TNS_ADMIN'] = tns_path

    username = 'perfect'
    password = 'perfect'
    dsn = cx_Oracle.makedsn('192.168.0.224', '1521', service_name='ho')

    connection = cx_Oracle.connect(username, password, dsn)
    return connection

# Home route - redirects to login
@app.route('/')
def home():
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

# Check credentials function
def check_credentials(emp_code, password):
    connection = get_db_connection()
    cursor = connection.cursor()

    # Note: Column names are EMPCODE, PASSWORD, and EMNAME
    cursor.execute("""
        SELECT EMNAME FROM EMPLOYEE_MAS
        WHERE EMPCODE = :emp_code AND PASSWORD = :password
    """, {'emp_code': emp_code, 'password': password})

    result = cursor.fetchone()
    connection.close()

    if result:
        return result[0]
    return None

# Dashboard route
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    return render_template('dashboard.html', emp_name=session['emp_name'])

# Leave application route
@app.route('/apply_leave', methods=['GET', 'POST'])
def apply_leave():
    if not session.get('logged_in'):
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
        INSERT INTO LEAVE_APPLICATION_EMP 
        (EMPCODE, LEAVE_START, LEAVE_END, LEAVE_REASON, LEAVE_TYPE)
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

if __name__ == '__main__':
    app.run(debug=True)
