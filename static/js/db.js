/**
 * db.js — IndexedDB wrapper for MoneyMate
 * Database: MoneyMateDB  Version: 1
 */

const db = (() => {
  const DB_NAME = 'MoneyMateDB';
  const DB_VERSION = 1;
  let _db = null;

  /* ── Open / Upgrade ─────────────────────────────────────────── */
  function init() {
    return new Promise((resolve, reject) => {
      if (_db) { resolve(_db); return; }

      const req = indexedDB.open(DB_NAME, DB_VERSION);

      req.onupgradeneeded = (e) => {
        const database = e.target.result;

        // statements
        if (!database.objectStoreNames.contains('statements')) {
          database.createObjectStore('statements', { keyPath: 'id', autoIncrement: true });
        }

        // transactions
        if (!database.objectStoreNames.contains('transactions')) {
          const txStore = database.createObjectStore('transactions', { keyPath: 'id', autoIncrement: true });
          txStore.createIndex('statementId', 'statementId', { unique: false });
          txStore.createIndex('type', 'type', { unique: false });
          txStore.createIndex('month', 'month', { unique: false });
        }

        // budgets
        if (!database.objectStoreNames.contains('budgets')) {
          const budgetStore = database.createObjectStore('budgets', { keyPath: 'id', autoIncrement: true });
          budgetStore.createIndex('month', 'month', { unique: false });
          budgetStore.createIndex('month_year', ['month', 'year'], { unique: false });
        }

        // goals
        if (!database.objectStoreNames.contains('goals')) {
          database.createObjectStore('goals', { keyPath: 'id', autoIncrement: true });
        }

        // profile (single record, id=1)
        if (!database.objectStoreNames.contains('profile')) {
          database.createObjectStore('profile', { keyPath: 'id' });
        }

        // cashflowSettings (single record, id=1)
        if (!database.objectStoreNames.contains('cashflowSettings')) {
          database.createObjectStore('cashflowSettings', { keyPath: 'id' });
        }

        // extraIncomes
        if (!database.objectStoreNames.contains('extraIncomes')) {
          database.createObjectStore('extraIncomes', { keyPath: 'id', autoIncrement: true });
        }
      };

      req.onsuccess = async (e) => {
        _db = e.target.result;

        // Insert defaults if not present
        try {
          const profile = await _get('profile', 1).catch(() => null);
          if (!profile) {
            await _put('profile', { id: 1, name: 'User', familyStatus: 'single', numKids: 0 });
          }

          const cf = await _get('cashflowSettings', 1).catch(() => null);
          if (!cf) {
            await _put('cashflowSettings', {
              id: 1,
              baseMonthlySalary: 0,
              salaryIncrementPct: 5,
              annualBonus: 0,
              thirteenthMonthSalary: 0,
              otherMonthlyIncome: 0,
              monthlyExpenses: 0,
              expenseInflationPct: 3
            });
          }
        } catch (err) {
          console.warn('db.init defaults:', err);
        }

        resolve(_db);
      };

      req.onerror = () => reject(req.error);
      req.onblocked = () => reject(new Error('Database blocked — please close other tabs.'));
    });
  }

  /* ── Low-level helpers ──────────────────────────────────────── */
  function _store(storeName, mode) {
    if (!_db) throw new Error('DB not initialised — call db.init() first.');
    return _db.transaction(storeName, mode).objectStore(storeName);
  }

  function _req(idbRequest) {
    return new Promise((resolve, reject) => {
      idbRequest.onsuccess = () => resolve(idbRequest.result);
      idbRequest.onerror  = () => reject(idbRequest.error);
    });
  }

  function _get(storeName, id) {
    return _req(_store(storeName, 'readonly').get(id));
  }

  function _put(storeName, data) {
    return _req(_store(storeName, 'readwrite').put(data));
  }

  /* ── Public API ─────────────────────────────────────────────── */

  async function getAll(storeName) {
    await init();
    return _req(_store(storeName, 'readonly').getAll());
  }

  async function get(storeName, id) {
    await init();
    return _get(storeName, id);
  }

  async function add(storeName, data) {
    await init();
    return _req(_store(storeName, 'readwrite').add(data));
  }

  async function update(storeName, data) {
    await init();
    return _put(storeName, data);
  }

  async function del(storeName, id) {
    await init();
    return _req(_store(storeName, 'readwrite').delete(id));
  }

  async function clear(storeName) {
    await init();
    return _req(_store(storeName, 'readwrite').clear());
  }

  async function getAllByIndex(storeName, indexName, value) {
    await init();
    const store = _store(storeName, 'readonly');
    const index = store.index(indexName);
    return _req(index.getAll(value));
  }

  async function getFiltered(storeName, filterFn) {
    const all = await getAll(storeName);
    return all.filter(filterFn);
  }

  /* ── Convenience: bulk insert transactions ──────────────────── */
  async function addBulk(storeName, records) {
    await init();
    const tx = _db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    const ids = [];
    for (const rec of records) {
      const id = await _req(store.add(rec));
      ids.push(id);
    }
    return ids;
  }

  return {
    init,
    getAll,
    get,
    add,
    update,
    delete: del,
    clear,
    getAllByIndex,
    getFiltered,
    addBulk
  };
})();
