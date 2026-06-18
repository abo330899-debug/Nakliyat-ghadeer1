(() => {
  "use strict";

  const API_BASE = '/api';

  const KEYS = {
    CLIENTS: "ghadeer:clients",
    INVOICES: "ghadeer:invoices",
    PAYMENTS: "ghadeer:payments",
    EXPENSES: "ghadeer:expenses",
    TRASH: "ghadeer:trash",
    META: "ghadeer:meta",
  };

  async function apiGet(endpoint) {
    const res = await fetch(`${API_BASE}${endpoint}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function apiPost(endpoint, data) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function apiPut(endpoint, data) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function apiDelete(endpoint) {
    const res = await fetch(`${API_BASE}${endpoint}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    return res.json();
  }

  let clientsCache = null;
  let invoicesCache = {};
  let paymentsCache = {};
  let expensesCache = null;

  const GhadeerDB = {
    KEYS,

    migrateOnce() {},

    async getClientsAsync() {
      const clients = await apiGet('/clients');
      clientsCache = clients;
      return clients;
    },

    getClients() {
      if (clientsCache) return clientsCache;
      apiGet('/clients').then(c => { clientsCache = c; }).catch(() => {});
      return clientsCache || [];
    },

    async addClientAsync({ name, phone = "", company = "" }) {
      const client = await apiPost('/clients', { name, phone, company });
      clientsCache = null;
      return client;
    },

    addClient({ name, phone = "", company = "" }) {
      apiPost('/clients', { name, phone, company })
        .then(() => { clientsCache = null; })
        .catch(e => console.error('Error adding client:', e));
      return { id: 'pending', name, phone, company, createdAt: Date.now() };
    },

    async deleteClientByIdAsync(clientId) {
      await apiDelete(`/clients/${encodeURIComponent(clientId)}`);
      clientsCache = null;
      return true;
    },

    deleteClientById(clientId) {
      apiDelete(`/clients/${encodeURIComponent(clientId)}`)
        .then(() => { clientsCache = null; })
        .catch(e => console.error('Error deleting client:', e));
      return true;
    },

    async updateClientByIdAsync(clientId, patch) {
      const client = await apiPut(`/clients/${encodeURIComponent(clientId)}`, patch);
      clientsCache = null;
      return client;
    },

    updateClientById(clientId, patch) {
      apiPut(`/clients/${encodeURIComponent(clientId)}`, patch)
        .then(() => { clientsCache = null; })
        .catch(e => console.error('Error updating client:', e));
      return patch;
    },

    async getInvoicesAsync() {
      return apiGet('/invoices');
    },

    async getInvoicesByClientAsync(clientId) {
      const invoices = await apiGet(`/invoices?clientId=${encodeURIComponent(clientId)}`);
      invoicesCache[clientId] = invoices;
      return invoices;
    },

    getInvoicesByClient(clientId) {
      if (invoicesCache[clientId]) return invoicesCache[clientId];
      apiGet(`/invoices?clientId=${encodeURIComponent(clientId)}`)
        .then(i => { invoicesCache[clientId] = i; })
        .catch(() => {});
      return invoicesCache[clientId] || [];
    },

    async addInvoiceAsync({ clientId, date, note = "—", amount }) {
      const invoice = await apiPost('/invoices', { clientId, date, note, amount });
      delete invoicesCache[clientId];
      return invoice;
    },

    addInvoice({ clientId, date, note = "—", amount }) {
      apiPost('/invoices', { clientId, date, note, amount })
        .then(() => { delete invoicesCache[clientId]; })
        .catch(e => console.error('Error adding invoice:', e));
      return { id: 'pending', clientId, date, note, amount, createdAt: Date.now() };
    },

    async deleteInvoiceByIdAsync(invoiceId, clientId) {
      await apiDelete(`/invoices/${encodeURIComponent(invoiceId)}`);
      if (clientId) delete invoicesCache[clientId];
      return true;
    },

    async getPaymentsAsync() {
      return apiGet('/payments');
    },

    async getPaymentsByClientAsync(clientId) {
      const payments = await apiGet(`/payments?clientId=${encodeURIComponent(clientId)}`);
      paymentsCache[clientId] = payments;
      return payments;
    },

    getPaymentsByClient(clientId) {
      if (paymentsCache[clientId]) return paymentsCache[clientId];
      apiGet(`/payments?clientId=${encodeURIComponent(clientId)}`)
        .then(p => { paymentsCache[clientId] = p; })
        .catch(() => {});
      return paymentsCache[clientId] || [];
    },

    async addPaymentAsync({ clientId, date, note = "—", amount }) {
      const payment = await apiPost('/payments', { clientId, date, note, amount });
      delete paymentsCache[clientId];
      return payment;
    },

    addPayment({ clientId, date, note = "—", amount }) {
      apiPost('/payments', { clientId, date, note, amount })
        .then(() => { delete paymentsCache[clientId]; })
        .catch(e => console.error('Error adding payment:', e));
      return { id: 'pending', clientId, date, note, amount, createdAt: Date.now() };
    },

    async deletePaymentByIdAsync(paymentId, clientId) {
      await apiDelete(`/payments/${encodeURIComponent(paymentId)}`);
      if (clientId) delete paymentsCache[clientId];
      return true;
    },

    async getExpensesAsync() {
      const expenses = await apiGet('/expenses');
      expensesCache = expenses;
      return expenses;
    },

    getExpenses() {
      if (expensesCache) return expensesCache;
      apiGet('/expenses').then(e => { expensesCache = e; }).catch(() => {});
      return expensesCache || [];
    },

    async addExpenseAsync({ title, category = "", amount, date }) {
      const expense = await apiPost('/expenses', { title, category, amount, date });
      expensesCache = null;
      return expense;
    },

    addExpense({ title, category = "", amount, date }) {
      apiPost('/expenses', { title, category, amount, date })
        .then(() => { expensesCache = null; })
        .catch(e => console.error('Error adding expense:', e));
      return { id: 'pending', title, category, amount, date, createdAt: Date.now() };
    },

    async deleteExpenseByIdAsync(expenseId) {
      await apiDelete(`/expenses/${encodeURIComponent(expenseId)}`);
      expensesCache = null;
      return true;
    },

    async getTrashAsync() {
      return apiGet('/trash');
    },

    getTrash() {
      return [];
    },

    async restoreTrashItemAsync(trashId) {
      await apiPost(`/trash/${trashId}/restore`, {});
      clientsCache = null;
      return true;
    },

    restoreTrashItem(index) {
      return false;
    },

    async deleteTrashItemAsync(trashId) {
      await apiDelete(`/trash/${trashId}`);
      return true;
    },

    deleteTrashItem(index) {
      return false;
    },

    clearCache() {
      clientsCache = null;
      invoicesCache = {};
      paymentsCache = {};
      expensesCache = null;
      notesCache = null;
      statusesCache = null;
    },

    async getNotesAsync() {
      notesCache = await apiGet('/notes');
      return notesCache;
    },

    async addNoteAsync({ title, content = "", category = "", priority = "normal" }) {
      const note = await apiPost('/notes', { title, content, category, priority });
      notesCache = null;
      return note;
    },

    async updateNoteAsync(noteId, data) {
      const note = await apiPut(`/notes/${encodeURIComponent(noteId)}`, data);
      notesCache = null;
      return note;
    },

    async deleteNoteByIdAsync(noteId) {
      await apiDelete(`/notes/${encodeURIComponent(noteId)}`);
      notesCache = null;
      return true;
    },

    async getStatusesAsync() {
      statusesCache = await apiGet('/statuses');
      return statusesCache;
    },

    async addStatusAsync({ title, description = "", statusType = "pending", clientId = "", date = "" }) {
      const status = await apiPost('/statuses', { title, description, statusType, clientId, date });
      statusesCache = null;
      return status;
    },

    async updateStatusAsync(statusId, data) {
      const status = await apiPut(`/statuses/${encodeURIComponent(statusId)}`, data);
      statusesCache = null;
      return status;
    },

    async deleteStatusByIdAsync(statusId) {
      await apiDelete(`/statuses/${encodeURIComponent(statusId)}`);
      statusesCache = null;
      return true;
    },

    async getTransactionsAsync(clientId = null) {
      const url = clientId ? `/transactions?clientId=${encodeURIComponent(clientId)}` : '/transactions';
      transactionsCache = await apiGet(url);
      return transactionsCache;
    },

    async addTransactionAsync({ clientId, date, amount, type, description = "", refType = "manual", refId = "" }) {
      const transaction = await apiPost('/transactions', { clientId, date, amount, type, description, refType, refId });
      transactionsCache = null;
      return transaction;
    },

    async updateTransactionAsync(transactionId, data) {
      const transaction = await apiPut(`/transactions/${encodeURIComponent(transactionId)}`, data);
      transactionsCache = null;
      return transaction;
    },

    async deleteTransactionByIdAsync(transactionId) {
      await apiDelete(`/transactions/${encodeURIComponent(transactionId)}`);
      transactionsCache = null;
      return true;
    },

    async getClientBalanceAsync(clientId) {
      return apiGet(`/clients/${encodeURIComponent(clientId)}/balance`);
    }
  };

  let notesCache = null;
  let statusesCache = null;
  let transactionsCache = null;

  window.GhadeerDB = GhadeerDB;
})();
