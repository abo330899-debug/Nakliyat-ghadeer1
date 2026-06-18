# Al Ghadeer Transport Company Website

## Overview
A comprehensive accounting and invoice management system for شركة الغدير للنقل والتخليص الكمركي (Ghadeer Transportation Company). Features Arabic RTL interface, PostgreSQL database for cross-device synchronization, and professional PDF export.

## Project Structure

### Backend
- `server.py` - Flask API server with REST endpoints
- `models.py` - SQLAlchemy database models

### Frontend Pages
| File | Description |
|------|-------------|
| `index.html` | Login page |
| `home.html` | Dashboard with 8 card layout |
| `client.html` | Client management (add/edit/delete) |
| `client-account.html` | Monthly ledger (Invoice = month container) |
| `client-statement.html` | Detailed statement (4 tabs: Receipts/Payments/Invoices/Summary) |
| `drivers.html` | Driver management per client |
| `payments.html` | Payment (قبوضات) management per client |
| `expenses.html` | Company expenses tracking |
| `notes.html` | Notes and statuses management |
| `general-statement.html` | General statement for all clients |
| `all-operations.html` | All operations search view |

### Assets
- `assets/js/ghadeer-db.js` - Async API client
- `assets/css/theme.css` - Premium dark luxury theme (CSS variables, header, nav, bottom nav, mobile menu)
- `assets/css/mobile.css` - Mobile-first responsive styles (iPhone optimized, bottom sheet modals, safe areas)
- `assets/ghadeer-logo.png` - Company logo

## Theme
All pages use a premium dark luxury theme via `assets/css/theme.css`:
- Deep dark background (`--bg1:#060e1a`, `--bg2:#0c1829`)
- Gold accent (`--accent1:#d4a22c`, `--accent2:#f0c85a`)
- Premium glass effects (`--cardBg:rgba(12,24,41,0.65)`)
- Consistent `header.main-header` class across all pages
- Bottom navigation bar on mobile (5 items: الرئيسية, العملاء, الحساب, المصروفات, الملاحظات)
- iOS safe area support (`env(safe-area-inset-bottom)`)
- Logo path: `assets/ghadeer-logo.png`
- Footer format: plain text, no emojis
- theme.css must be linked BEFORE mobile.css
- All pages (except index.html) include both theme.css and mobile.css

## Mobile Design
- Bottom navigation bar appears on screens ≤768px
- Bottom sheet modals (slide up from bottom)
- 16px font inputs to prevent iOS zoom
- Dashboard: 2-column grid on tablet, 1-column on small phones (≤480px)
- Touch targets minimum 44px
- Safe area padding for notched devices

## Database Tables
| Table | Description |
|-------|-------------|
| `clients` | Client info (name, phone, company, oldBalance) |
| `invoices` | Monthly containers (amount, date, note) - groups drivers/payments per month |
| `payments` | Client payments (date, note, amount, invoice_db_id) |
| `drivers` | Driver records (name, car, date, day, amount, city) |
| `expenses` | Company expenses (title, amount, category, date) |
| `notes` | Administrative notes |
| `statuses` | Status tracking |
| `transactions` | Financial transactions |
| `trash` | Soft-deleted items |

## Monthly Accounting Model
- Invoice = monthly settlement container (Invoice.note = month name, e.g. "شهر 1 - 2026")
- Each month groups: سواق (drivers/receipts) + قبوضات (payments)
- Running balance: الرصيد السابق + مجموع الوصولات - مجموع القبوضات
- Invoices sorted by date (chronological), then by ID
- HTML escaping (esc() function) applied to all user content to prevent XSS

## API Endpoints
- `GET/POST /api/clients` - Client operations
- `GET/PUT/DELETE /api/clients/:id` - Individual client
- `GET/POST /api/invoices` - Invoice operations (supports `?full=true` for nested drivers/payments)
- `GET/POST /api/payments` - Payment operations
- `GET/POST /api/drivers` - Driver operations
- `GET/POST /api/expenses` - Expense operations
- `GET/POST /api/notes` - Note operations
- `GET/POST /api/statuses` - Status operations
- `GET/POST /api/transactions` - Transaction operations

## Navigation Flow
```
home.html
  ├── client.html (العملاء)
  │     ├── 💰 قبوضات → payments.html
  │     ├── 🚚 السواق → drivers.html
  │     └── 📊 كشف تفصيلي → client-statement.html
  ├── client-statement.html (الوصولات)
  ├── client-account.html (كشف الحساب الشهري)
  ├── expenses.html (المصروفات)
  ├── notes.html (الملاحظات والحالات)
  ├── general-statement.html (كشف الحساب العام)
  └── all-operations.html (جميع العمليات)
```

## Security
- Static file serving restricted to allowed extensions (.html, .css, .js, images, fonts) and the `assets/` directory
- Source code files (.py, .toml, .lock, .db) are not served to clients
- Path traversal attacks blocked via normalization
- Login form uses proper `<form>` tag with autocomplete attributes

## Running the Project
```bash
python server.py
```
Server runs on port 5000.

## Login
Username: `star`, Password: `star`
