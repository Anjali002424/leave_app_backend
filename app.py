from flask import Flask, request, jsonify
import cx_Oracle
from datetime import datetime

app = Flask(__name__)

# Oracle DB config
DB_USER = 'perfect'
DB_PASSWORD = 'perfect'
DB_DSN = "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=192.168.0.224)(PORT=1521))(CONNECT_DATA=(SERVICE_NAME=ho)))"

# Utility: Create DB connection
def get_db_connection():
    return cx_Oracle.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)

# Endpoint 1: Get employee name
@app.route('/get_employee_name', methods=['POST'])
def get_employee_name():
    data = request.json
    empcode = data.get('empcode')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EMPNAME FROM EMPLOYEE_MAS WHERE EMPCODE = :1", (empcode,))
    result = cursor.fetchone()
    conn.close()

    return jsonify({'empname': result[0] if result else None})

# Endpoint 2: Get leave balance
@app.route('/get_leave_balance', methods=['POST'])
def get_leave_balance():
    data = request.json
    empcode = data.get('empcode')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT LTYPE, MAX(SDATE) AS LAST_DATE
        FROM LEAVE_REG
        WHERE EMPCODE = :1 AND LTYPE IN ('CL', 'SL', 'PL') AND REASON != 'OP'
        GROUP BY LTYPE
    """, (empcode,))
    latest_dates = dict(cursor.fetchall())

    balances = []
    for ltype in ['CL', 'SL', 'PL']:
        if ltype in latest_dates:
            cursor.execute("""
                SELECT CR FROM LEAVE_REG 
                WHERE EMPCODE = :1 AND LTYPE = :2 AND SDATE = :3
            """, (empcode, ltype, latest_dates[ltype]))
        else:
            cursor.execute("""
                SELECT CR FROM LEAVE_REG 
                WHERE EMPCODE = :1 AND LTYPE = :2 AND REASON = 'OP'
            """, (empcode, ltype))
        cr = cursor.fetchone()
        balances.append({'type': ltype, 'balance': cr[0] if cr else 0})

    conn.close()
    return jsonify({'leave_balances': balances})

# Endpoint 3: Apply leave
@app.route('/apply_leave', methods=['POST'])
def apply_leave():
    data = request.json
    empcode = data['empcode']
    sdate = datetime.strptime(data['start_date'], '%Y-%m-%d')
    edate = datetime.strptime(data['end_date'], '%Y-%m-%d')
    ltype = data['ltype']
    reason = data['reason']
    days = (edate - sdate).days + 1

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT MAX(SDATE) FROM LEAVE_REG 
        WHERE EMPCODE = :1 AND LTYPE = :2 AND REASON != 'OP'
    """, (empcode, ltype))
    latest = cursor.fetchone()[0]

    if latest:
        cursor.execute("""
            SELECT CR FROM LEAVE_REG WHERE EMPCODE = :1 AND LTYPE = :2 AND SDATE = :3
        """, (empcode, ltype, latest))
    else:
        cursor.execute("""
            SELECT CR FROM LEAVE_REG WHERE EMPCODE = :1 AND LTYPE = :2 AND REASON = 'OP'
        """, (empcode, ltype))
    cr = cursor.fetchone()[0]
    
    if cr < days:
        return jsonify({'error': f'Not enough leave. Required: {days}, Available: {cr}'})

    new_cr = cr - days
    cursor.execute("""
        INSERT INTO LEAVE_REG (EMPCODE, SDATE, EDATE, LTYPE, DR, CR, REASON)
        VALUES (:1, :2, :3, :4, :5, :6, :7)
    """, (empcode, sdate, edate, ltype, days, new_cr, reason))
    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'new_balance': new_cr})

# Endpoint 4: Leave history
@app.route('/get_leave_history', methods=['POST'])
def get_leave_history():
    data = request.json
    empcode = data.get('empcode')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TO_CHAR(SDATE, 'DD-MM-YYYY') AS START_DATE,
               TO_CHAR(EDATE, 'DD-MM-YYYY') AS END_DATE,
               LTYPE,
               DR,
               CR,
               REASON
        FROM LEAVE_REG
        WHERE EMPCODE = :1
        ORDER BY SDATE
    """, (empcode,))
    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append({
            'start_date': row[0],
            'end_date': row[1],
            'ltype': row[2],
            'days_taken': row[3],
            'balance_after': row[4],
            'reason': row[5]
        })
    return jsonify({'history': history})

if __name__ == '__main__':
    app.run(debug=True)
