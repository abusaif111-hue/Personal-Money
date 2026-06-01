import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename

import database as db
from parser import parse_statement

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'moneymate-secret-key-2024')

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'csv'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_spending_recommendations(family_status):
    """Return recommended spending percentages based on family status."""
    recommendations = {
        'single': {
            'Housing': 30, 'Food': 15, 'Transport': 10, 'Utilities': 5,
            'Entertainment': 10, 'Savings': 20, 'Others': 10
        },
        'married': {
            'Housing': 35, 'Food': 20, 'Transport': 10, 'Utilities': 8,
            'Entertainment': 5, 'Savings': 15, 'Others': 7
        },
        'married_with_kids': {
            'Housing': 35, 'Food': 22, 'Transport': 12, 'Utilities': 8,
            'Entertainment': 3, 'Education': 10, 'Savings': 10
        }
    }
    return recommendations.get(family_status, recommendations['single'])


def check_overspending(category_breakdown, total_income, family_status):
    """Check if any category exceeds recommendations by >20%."""
    alerts = []
    if total_income <= 0:
        return alerts

    recommendations = get_spending_recommendations(family_status)

    for item in category_breakdown:
        cat = item['category']
        spent = item['spent']
        pct_of_income = (spent / total_income) * 100

        if cat in recommendations:
            recommended_pct = recommendations[cat]
            threshold = recommended_pct * 1.2  # 20% over recommendation
            if pct_of_income > threshold:
                alerts.append({
                    'category': cat,
                    'spent': spent,
                    'spent_pct': round(pct_of_income, 1),
                    'recommended_pct': recommended_pct,
                    'threshold_pct': round(threshold, 1)
                })

    return alerts


def calculate_cashflow(settings, extra_incomes, goals):
    """Calculate 10-year cash flow projection."""
    results = []
    cumulative_savings = 0

    base_salary = settings.get('base_monthly_salary', 0) or 0
    increment_pct = settings.get('salary_increment_pct', 5.0) or 5.0
    annual_bonus = settings.get('annual_bonus', 0) or 0
    thirteenth = settings.get('thirteenth_month_salary', 0) or 0
    other_monthly = settings.get('other_monthly_income', 0) or 0
    monthly_expenses = settings.get('monthly_expenses', 0) or 0
    inflation_pct = settings.get('expense_inflation_pct', 3.0) or 3.0

    for year in range(1, 11):
        # Salary grows each year
        monthly_salary = base_salary * ((1 + increment_pct / 100) ** (year - 1))
        annual_salary = monthly_salary * 12

        # Bonuses
        year_bonus = annual_bonus
        year_thirteenth = thirteenth

        # Other income
        other_annual = other_monthly * 12

        # Extra income sources
        for ei in extra_incomes:
            start = ei.get('start_year', 1) or 1
            end = ei.get('end_year', 10) or 10
            if start <= year <= end:
                freq = ei.get('frequency', 'monthly')
                amount = ei.get('amount', 0) or 0
                if freq == 'monthly':
                    other_annual += amount * 12
                elif freq == 'annual':
                    other_annual += amount
                elif freq == 'one_time' and year == start:
                    other_annual += amount

        total_income = annual_salary + year_bonus + year_thirteenth + other_annual

        # Expenses grow with inflation
        annual_expenses = monthly_expenses * 12 * ((1 + inflation_pct / 100) ** (year - 1))

        # Goal payments
        goal_payments = sum((g.get('monthly_contribution', 0) or 0) * 12 for g in goals)

        net = total_income - annual_expenses - goal_payments
        cumulative_savings += net

        results.append({
            'year': year,
            'annual_income': round(total_income, 2),
            'annual_expenses': round(annual_expenses, 2),
            'goal_payments': round(goal_payments, 2),
            'net_savings': round(net, 2),
            'cumulative_savings': round(cumulative_savings, 2),
            'monthly_salary': round(monthly_salary, 2)
        })

    return results


# ─────────────────────── MAIN ROUTES ───────────────────────

@app.route('/')
def dashboard():
    now = datetime.now()
    month = request.args.get('month', now.month, type=int)
    year = request.args.get('year', now.year, type=int)

    stats = db.get_dashboard_stats(month, year)
    recent_txns = db.get_transactions(month=month, year=year)[:10]
    profile = db.get_profile()
    family_status = profile.get('family_status', 'single')
    recommendations = get_spending_recommendations(family_status)
    alerts = check_overspending(
        stats['category_breakdown'], stats['total_income'], family_status
    )

    months_list = [(i, datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)]
    years_list = list(range(now.year - 3, now.year + 2))

    return render_template(
        'dashboard.html',
        stats=stats,
        recent_txns=recent_txns,
        profile=profile,
        alerts=alerts,
        recommendations=recommendations,
        month=month,
        year=year,
        months_list=months_list,
        years_list=years_list,
        current_month_name=datetime(year, month, 1).strftime('%B %Y')
    )


@app.route('/statements')
def statements():
    all_statements = db.get_all_statements()
    now = datetime.now()
    months_list = [(i, datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)]
    years_list = list(range(now.year - 5, now.year + 2))
    return render_template(
        'statements.html',
        statements=all_statements,
        months_list=months_list,
        years_list=years_list,
        current_month=now.month,
        current_year=now.year
    )


@app.route('/statements/upload', methods=['POST'])
def upload_statement():
    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('statements'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('statements'))

    if not allowed_file(file.filename):
        flash('Only PDF and CSV files are supported.', 'danger')
        return redirect(url_for('statements'))

    bank_name = request.form.get('bank_name', 'Unknown')
    month = request.form.get('month', datetime.now().month, type=int)
    year = request.form.get('year', datetime.now().year, type=int)
    pdf_password = request.form.get('pdf_password', '').strip() or None

    original_filename = secure_filename(file.filename)
    ext = original_filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)

    try:
        file.save(filepath)
        stmt_id = db.insert_statement(unique_filename, original_filename, bank_name, month, year)
        transactions = parse_statement(filepath, original_filename, password=pdf_password)

        if transactions:
            db.insert_transactions_bulk(stmt_id, transactions)
            flash(f'Statement uploaded successfully! Parsed {len(transactions)} transactions.', 'success')
        else:
            flash('Statement uploaded, but no transactions could be parsed. You can add transactions manually.', 'warning')

    except ValueError as e:
        if 'WRONG_PASSWORD' in str(e):
            flash('Incorrect PDF password. Please check the password and try again.', 'danger')
        else:
            flash(f'Error processing file: {str(e)}', 'danger')
        db.delete_statement(stmt_id) if 'stmt_id' in dir() else None
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'danger')
        if os.path.exists(filepath):
            os.remove(filepath)

    return redirect(url_for('statements'))


@app.route('/statements/<int:stmt_id>/delete', methods=['POST'])
def delete_statement(stmt_id):
    try:
        db.delete_statement(stmt_id)
        flash('Statement deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting statement: {str(e)}', 'danger')
    return redirect(url_for('statements'))


@app.route('/transactions')
def transactions():
    now = datetime.now()
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    category = request.args.get('category', '')
    txn_type = request.args.get('type', '')

    txns = db.get_transactions(
        month=month if month else None,
        year=year if year else None,
        category=category if category else None,
        txn_type=txn_type if txn_type else None
    )

    categories = db.get_distinct_categories()
    months_list = [(i, datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)]
    years_list = list(range(now.year - 5, now.year + 2))

    all_categories = [
        'Food', 'Transport', 'Utilities', 'Shopping', 'Healthcare', 'Education',
        'Entertainment', 'Housing', 'Insurance', 'Loan Payment', 'Salary', 'Income', 'Uncategorized'
    ]

    return render_template(
        'transactions.html',
        transactions=txns,
        categories=categories,
        all_categories=all_categories,
        months_list=months_list,
        years_list=years_list,
        filter_month=month or '',
        filter_year=year or '',
        filter_category=category,
        filter_type=txn_type
    )


@app.route('/transactions/<int:txn_id>/update', methods=['POST'])
def update_transaction(txn_id):
    category = request.form.get('category', 'Uncategorized')
    db.update_transaction_category(txn_id, category)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    flash('Transaction category updated.', 'success')
    return redirect(request.referrer or url_for('transactions'))


@app.route('/budget')
def budget():
    now = datetime.now()
    month = request.args.get('month', now.month, type=int)
    year = request.args.get('year', now.year, type=int)

    budgets = db.get_budgets(month, year)
    category_spending = db.get_category_spending(month, year)

    budget_map = {b['category']: b['monthly_limit'] for b in budgets}
    spending_map = {s['category']: s['total'] for s in category_spending}

    expense_categories = [
        'Food', 'Transport', 'Utilities', 'Shopping', 'Healthcare', 'Education',
        'Entertainment', 'Housing', 'Insurance', 'Loan Payment', 'Uncategorized'
    ]

    budget_data = []
    for cat in expense_categories:
        limit = budget_map.get(cat, 0)
        actual = spending_map.get(cat, 0)
        pct = (actual / limit * 100) if limit > 0 else (100 if actual > 0 else 0)
        status = 'over' if (limit > 0 and actual > limit) else 'ok' if limit > 0 else 'no_budget'
        budget_data.append({
            'category': cat,
            'limit': limit,
            'actual': actual,
            'pct': min(pct, 100),
            'bar_pct': min(pct, 100),
            'status': status
        })

    months_list = [(i, datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)]
    years_list = list(range(now.year - 3, now.year + 2))

    return render_template(
        'budget.html',
        budget_data=budget_data,
        month=month,
        year=year,
        months_list=months_list,
        years_list=years_list,
        current_month_name=datetime(year, month, 1).strftime('%B %Y')
    )


@app.route('/budget/set', methods=['POST'])
def set_budget():
    category = request.form.get('category')
    month = request.form.get('month', type=int)
    year = request.form.get('year', type=int)
    limit = request.form.get('limit', type=float)

    if not all([category, month, year, limit is not None]):
        flash('Invalid budget data.', 'danger')
        return redirect(url_for('budget'))

    db.set_budget(category, month, year, limit)
    flash(f'Budget for {category} updated.', 'success')
    return redirect(url_for('budget', month=month, year=year))


@app.route('/goals')
def goals():
    all_goals = db.get_goals()
    return render_template('goals.html', goals=all_goals)


@app.route('/goals/add', methods=['POST'])
def add_goal():
    data = {
        'name': request.form.get('name'),
        'type': request.form.get('type', 'savings'),
        'target_amount': request.form.get('target_amount', 0, type=float),
        'current_amount': request.form.get('current_amount', 0, type=float),
        'monthly_contribution': request.form.get('monthly_contribution', 0, type=float),
        'interest_rate': request.form.get('interest_rate', 0, type=float),
        'loan_balance': request.form.get('loan_balance', 0, type=float),
        'target_date': request.form.get('target_date') or None
    }
    if not data['name']:
        flash('Goal name is required.', 'danger')
        return redirect(url_for('goals'))

    db.add_goal(data)
    flash('Goal added successfully!', 'success')
    return redirect(url_for('goals'))


@app.route('/goals/<int:goal_id>/update', methods=['POST'])
def update_goal(goal_id):
    data = {
        'name': request.form.get('name'),
        'type': request.form.get('type', 'savings'),
        'target_amount': request.form.get('target_amount', 0, type=float),
        'current_amount': request.form.get('current_amount', 0, type=float),
        'monthly_contribution': request.form.get('monthly_contribution', 0, type=float),
        'interest_rate': request.form.get('interest_rate', 0, type=float),
        'loan_balance': request.form.get('loan_balance', 0, type=float),
        'target_date': request.form.get('target_date') or None
    }
    db.update_goal(goal_id, data)
    flash('Goal updated successfully!', 'success')
    return redirect(url_for('goals'))


@app.route('/goals/<int:goal_id>/delete', methods=['POST'])
def delete_goal(goal_id):
    db.delete_goal(goal_id)
    flash('Goal deleted.', 'success')
    return redirect(url_for('goals'))


@app.route('/cashflow')
def cashflow():
    settings = db.get_cashflow_settings()
    extra_incomes = db.get_extra_incomes()
    goals = db.get_goals()
    projection = calculate_cashflow(settings, extra_incomes, goals)
    return render_template(
        'cashflow.html',
        settings=settings,
        extra_incomes=extra_incomes,
        goals=goals,
        projection=projection
    )


@app.route('/cashflow/save', methods=['POST'])
def save_cashflow():
    data = {
        'base_monthly_salary': request.form.get('base_monthly_salary', 0, type=float),
        'salary_increment_pct': request.form.get('salary_increment_pct', 5.0, type=float),
        'annual_bonus': request.form.get('annual_bonus', 0, type=float),
        'thirteenth_month_salary': request.form.get('thirteenth_month_salary', 0, type=float),
        'other_monthly_income': request.form.get('other_monthly_income', 0, type=float),
        'monthly_expenses': request.form.get('monthly_expenses', 0, type=float),
        'expense_inflation_pct': request.form.get('expense_inflation_pct', 3.0, type=float)
    }
    db.save_cashflow_settings(data)
    flash('Cash flow settings saved.', 'success')
    return redirect(url_for('cashflow'))


@app.route('/cashflow/extra-income/add', methods=['POST'])
def add_extra_income():
    data = {
        'name': request.form.get('name'),
        'amount': request.form.get('amount', 0, type=float),
        'frequency': request.form.get('frequency', 'monthly'),
        'start_year': request.form.get('start_year', 1, type=int),
        'end_year': request.form.get('end_year', 10, type=int)
    }
    if not data['name']:
        flash('Income source name is required.', 'danger')
        return redirect(url_for('cashflow'))

    db.add_extra_income(data)
    flash('Extra income source added.', 'success')
    return redirect(url_for('cashflow'))


@app.route('/cashflow/extra-income/<int:income_id>/delete', methods=['POST'])
def delete_extra_income(income_id):
    db.delete_extra_income(income_id)
    flash('Extra income source removed.', 'success')
    return redirect(url_for('cashflow'))


@app.route('/profile')
def profile():
    user_profile = db.get_profile()
    return render_template('profile.html', profile=user_profile)


@app.route('/profile/save', methods=['POST'])
def save_profile():
    data = {
        'name': request.form.get('name', 'User'),
        'family_status': request.form.get('family_status', 'single'),
        'num_kids': request.form.get('num_kids', 0, type=int),
        'monthly_salary': request.form.get('monthly_salary', 0, type=float),
        'salary_increment_pct': request.form.get('salary_increment_pct', 5.0, type=float)
    }
    db.save_profile(data)
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))


# ─────────────────────── API ROUTES ───────────────────────

@app.route('/api/dashboard-stats')
def api_dashboard_stats():
    now = datetime.now()
    month = request.args.get('month', now.month, type=int)
    year = request.args.get('year', now.year, type=int)
    stats = db.get_dashboard_stats(month, year)
    return jsonify(stats)


@app.route('/api/monthly-trends')
def api_monthly_trends():
    trends = db.get_monthly_trends(12)
    return jsonify(trends)


@app.route('/api/cashflow-data')
def api_cashflow_data():
    settings = db.get_cashflow_settings()
    extra_incomes = db.get_extra_incomes()
    goals = db.get_goals()
    projection = calculate_cashflow(settings, extra_incomes, goals)
    return jsonify(projection)


@app.route('/api/budget-vs-actual')
def api_budget_vs_actual():
    now = datetime.now()
    month = request.args.get('month', now.month, type=int)
    year = request.args.get('year', now.year, type=int)

    budgets = db.get_budgets(month, year)
    category_spending = db.get_category_spending(month, year)

    budget_map = {b['category']: b['monthly_limit'] for b in budgets}
    spending_map = {s['category']: s['total'] for s in category_spending}

    all_cats = set(list(budget_map.keys()) + list(spending_map.keys()))
    result = []
    for cat in all_cats:
        budget_limit = budget_map.get(cat, 0)
        actual = spending_map.get(cat, 0)
        if budget_limit > 0 and actual > budget_limit:
            status = 'over'
        elif budget_limit > 0:
            status = 'ok'
        else:
            status = 'no_budget'
        result.append({
            'category': cat,
            'budget': budget_limit,
            'actual': actual,
            'status': status
        })

    return jsonify(result)


db.init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
