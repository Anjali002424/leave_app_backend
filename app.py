import cx_Oracle
import streamlit as st
import pandas as pd
from datetime import datetime
from flask import Flask

# Flask app initialization
app = Flask(__name__)

# Root route for testing
@app.route('/')
def home():
    return 'Welcome to the Leave Management System!'

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
        st.error(f"Database connection failed: {e}")
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
        st.error("Invalid leave type.")
        return

    days = (edate - sdate).days + 1
    if ltype == 'SL':
        count_weekends = sum(1 for i in range(days) if (sdate + pd.DateOffset(i)).weekday() >= 5)
        days -= count_weekends
        st.write(f"SL days to be deducted: {days} (after excluding weekends)")

    sdate_str = sdate.strftime('%d-%m-%Y')
    edate_str = edate.strftime('%d-%m-%Y')

    leave_balance = get_leave_balance(emp_code)
    remaining_balance = 0
    for lt, bal in leave_balance:
        if lt == ltype:
            remaining_balance = bal
            break

    if remaining_balance < days:
        st.error(f"Not enough {ltype} leave balance. Needed: {days}, Available: {remaining_balance}")
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
        st.success(f"Leave applied for {days} day(s). New {ltype} balance: {updated_balance}")
    except cx_Oracle.DatabaseError as e:
        st.error(f"Error applying leave: {e}")
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

# Main Streamlit App
def main():
    st.title("Employee Leave Application")

    # Login section
    st.subheader("Login")
    emp_code = st.text_input("Enter Employee Code")
    password = st.text_input("Enter Password", type="password")

    if st.button("Login"):
        if emp_code and password:
            emp_name = get_employee_name(emp_code)
            if emp_name:
                st.session_state['emp_code'] = emp_code
                st.session_state['emp_name'] = emp_name
                st.session_state['logged_in'] = True
                st.success(f"Welcome, {emp_name}!")
            else:
                st.error("Invalid credentials.")
        else:
            st.error("Please enter both credentials.")

    # Post-login
    if st.session_state.get('logged_in'):
        st.subheader(f"Leave Application - {st.session_state['emp_name']}")

        # Show leave balances
        leave_balance = get_leave_balance(st.session_state['emp_code'])
        st.write("### Leave Balances:")
        for lt, bal in leave_balance:
            st.write(f"{lt}: {bal} days")

        # Leave application form
        st.write("### Apply for Leave")
        sdate = st.date_input("Start Date")
        edate = st.date_input("End Date")
        ltype = st.selectbox("Leave Type", ["CL", "SL", "PL"])
        reason = st.text_area("Reason for Leave")

        if st.button("Apply Leave"):
            if sdate <= edate:
                apply_leave(st.session_state['emp_code'], sdate, edate, ltype, reason)
            else:
                st.error("Start date cannot be after end date.")

        # Leave History
        st.write("### Leave History")
        history_df = get_leave_history(st.session_state['emp_code'])
        if not history_df.empty:
            st.dataframe(history_df, use_container_width=True)
        else:
            st.info("No leave history found.")

# Run the app
if __name__ == "__main__":
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    main()
