import cx_Oracle
from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'mapra042473'  # Change it to a secure key
app.config['SQLALCHEMY_DATABASE_URI'] = 'oracle+cx_oracle://perfect:perfect@192.168.0.224:1521/ho'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database connection function
def get_db_connection():
    try:
        conn = cx_Oracle.connect(
            user="perfect",
            password="perfect",
            dsn="(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=192.168.0.224)(PORT=1521))(CONNECT_DATA=(SERVICE_NAME=ho)))"
        )
        return conn
    except cx_Oracle.DatabaseError as e:
        flash(f"Database connection failed: {e}", 'error')
        return None

# Get employee name after login
def get_employee_name(emp_code):
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT EMPNAME FROM EMPLOYEE_MAS WHERE EMPCODE = :1", (emp_code,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Get latest leave balance per LTYPE (excluding OP row)
def get_leave_balance(emp_code):
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute("""
        SELECT LTYPE, MAX(SDATE) AS LAST_DATE
        FROM LEAVE_REG
        WHERE EMPCODE = :1 AND LTYPE IN ('CL', 'SL', 'PL') AND REASON != 'OP'
        GROUP BY LTYPE
    """, (emp_code,))
    latest_dates = dict(cursor.fetchall())

    balances = []
    for ltype in ['CL', 'SL', 'PL']:
        if ltype in latest_dates:
            cursor.execute("""
                SELECT CR FROM LEAVE_REG 
                WHERE EMPCODE = :1 AND LTYPE = :2 AND SDATE = :3
            """, (emp_code, ltype, latest_dates[ltype]))
            cr = cursor.fetchone()
            balances.append((ltype, cr[0] if cr else 0))
        else:
            # If no leave applied yet, fetch OP CR
            cursor.execute("""
                SELECT CR FROM LEAVE_REG 
                WHERE EMPCODE = :1 AND LTYPE = :2 AND REASON = 'OP'
            """, (emp_code, ltype))
            cr = cursor.fetchone()
            balances.append((ltype, cr[0] if cr else 0))
    
    conn.close()
    return balances

# Apply leave logic
def apply_leave(emp_code, sdate, edate, ltype, reason):
    if ltype not in ['CL', 'SL', 'PL']:
        flash("Invalid leave type.", 'error')
        return

    days = (edate - sdate).days + 1
    if ltype == 'SL':
        count_weekends = sum(1 for i in range(days) if (sdate + pd.DateOffset(i)).weekday() >= 5)
        days -= count_weekends
        flash(f"SL days to be deducted: {days} (after excluding weekends)", 'info')

    sdate_str = sdate.strftime('%d-%m-%Y')
    edate_str = edate.strftime('%d-%m-%Y')

    leave_balance = get_leave_balance(emp_code)
    remaining_balance = 0
    for lt, bal in leave_balance:
        if lt == ltype:
            remaining_balance = bal
            break

    if remaining_balance < days:
        flash(f"Not enough {ltype} leave balance. Needed: {days}, Available: {remaining_balance}", 'error')
        return

    updated_balance = remaining_balance - days

    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        # Insert new leave row
        cursor.execute("""
            INSERT INTO LEAVE_REG (EMPCODE, SDATE, EDATE, LTYPE, DR, CR, REASON)
            VALUES (:1, TO_DATE(:2, 'DD-MM-YYYY'), TO_DATE(:3, 'DD-MM-YYYY'), :4, :5, :6, :7)
        """, (emp_code, sdate_str, edate_str, ltype, days, updated_balance, reason))
        conn.commit()
        flash(f"Leave applied for {days} day(s). New {ltype} balance: {updated_balance}", 'success')
    except cx_Oracle.DatabaseError as e:
        flash(f"Error applying leave: {e}", 'error')
    finally:
        conn.close()

# Get leave history for display
def get_leave_history(emp_code):
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    query = """
        SELECT TO_CHAR(SDATE, 'DD-MM-YYYY') AS START_DATE,
               TO_CHAR(EDATE, 'DD-MM-YYYY') AS END_DATE,
               LTYPE,
               DR AS "Days Taken",
               CR AS "Balance After",
               REASON
        FROM LEAVE_REG
        WHERE EMPCODE = :1
        ORDER BY SDATE
    """
    df = pd.read_sql(query, conn, params=[emp_code])
    conn.close()
    return df

# Home route - Update to show login page
@app.route('/')
def home():
    return redirect(url_for('login'))  # Redirect to the login page

# Login route - Display login form
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        emp_code = request.form['emp_code']
        password = request.form['password']

        if emp_code and password:
            emp_name = get_employee_name(emp_code)
            if emp_name:
                session['emp_code'] = emp_code
                session['emp_name'] = emp_name
                session['logged_in'] = True
                flash(f"Welcome, {emp_name}!", 'success')
                return redirect(url_for('dashboard'))
            else:
                flash("Invalid credentials.", 'error')
        else:
            flash("Please enter both credentials.", 'error')

    return render_template('login.html')

# Dashboard route after login
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    emp_code = session.get('emp_code')
    emp_name = session.get('emp_name')

    # Show leave balances
    leave_balance = get_leave_balance(emp_code)

    if request.method == 'POST':
        sdate = datetime.strptime(request.form['sdate'], '%Y-%m-%d')
        edate = datetime.strptime(request.form['edate'], '%Y-%m-%d')
        ltype = request.form['ltype']
        reason = request.form['reason']

        if sdate <= edate:
            apply_leave(emp_code, sdate, edate, ltype, reason)
        else:
            flash("Start date cannot be after end date.", 'error')

    # Leave History
    history_df = get_leave_history(emp_code)

    return render_template('dashboard.html', emp_name=emp_name, leave_balance=leave_balance, history_df=history_df)

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", 'success')
    return redirect(url_for('login'))

# Run the app
if __name__ == "__main__":
    app.run(debug=True)
