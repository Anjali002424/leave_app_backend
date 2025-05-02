import os
import cx_Oracle
from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session


# Your other Flask-related imports
from werkzeug.utils import secure_filename

# Initialize the Flask app
app = Flask(__name__)

# Set up session management
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mapra042473')  # Set from environment variable
app.config['SESSION_TYPE'] = 'filesystem'  # Can also use 'redis' for scaling
Session(app)

# Function to get database connection using TNS
def get_db_connection():
    # Path to your TNS file
    tns_path = 'C:/Program Files/Oracle Client for Microsoft Tools/network/admin'  # Update this with the path to your TNS file

    # Use cx_Oracle to load TNS from the file
    os.environ['TNS_ADMIN'] = tns_path  # Set TNS_ADMIN environment variable to TNS file path

    # Define your Oracle username and password
    username = 'perfect'
    password = 'perfect'

    # Use the TNS configuration provided by you
    dsn = cx_Oracle.makedsn('192.168.0.224', '1521', service_name='ho')

    # Create a connection using the TNS configuration
    connection = cx_Oracle.connect(username, password, dsn)
    return connection

# Home route (login page)
@app.route('/')
def index():
    return redirect(url_for('login'))  # Redirects to login page

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get form data
        emp_code = request.form['emp_code']
        password = request.form['password']

        # Check credentials in the database
        emp_name = check_credentials(emp_code, password)

        if emp_name:
            session['emp_code'] = emp_code
            session['emp_name'] = emp_name
            session['logged_in'] = True
            return redirect(url_for('dashboard'))  # Redirect to dashboard after successful login
        else:
            return "Invalid credentials", 401  # Handle invalid login

    return render_template('login.html')  # Render login form for GET requests

# Function to check user credentials
def check_credentials(emp_code, password):
    # Connect to DB and fetch user data
    connection = get_db_connection()
    cursor = connection.cursor()

    # Write your SQL query here to check credentials
    cursor.execute("SELECT emp_name FROM employee_mas WHERE emp_code = :emp_code AND password = :password", 
                   {'emp_code': emp_code, 'password': password})

    result = cursor.fetchone()
    connection.close()

    if result:
        return result[0]  # Return employee name if credentials are correct
    else:
        return None

# Dashboard route (protected)
@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))  # If not logged in, redirect to login page

    return render_template('dashboard.html', emp_name=session['emp_name'])  # Pass employee name to dashboard

# Leave application route (protected)
@app.route('/apply_leave', methods=['GET', 'POST'])
def apply_leave():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))  # If not logged in, redirect to login page

    if request.method == 'POST':
        # Get form data
        leave_start = request.form['leave_start']
        leave_end = request.form['leave_end']
        leave_reason = request.form['leave_reason']
        leave_type = request.form['leave_type']

        # Save leave application to database
        save_leave_application(session['emp_code'], leave_start, leave_end, leave_reason, leave_type)

        return "Leave application submitted successfully!"  # Success message

    return render_template('apply_leave.html')  # Render leave application form

# Function to save leave application data to DB
def save_leave_application(emp_code, leave_start, leave_end, leave_reason, leave_type):
    connection = get_db_connection()
    cursor = connection.cursor()

    # Write your SQL query to insert the leave application into the database
    cursor.execute("INSERT INTO leave_application_emp (emp_code, leave_start, leave_end, leave_reason, leave_type) VALUES (:emp_code, :leave_start, :leave_end, :leave_reason, :leave_type)", 
                   {'emp_code': emp_code, 'leave_start': leave_start, 'leave_end': leave_end, 'leave_reason': leave_reason, 'leave_type': leave_type})
    connection.commit()
    connection.close()

if __name__ == '__main__':
    app.run(debug=True)
