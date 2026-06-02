/**
 * parser.js — CSV and PDF bank statement parser for MoneyMate
 */

/* ── Auto-categorisation ────────────────────────────────────── */
const CATEGORIES = {
  'Food & Dining': ['mcd', 'mcdonalds', 'kfc', 'grab food', 'grabfood', 'restaurant', 'cafe',
    'mamak', 'pizza', 'burger', 'nando', 'subway', 'starbucks', 'food', 'bakery', 'kopitiam',
    'sushi', 'chatime', 'tealive', 'boba', 'old town', 'domino'],
  'Transport': ['myrapid', 'lrt', 'mrt', 'parking', 'toll', 'petrol', 'shell', 'petronas',
    'bhp', 'caltex', 'fuel', 'rapidkl', 'plus', 'highway', 'touch n go', 'tng', 'e-toll',
    'autopay', 'grab'],
  'Utilities': ['tnb', 'syabas', 'telekom', 'maxis', 'celcom', 'digi', 'unifi', 'streamyx',
    'astro', 'water', 'electric', 'gas', 'internet', 'broadband', 'yes 4g', 'u mobile',
    'time dotcom'],
  'Shopping': ['lazada', 'shopee', 'amazon', 'ikea', 'tesco', 'aeon', 'mydin', 'watsons',
    'guardian', '99speedmart', 'speedmart', 'giant', 'jaya grocer', 'village grocer', 'lotus',
    'cold storage', 'kk super mart'],
  'Healthcare': ['hospital', 'klinik', 'clinic', 'pharmacy', 'farmasi', 'doctor', 'dentist',
    'medical', 'health', 'specialist', 'pathlab', 'pantai', 'columbia'],
  'Education': ['school', 'university', 'tuition', 'college', 'institute', 'education',
    'course', 'training', 'udemy', 'coursera', 'yuran', 'sekolah', 'universiti'],
  'Entertainment': ['netflix', 'spotify', 'cinema', 'tgv', 'gsc', 'gaming', 'steam',
    'apple music', 'disney', 'hbo', 'viu', 'iflix', 'movie', 'concert', 'karaoke'],
  'Housing': ['rent', 'rental', 'condo', 'apartment', 'maintenance', 'strata',
    'management fee', 'renovation', 'plumber', 'air cond', 'property'],
  'Insurance': ['great eastern', 'prudential', 'allianz', 'aia', 'insurance', 'takaful',
    'zurich', 'tokio marine', 'premium', 'life insurance', 'medical card', 'motor insurance'],
  'Loan Payment': ['loan', 'mortgage', 'hire purchase', 'pinjaman', 'repayment',
    'instalment', 'installment', 'ptptn', 'personal loan', 'auto loan', 'housing loan'],
  'Salary': ['salary', 'gaji', 'payroll', 'wages', 'emolumen'],
  'Income': ['income', 'dividend', 'interest', 'bonus', 'commission', 'freelance',
    'rental income', 'profit', 'rebate', 'cashback', 'refund', 'payment received',
    'transfer in', 'ibg in', 'duitnow'],
};

const ALL_CATEGORIES = [
  'Food & Dining', 'Transport', 'Utilities', 'Shopping', 'Healthcare', 'Education',
  'Entertainment', 'Housing', 'Insurance', 'Loan Payment', 'Salary', 'Income', 'Uncategorized'
];

function autoCategory(description) {
  const lower = (description || '').toLowerCase();
  for (const [cat, keywords] of Object.entries(CATEGORIES)) {
    for (const kw of keywords) {
      if (lower.includes(kw)) return cat;
    }
  }
  return 'Uncategorized';
}

/* ── Date helpers ───────────────────────────────────────────── */
const MONTH_MAP = {
  jan:1, feb:2, mar:3, apr:4, may:5, jun:6,
  jul:7, aug:8, sep:9, oct:10, nov:11, dec:12
};

function normaliseDate(raw) {
  if (!raw) return null;
  raw = raw.trim();

  // YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;

  // DD/MM/YYYY or DD-MM-YYYY
  let m = raw.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
  if (m) return `${m[3]}-${String(m[2]).padStart(2,'0')}-${String(m[1]).padStart(2,'0')}`;

  // MM/DD/YYYY
  m = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/);
  if (m) {
    const yr = m[3].length === 2 ? '20' + m[3] : m[3];
    return `${yr}-${String(m[1]).padStart(2,'0')}-${String(m[2]).padStart(2,'0')}`;
  }

  // DD MMM YYYY or DD-MMM-YYYY
  m = raw.match(/^(\d{1,2})[\s\-]([A-Za-z]{3})[\s\-](\d{4})$/);
  if (m) {
    const mo = MONTH_MAP[m[2].toLowerCase()];
    if (mo) return `${m[3]}-${String(mo).padStart(2,'0')}-${String(m[1]).padStart(2,'0')}`;
  }

  // MMM DD, YYYY
  m = raw.match(/^([A-Za-z]{3})\s+(\d{1,2}),?\s+(\d{4})$/);
  if (m) {
    const mo = MONTH_MAP[m[1].toLowerCase()];
    if (mo) return `${m[3]}-${String(mo).padStart(2,'0')}-${String(m[2]).padStart(2,'0')}`;
  }

  return null;
}

function cleanAmount(str) {
  if (str === undefined || str === null) return NaN;
  const s = String(str).replace(/[RM$,\s]/g, '').replace(/\(([0-9.]+)\)/, '-$1');
  return parseFloat(s);
}

/* ── CSV Parser ─────────────────────────────────────────────── */
async function parseCSV(file) {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        try {
          const rows = results.data;
          if (!rows.length) { resolve([]); return; }

          const headers = Object.keys(rows[0]).map(h => h.toLowerCase().trim());

          // Find date column
          const dateCol = headers.find(h => /date|tarikh/.test(h));
          // Find description column
          const descCol = headers.find(h => /desc|narr|particular|detail|remark|payee|memo|ref/.test(h)) ||
                          headers.find(h => /name|info|text/.test(h));
          // Find amount columns
          const creditCol = headers.find(h => /credit|masuk|in\b|cr\b|deposit/.test(h));
          const debitCol  = headers.find(h => /debit|keluar|out\b|dr\b|withdraw/.test(h));
          const amtCol    = headers.find(h => /amount|jumlah|balance/.test(h) && !/balance|baki/.test(h));
          // single amount fallback
          const singleAmt = amtCol || headers.find(h => /amount|jumlah/.test(h));

          if (!dateCol) { resolve([]); return; }

          const transactions = [];
          for (const row of rows) {
            const rawDate = row[Object.keys(row)[headers.indexOf(dateCol)]];
            const date = normaliseDate(rawDate);
            if (!date) continue;

            const descKey = descCol ? Object.keys(row)[headers.indexOf(descCol)] : null;
            const description = (descKey ? row[descKey] : Object.values(row).join(' ')).trim();

            let amount = 0;
            let type = 'expense';

            if (creditCol && debitCol) {
              const credit = cleanAmount(row[Object.keys(row)[headers.indexOf(creditCol)]]);
              const debit  = cleanAmount(row[Object.keys(row)[headers.indexOf(debitCol)]]);
              if (!isNaN(credit) && credit > 0) { amount = credit; type = 'income'; }
              else if (!isNaN(debit) && debit > 0) { amount = debit; type = 'expense'; }
              else continue;
            } else if (singleAmt) {
              const raw = cleanAmount(row[Object.keys(row)[headers.indexOf(singleAmt)]]);
              if (isNaN(raw)) continue;
              amount = Math.abs(raw);
              type = raw >= 0 ? 'income' : 'expense';
            } else {
              continue;
            }

            if (amount === 0) continue;

            const category = autoCategory(description);
            // Override type based on category
            const finalType = (category === 'Salary' || category === 'Income') ? 'income' : type;

            transactions.push({ date, description, amount, type: finalType, category });
          }

          resolve(transactions);
        } catch (err) {
          reject(err);
        }
      },
      error: (err) => reject(err)
    });
  });
}

/* ── PDF Parser ─────────────────────────────────────────────── */
async function parsePDF(file, password = '') {
  const arrayBuffer = await file.arrayBuffer();

  let pdf;
  try {
    const loadingTask = pdfjsLib.getDocument({
      data: arrayBuffer,
      password: password || undefined
    });
    pdf = await loadingTask.promise;
  } catch (err) {
    if (err && err.name === 'PasswordException') {
      if (err.code === pdfjsLib.PasswordResponses.NEED_PASSWORD) {
        return { needsPassword: true };
      }
      if (err.code === pdfjsLib.PasswordResponses.INCORRECT_PASSWORD) {
        return { wrongPassword: true };
      }
      return { needsPassword: true };
    }
    throw err;
  }

  // Extract text from all pages
  let fullText = '';
  for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
    const page = await pdf.getPage(pageNum);
    const content = await page.getTextContent();
    const pageText = content.items.map(item => item.str).join(' ');
    fullText += pageText + '\n';
  }

  const transactions = extractTransactionsFromText(fullText);
  return transactions;
}

function extractTransactionsFromText(text) {
  const transactions = [];
  const lines = text.split(/\n/);

  // Patterns to match transaction lines
  const patterns = [
    // DD/MM/YYYY description amount [CR/DR]
    /(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s+(.+?)\s+([\d,]+\.\d{2})\s*(CR|DR)?/i,
    // DD MMM YYYY description amount
    /(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s*(CR|DR)?/i,
    // amount description date (reverse order)
    /([\d,]+\.\d{2})\s+(CR|DR)\s+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})\s+(.+)/i,
  ];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.length < 10) continue;

    for (const pattern of patterns) {
      const m = trimmed.match(pattern);
      if (!m) continue;

      let date, description, amount, crdr;

      if (pattern === patterns[2]) {
        // reverse order
        amount = cleanAmount(m[1]);
        crdr = m[2].toUpperCase();
        date = normaliseDate(m[3]);
        description = m[4].trim();
      } else {
        date = normaliseDate(m[1]);
        description = m[2].trim();
        amount = cleanAmount(m[3]);
        crdr = m[4] ? m[4].toUpperCase() : null;
      }

      if (!date || isNaN(amount) || amount <= 0) continue;

      // Determine type
      let type;
      if (crdr === 'CR') {
        type = 'income';
      } else if (crdr === 'DR') {
        type = 'expense';
      } else {
        // Guess from category
        const cat = autoCategory(description);
        type = (cat === 'Salary' || cat === 'Income') ? 'income' : 'expense';
      }

      const category = autoCategory(description);
      // Override type for clearly income categories
      const finalType = (category === 'Salary' || category === 'Income') ? 'income' : type;

      transactions.push({ date, description, amount, type: finalType, category });
      break; // matched, stop trying other patterns
    }
  }

  return transactions;
}

/* ── Main entry point ───────────────────────────────────────── */
async function parseStatement(file, password = '') {
  const name = file.name.toLowerCase();
  if (name.endsWith('.csv')) return parseCSV(file);
  if (name.endsWith('.pdf')) return parsePDF(file, password);
  // Attempt CSV first
  try {
    return await parseCSV(file);
  } catch {
    return parsePDF(file, password);
  }
}
