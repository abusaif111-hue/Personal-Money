import sqlite3
import os
from datetime import datetime, date
import calendar

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'moneymate.db')


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY,
        name TEXT DEFAULT 'User',
        family_status TEXT DEFAULT 'single',
        num_kids INTEGER DEFAULT 0,
        monthly_salary REAL DEFAULT 0,
        salary_increment_pct REAL DEFAULT 5.0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS statements (
        id INTEGER PRIMARY KEY,
        filename TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        bank_name TEXT DEFAULT 'Unknown',
        statement_month INTEGER,
        statement_year INTEGER,
        total_income REAL DEFAULT 0,
        total_expenses REAL DEFAULT 0,
        upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        statement_id INTEGER,
        date TEXT NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        type TEXT NOT NULL,
        category TEXT DEFAULT 'Uncategorized',
        FOREIGN KEY (statement_id) REFERENCES statements(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY,
        category TEXT NOT NULL,
        monthly_limit REAL NOT NULL,
        month INTEGER NOT NULL,
        year INTEGER NOT NULL,
        UNIQUE(category, month, year)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        target_amount REAL DEFAULT 0,
        current_amount REAL DEFAULT 0,
        monthly_contribution REAL DEFAULT 0,
        interest_rate REAL DEFAULT 0,
        loan_balance REAL DEFAULT 0,
        target_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cashflow_settings (
        id INTEGER PRIMARY KEY,
        base_monthly_salary REAL DEFAULT 0,
        salary_increment_pct REAL DEFAULT 5.0,
        annual_bonus REAL DEFAULT 0,
        thirteenth_month_salary REAL DEFAULT 0,
        other_monthly_income REAL DEFAULT 0,
        monthly_expenses REAL DEFAULT 0,
        expense_inflation_pct REAL DEFAULT 3.0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS extra_income (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        amount REAL NOT NULL,
        frequency TEXT NOT NULL,
        start_year INTEGER DEFAULT 1,
        end_year INTEGER DEFAULT 10
    )''')

    # Insert default profile if not exists
    c.execute('SELECT COUNT(*) FROM user_profile')
    if c.fetchone()[0] == 0:
        c.execute('''INSERT INTO user_profile (name, family_status, num_kids, monthly_salary, salary_increment_pct)
                     VALUES (?, ?, ?, ?, ?)''', ('User', 'single', 0, 0, 5.0))

    # Insert default cashflow settings if not exists
    c.execute('SELECT COUNT(*) FROM cashflow_settings')
    if c.fetchone()[0] == 0:
        c.execute('''INSERT INTO cashflow_settings
                     (base_monthly_salary, salary_increment_pct, annual_bonus, thirteenth_month_salary,
                      other_monthly_income, monthly_expenses, expense_inflation_pct)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''', (0, 5.0, 0, 0, 0, 0, 3.0))

    conn.commit()
    conn.close()


def get_dashboard_stats(month, year):
    conn = get_db()
    c = conn.cursor()

    c.execute('''SELECT
        COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 0) as total_income,
        COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as total_expenses
        FROM transactions
        WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?''',
              (str(month).zfill(2), str(year)))
    totals = c.fetchone()

    c.execute('''SELECT category,
        COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as spent
        FROM transactions
        WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?
        AND type='expense'
        GROUP BY category
        ORDER BY spent DESC''',
              (str(month).zfill(2), str(year)))
    categories = c.fetchall()

    conn.close()

    total_income = totals['total_income'] if totals else 0
    total_expenses = totals['total_expenses'] if totals else 0
    net = total_income - total_expenses
    savings_rate = (net / total_income * 100) if total_income > 0 else 0

    return {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net': net,
        'savings_rate': round(savings_rate, 1),
        'category_breakdown': [dict(r) for r in categories]
    }


def get_monthly_trends(months=12):
    conn = get_db()
    c = conn.cursor()

    today = date.today()
    results = []

    for i in range(months - 1, -1, -1):
        # Calculate target month
        month_offset = today.month - 1 - i
        year_offset = today.year + month_offset // 12
        month_num = month_offset % 12 + 1
        if month_offset < 0:
            year_offset = today.year - 1 - ((-month_offset - 1) // 12)
            month_num = 12 - ((-month_offset - 1) % 12)

        c.execute('''SELECT
            COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 0) as income,
            COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as expenses
            FROM transactions
            WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?''',
                  (str(month_num).zfill(2), str(year_offset)))
        row = c.fetchone()
        results.append({
            'month': month_num,
            'year': year_offset,
            'income': row['income'] if row else 0,
            'expenses': row['expenses'] if row else 0,
            'label': f"{calendar.month_abbr[month_num]} {year_offset}"
        })

    conn.close()
    return results


def get_category_spending(month, year):
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT category,
        SUM(amount) as total
        FROM transactions
        WHERE type='expense'
        AND strftime('%m', date) = ? AND strftime('%Y', date) = ?
        GROUP BY category
        ORDER BY total DESC''',
              (str(month).zfill(2), str(year)))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_statements():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM statements ORDER BY statement_year DESC, statement_month DESC, upload_date DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_statement(stmt_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM statements WHERE id=?', (stmt_id,))
    stmt = c.fetchone()
    if not stmt:
        conn.close()
        return None
    c.execute('SELECT * FROM transactions WHERE statement_id=? ORDER BY date DESC', (stmt_id,))
    txns = c.fetchall()
    conn.close()
    result = dict(stmt)
    result['transactions'] = [dict(t) for t in txns]
    return result


def delete_statement(stmt_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT filename FROM statements WHERE id=?', (stmt_id,))
    row = c.fetchone()
    c.execute('DELETE FROM statements WHERE id=?', (stmt_id,))
    conn.commit()
    conn.close()
    if row:
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', row['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)


def get_transactions(month=None, year=None, category=None, txn_type=None):
    conn = get_db()
    c = conn.cursor()
    query = '''SELECT t.*, s.bank_name, s.original_filename
               FROM transactions t
               LEFT JOIN statements s ON t.statement_id = s.id
               WHERE 1=1'''
    params = []
    if month:
        query += " AND strftime('%m', t.date) = ?"
        params.append(str(month).zfill(2))
    if year:
        query += " AND strftime('%Y', t.date) = ?"
        params.append(str(year))
    if category:
        query += " AND t.category = ?"
        params.append(category)
    if txn_type:
        query += " AND t.type = ?"
        params.append(txn_type)
    query += " ORDER BY t.date DESC, t.id DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_transaction_category(txn_id, category):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE transactions SET category=? WHERE id=?', (category, txn_id))
    conn.commit()
    conn.close()


def get_budgets(month, year):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM budgets WHERE month=? AND year=?', (month, year))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_budget(category, month, year, limit):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO budgets (category, monthly_limit, month, year)
                 VALUES (?, ?, ?, ?)
                 ON CONFLICT(category, month, year) DO UPDATE SET monthly_limit=excluded.monthly_limit''',
              (category, limit, month, year))
    conn.commit()
    conn.close()


def get_goals():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM goals ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_goal(data):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO goals (name, type, target_amount, current_amount, monthly_contribution,
                 interest_rate, loan_balance, target_date)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (data.get('name'), data.get('type'), data.get('target_amount', 0),
               data.get('current_amount', 0), data.get('monthly_contribution', 0),
               data.get('interest_rate', 0), data.get('loan_balance', 0),
               data.get('target_date')))
    conn.commit()
    conn.close()


def update_goal(goal_id, data):
    conn = get_db()
    c = conn.cursor()
    c.execute('''UPDATE goals SET name=?, type=?, target_amount=?, current_amount=?,
                 monthly_contribution=?, interest_rate=?, loan_balance=?, target_date=?
                 WHERE id=?''',
              (data.get('name'), data.get('type'), data.get('target_amount', 0),
               data.get('current_amount', 0), data.get('monthly_contribution', 0),
               data.get('interest_rate', 0), data.get('loan_balance', 0),
               data.get('target_date'), goal_id))
    conn.commit()
    conn.close()


def delete_goal(goal_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM goals WHERE id=?', (goal_id,))
    conn.commit()
    conn.close()


def get_profile():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM user_profile WHERE id=1')
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}


def save_profile(data):
    conn = get_db()
    c = conn.cursor()
    c.execute('''UPDATE user_profile SET name=?, family_status=?, num_kids=?,
                 monthly_salary=?, salary_increment_pct=? WHERE id=1''',
              (data.get('name', 'User'), data.get('family_status', 'single'),
               data.get('num_kids', 0), data.get('monthly_salary', 0),
               data.get('salary_increment_pct', 5.0)))
    conn.commit()
    conn.close()


def get_cashflow_settings():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM cashflow_settings WHERE id=1')
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}


def save_cashflow_settings(data):
    conn = get_db()
    c = conn.cursor()
    c.execute('''UPDATE cashflow_settings SET base_monthly_salary=?, salary_increment_pct=?,
                 annual_bonus=?, thirteenth_month_salary=?, other_monthly_income=?,
                 monthly_expenses=?, expense_inflation_pct=?,
                 updated_at=CURRENT_TIMESTAMP WHERE id=1''',
              (data.get('base_monthly_salary', 0), data.get('salary_increment_pct', 5.0),
               data.get('annual_bonus', 0), data.get('thirteenth_month_salary', 0),
               data.get('other_monthly_income', 0), data.get('monthly_expenses', 0),
               data.get('expense_inflation_pct', 3.0)))
    conn.commit()
    conn.close()


def get_extra_incomes():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM extra_income ORDER BY id')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_extra_income(data):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO extra_income (name, amount, frequency, start_year, end_year)
                 VALUES (?, ?, ?, ?, ?)''',
              (data.get('name'), data.get('amount', 0), data.get('frequency', 'monthly'),
               data.get('start_year', 1), data.get('end_year', 10)))
    conn.commit()
    conn.close()


def delete_extra_income(income_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM extra_income WHERE id=?', (income_id,))
    conn.commit()
    conn.close()


def get_distinct_categories():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT DISTINCT category FROM transactions ORDER BY category')
    rows = c.fetchall()
    conn.close()
    return [r['category'] for r in rows]


def insert_transactions_bulk(statement_id, transactions):
    conn = get_db()
    c = conn.cursor()
    total_income = 0
    total_expenses = 0
    for txn in transactions:
        c.execute('''INSERT INTO transactions (statement_id, date, description, amount, type, category)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (statement_id, txn['date'], txn['description'], txn['amount'],
                   txn['type'], txn.get('category', 'Uncategorized')))
        if txn['type'] == 'income':
            total_income += txn['amount']
        else:
            total_expenses += txn['amount']
    c.execute('UPDATE statements SET total_income=?, total_expenses=? WHERE id=?',
              (total_income, total_expenses, statement_id))
    conn.commit()
    conn.close()


def insert_statement(filename, original_filename, bank_name, month, year):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO statements (filename, original_filename, bank_name, statement_month, statement_year)
                 VALUES (?, ?, ?, ?, ?)''',
              (filename, original_filename, bank_name, month, year))
    stmt_id = c.lastrowid
    conn.commit()
    conn.close()
    return stmt_id
