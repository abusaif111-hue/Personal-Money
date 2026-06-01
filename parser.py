import re
import os
from datetime import datetime

PDF_AVAILABLE = False
pdfplumber = None
try:
    import subprocess, sys as _sys
    _result = subprocess.run(
        [_sys.executable, '-c', 'import pdfplumber'],
        capture_output=True, timeout=5
    )
    if _result.returncode == 0:
        import pdfplumber
        PDF_AVAILABLE = True
except Exception:
    pass

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except Exception:
    PANDAS_AVAILABLE = False
    pd = None

try:
    from dateutil import parser as dateparser
    DATEUTIL_AVAILABLE = True
except Exception:
    DATEUTIL_AVAILABLE = False
    dateparser = None


CATEGORIES = {
    'Food': [
        'mcd', 'mcdonalds', 'kfc', 'grab food', 'grabfood', 'restaurant', 'cafe', 'mamak',
        'pizza', 'burger', 'nando', 'subway', 'starbucks', 'food', 'eating', 'bakery',
        'kopitiam', 'canteen', 'domino', 'jollibee', 'chicken', 'warung', 'kedai makan',
        'sushi', 'ramen', 'boba', 'tealive', 'chatime', 'toastbox', 'old town'
    ],
    'Transport': [
        'grab', 'myrapid', 'lrt', 'mrt', 'parking', 'toll', 'petrol', 'shell', 'petronas',
        'bhp', 'caltex', 'fuel', 'rapidkl', 'prasarana', 'plus', 'highway', 'bas', 'taxi',
        'uber', 'car', 'kereta', 'autopay', 'smart tag', 'touch n go', 'tng', 'e-toll'
    ],
    'Utilities': [
        'tnb', 'syabas', 'air', 'telekom', 'maxis', 'celcom', 'digi', 'unifi', 'streamyx',
        'astro', 'water', 'electric', 'gas', 'internet', 'broadband', 'utility', 'bills',
        'yes 4g', 'u mobile', 'time dotcom', 'tm berhad'
    ],
    'Shopping': [
        'lazada', 'shopee', 'amazon', 'ikea', 'tesco', 'aeon', 'mydin', 'watsons', 'guardian',
        '99speedmart', 'speedmart', 'giant', 'jaya grocer', 'village grocer', 'lotus',
        'cold storage', 'hero', 'kk super mart', 'convenience', 'retail', 'mall', 'plaza',
        'centre point', 'mid valley', 'sunway', 'pavilion', 'klcc'
    ],
    'Healthcare': [
        'hospital', 'klinik', 'clinic', 'pharmacy', 'farmasi', 'watson', 'guardian', 'doctor',
        'dentist', 'medical', 'health', 'ubat', 'medicine', 'specialist', 'consultation',
        'xray', 'lab test', 'pathlab', 'pantai', 'columbia', 'sunway medical', 'hkl'
    ],
    'Education': [
        'school', 'university', 'tuition', 'book', 'stationery', 'college', 'institute',
        'education', 'learning', 'course', 'class', 'training', 'upskill', 'udemy',
        'coursera', 'fees', 'yuran', 'sekolah', 'universiti'
    ],
    'Entertainment': [
        'netflix', 'spotify', 'cinema', 'tgv', 'gsc', 'game', 'gaming', 'steam', 'playstation',
        'xbox', 'apple music', 'youtube', 'disney', 'hbo', 'viu', 'iflix', 'entertainment',
        'movie', 'concert', 'karaoke', 'bowling', 'recreation'
    ],
    'Housing': [
        'rent', 'rental', 'condo', 'apartment', 'maintenance', 'strata', 'management fee',
        'rumah', 'sewaan', 'deposit', 'renovation', 'plumber', 'electric repair', 'air cond',
        'property', 'housing', 'home', 'house'
    ],
    'Insurance': [
        'great eastern', 'prudential', 'allianz', 'aia', 'insurance', 'takaful', 'zurich',
        'tokio marine', 'msig', 'lonpac', 'berjaya sompo', 'premium', 'life insurance',
        'medical card', 'motor insurance', 'vehicle insurance'
    ],
    'Loan Payment': [
        'loan', 'mortgage', 'hire purchase', 'kereta', 'rumah', 'pinjaman', 'bayaran',
        'repayment', 'instalment', 'installment', 'ptptn', 'bank loan', 'personal loan',
        'auto loan', 'housing loan', 'home loan'
    ],
    'Salary': [
        'salary', 'gaji', 'payroll', 'wages', 'emolumen', 'allowance', 'epf contribution',
        'kwsp', 'bonus salary', 'increment'
    ],
    'Income': [
        'income', 'dividend', 'interest', 'bonus', 'commission', 'freelance', 'rental income',
        'profit', 'return', 'rebate', 'cashback', 'refund', 'reward', 'payment received',
        'transfer in', 'ibg in', 'fpx', 'duitnow', 'payment from'
    ],
}


def auto_categorize(description):
    """Keyword-based auto categorization of transactions."""
    if not description:
        return 'Uncategorized'

    desc_lower = description.lower()

    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            if keyword in desc_lower:
                return category

    return 'Uncategorized'


def _parse_date(date_str):
    """Try to parse a date string into YYYY-MM-DD format."""
    if not date_str:
        return None
    date_str = str(date_str).strip()

    # Try common formats
    formats = [
        '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y', '%d-%m-%y',
        '%Y/%m/%d', '%m/%d/%Y', '%m-%d-%Y', '%d %b %Y', '%d %B %Y',
        '%b %d, %Y', '%B %d, %Y', '%d %b %y', '%Y%m%d'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue

    if DATEUTIL_AVAILABLE:
        try:
            return dateparser.parse(date_str, dayfirst=True).strftime('%Y-%m-%d')
        except Exception:
            pass

    return None


def _clean_amount(amount_str):
    """Clean and convert amount string to float."""
    if amount_str is None:
        return None
    if isinstance(amount_str, (int, float)):
        return float(amount_str)
    s = str(amount_str).strip()
    # Remove currency symbols and commas
    s = re.sub(r'[RM$,\s]', '', s)
    s = re.sub(r'\(([0-9.]+)\)', r'-\1', s)  # (123.45) -> -123.45
    try:
        return float(s)
    except ValueError:
        return None


def parse_csv(filepath):
    """Parse CSV bank statement."""
    if not PANDAS_AVAILABLE:
        return []

    transactions = []

    try:
        # Try different encodings
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                df = pd.read_csv(filepath, encoding=encoding)
                break
            except Exception:
                continue
        else:
            return []

        # Normalize column names
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Find date column
        date_col = None
        for col in df.columns:
            if any(k in col for k in ['date', 'tarikh', 'tgl', 'dt']):
                date_col = col
                break

        # Find description column
        desc_col = None
        for col in df.columns:
            if any(k in col for k in ['description', 'desc', 'particulars', 'narration',
                                        'detail', 'remark', 'keterangan', 'memo', 'reference']):
                desc_col = col
                break

        # Find amount columns
        credit_col = None
        debit_col = None
        amount_col = None

        for col in df.columns:
            if any(k in col for k in ['credit', 'cr', 'deposit', 'masuk', 'in']):
                credit_col = col
            if any(k in col for k in ['debit', 'dr', 'withdrawal', 'keluar', 'out']):
                debit_col = col
            if col == 'amount' or col == 'jumlah':
                amount_col = col

        if date_col is None:
            # Try first column as date
            date_col = df.columns[0]

        if desc_col is None:
            # Try second column as description
            if len(df.columns) > 1:
                desc_col = df.columns[1]

        for _, row in df.iterrows():
            date_val = _parse_date(row.get(date_col, ''))
            if not date_val:
                continue

            desc = str(row.get(desc_col, '')).strip() if desc_col else 'Unknown'
            if not desc or desc == 'nan':
                continue

            amount = None
            txn_type = None

            if credit_col and debit_col:
                credit = _clean_amount(row.get(credit_col))
                debit = _clean_amount(row.get(debit_col))
                if credit and credit > 0:
                    amount = credit
                    txn_type = 'income'
                elif debit and debit > 0:
                    amount = debit
                    txn_type = 'expense'
                elif credit and credit < 0:
                    amount = abs(credit)
                    txn_type = 'expense'
                elif debit and debit < 0:
                    amount = abs(debit)
                    txn_type = 'income'
            elif amount_col:
                val = _clean_amount(row.get(amount_col))
                if val is not None:
                    if val >= 0:
                        amount = val
                        txn_type = 'income'
                    else:
                        amount = abs(val)
                        txn_type = 'expense'
            else:
                # Try to find any numeric column
                for col in df.columns:
                    if col not in [date_col, desc_col]:
                        val = _clean_amount(row.get(col))
                        if val is not None:
                            if val >= 0:
                                amount = val
                                txn_type = 'income'
                            else:
                                amount = abs(val)
                                txn_type = 'expense'
                            break

            if amount is None or amount == 0:
                continue

            category = auto_categorize(desc)
            # Override category for income
            if txn_type == 'income' and category == 'Uncategorized':
                category = 'Income'

            transactions.append({
                'date': date_val,
                'description': desc[:255],
                'amount': round(amount, 2),
                'type': txn_type,
                'category': category
            })

    except Exception as e:
        print(f"CSV parse error: {e}")

    return transactions


def parse_pdf(filepath, password=None):
    """Parse PDF bank statement using pdfplumber. Supports password-protected PDFs."""
    if not PDF_AVAILABLE:
        return []

    transactions = []
    open_kwargs = {'password': password} if password else {}

    try:
        with pdfplumber.open(filepath, **open_kwargs) as pdf:
            # Detect if PDF is encrypted but wrong/no password given
            if pdf.doc.is_encrypted and not pdf.doc.authenticate(password or ''):
                raise ValueError("WRONG_PASSWORD")

            full_text = ''
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + '\n'

            transactions = _parse_text_transactions(full_text)

            # If text extraction failed, try table extraction
            if not transactions:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        transactions.extend(_parse_table_transactions(table))

    except ValueError:
        raise
    except Exception as e:
        print(f"PDF parse error: {e}")

    return transactions


def _parse_text_transactions(text):
    """Parse transactions from extracted PDF text."""
    transactions = []

    # Common patterns for bank statement lines
    # Pattern: DD/MM/YYYY or DD-MM-YYYY followed by description and amount
    patterns = [
        # Date Description Amount
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.\d{2})\s*(?:CR|DR)?\s*$',
        # Date Description Credit Debit
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.\d{2})?\s*([\d,]+\.\d{2})?\s*$',
        # DD MMM YYYY format
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4})\s+(.+?)\s+([\d,]+\.\d{2})',
    ]

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                date_str = groups[0]
                desc = groups[1].strip()
                date_val = _parse_date(date_str)

                if not date_val or not desc:
                    continue

                # Try to determine amount and type
                amount = None
                txn_type = None

                if len(groups) == 3:
                    # Single amount column
                    amount = _clean_amount(groups[2])
                    if amount:
                        # Check for CR/DR indicators
                        if 'CR' in line.upper():
                            txn_type = 'income'
                        elif 'DR' in line.upper():
                            txn_type = 'expense'
                        else:
                            # Use auto-categorization to guess
                            cat = auto_categorize(desc)
                            txn_type = 'income' if cat in ['Salary', 'Income'] else 'expense'

                elif len(groups) == 4:
                    credit = _clean_amount(groups[2]) if groups[2] else None
                    debit = _clean_amount(groups[3]) if groups[3] else None
                    if credit and credit > 0:
                        amount = credit
                        txn_type = 'income'
                    elif debit and debit > 0:
                        amount = debit
                        txn_type = 'expense'

                if amount and amount > 0 and txn_type:
                    category = auto_categorize(desc)
                    if txn_type == 'income' and category == 'Uncategorized':
                        category = 'Income'

                    transactions.append({
                        'date': date_val,
                        'description': desc[:255],
                        'amount': round(amount, 2),
                        'type': txn_type,
                        'category': category
                    })
                break

    return transactions


def _parse_table_transactions(table):
    """Parse transactions from a PDF table."""
    transactions = []

    if not table or len(table) < 2:
        return transactions

    # Try to identify header row
    header = [str(c).strip().lower() if c else '' for c in table[0]]

    date_idx = None
    desc_idx = None
    credit_idx = None
    debit_idx = None
    amount_idx = None

    for i, col in enumerate(header):
        if any(k in col for k in ['date', 'tarikh']):
            date_idx = i
        elif any(k in col for k in ['description', 'desc', 'particular', 'detail', 'narration']):
            desc_idx = i
        elif any(k in col for k in ['credit', 'cr', 'deposit']):
            credit_idx = i
        elif any(k in col for k in ['debit', 'dr', 'withdrawal']):
            debit_idx = i
        elif 'amount' in col or 'jumlah' in col:
            amount_idx = i

    if date_idx is None:
        date_idx = 0
    if desc_idx is None:
        desc_idx = 1 if len(header) > 1 else 0

    for row in table[1:]:
        if not row or len(row) <= date_idx:
            continue

        date_val = _parse_date(str(row[date_idx]) if row[date_idx] else '')
        if not date_val:
            continue

        desc = str(row[desc_idx]).strip() if desc_idx < len(row) and row[desc_idx] else 'Unknown'
        if not desc or desc == 'None':
            continue

        amount = None
        txn_type = None

        if credit_idx is not None and debit_idx is not None:
            credit = _clean_amount(row[credit_idx] if credit_idx < len(row) else None)
            debit = _clean_amount(row[debit_idx] if debit_idx < len(row) else None)
            if credit and credit > 0:
                amount = credit
                txn_type = 'income'
            elif debit and debit > 0:
                amount = debit
                txn_type = 'expense'
        elif amount_idx is not None:
            val = _clean_amount(row[amount_idx] if amount_idx < len(row) else None)
            if val is not None:
                if val >= 0:
                    amount = val
                    txn_type = 'income'
                else:
                    amount = abs(val)
                    txn_type = 'expense'

        if amount and amount > 0 and txn_type:
            category = auto_categorize(desc)
            if txn_type == 'income' and category == 'Uncategorized':
                category = 'Income'

            transactions.append({
                'date': date_val,
                'description': desc[:255],
                'amount': round(amount, 2),
                'type': txn_type,
                'category': category
            })

    return transactions


def parse_statement(filepath, filename, password=None):
    """Parse a bank statement file (PDF or CSV) and return list of transactions."""
    ext = os.path.splitext(filename)[1].lower()

    if ext == '.csv':
        transactions = parse_csv(filepath)
    elif ext == '.pdf':
        transactions = parse_pdf(filepath, password=password)
    else:
        transactions = parse_csv(filepath)
        if not transactions:
            transactions = parse_pdf(filepath, password=password)

    return transactions
