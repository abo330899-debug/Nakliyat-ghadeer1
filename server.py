import os
import io
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from models import db, Client, Invoice, Payment, Expense, Trash, Note, Status, Transaction, Driver
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
import arabic_reshaper
from bidi.algorithm import get_display

app = Flask(__name__, static_folder=None)
CORS(app)

# ---------- IMPORTANT: DB CONFIG (FIXED) ----------
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "ghadeer-secret-key-2026"

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    # Local persistent sqlite file inside the project
    db_url = "sqlite:///app.db"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

print("DB URL =", db_url)
# -----------------------------------------------

db.init_app(app)

with app.app_context():
    db.create_all()
    
    try:
        from sqlalchemy import text, inspect
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('payments')]
        if 'invoice_db_id' not in columns:
            db.session.execute(text('ALTER TABLE payments ADD COLUMN invoice_db_id INTEGER REFERENCES invoices(id)'))
            db.session.commit()
            print("Added invoice_db_id column to payments table")
    except Exception as e:
        db.session.rollback()
        print(f"Migration check error: {e}")


def get_next_id(prefix, model, id_field):
    from sqlalchemy import func, text
    col = getattr(model, id_field)
    max_id = db.session.query(func.max(col)).filter(col.like(f'{prefix}-%')).with_for_update().scalar()
    if max_id:
        try:
            num = int(max_id.split('-')[1])
            return f"{prefix}-{str(num + 1).zfill(3)}"
        except (ValueError, IndexError):
            pass
    return f"{prefix}-001"


@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')


ALLOWED_STATIC_EXTENSIONS = {'.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.webp'}
ALLOWED_STATIC_DIRS = {'assets'}

@app.route('/<path:path>')
def serve_static(path):
    normalized = os.path.normpath(path)
    if normalized.startswith('..') or normalized.startswith('/'):
        return send_from_directory('.', 'index.html')
    ext = os.path.splitext(normalized)[1].lower()
    parts = normalized.replace('\\', '/').split('/')
    is_allowed_dir = parts[0] in ALLOWED_STATIC_DIRS if len(parts) > 1 else False
    is_allowed_root_file = len(parts) == 1 and ext in ALLOWED_STATIC_EXTENSIONS
    if (is_allowed_dir or is_allowed_root_file) and os.path.isfile(normalized):
        directory = os.path.dirname(normalized) or '.'
        filename = os.path.basename(normalized)
        return send_from_directory(directory, filename)
    return send_from_directory('.', 'index.html')


@app.route('/api/clients', methods=['GET'])
def get_clients():
    clients = Client.query.all()
    return jsonify([c.to_dict() for c in clients])


@app.route('/api/clients', methods=['POST'])
def add_client():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'اسم العميل مطلوب'}), 400

    client_id = get_next_id('CLIENT', Client, 'client_id')
    old_balance = 0
    try:
        old_balance = float(data.get('oldBalance') or 0)
    except:
        old_balance = 0
    
    client = Client(
        client_id=client_id,
        name=name,
        phone=(data.get('phone') or '').strip(),
        company=(data.get('company') or '').strip(),
        old_balance=old_balance
    )
    db.session.add(client)
    db.session.commit()
    return jsonify(client.to_dict()), 201


@app.route('/api/clients/<client_id>', methods=['PUT'])
def update_client(client_id):
    client = Client.query.filter_by(client_id=client_id).first()
    if not client:
        return jsonify({'error': 'العميل غير موجود'}), 404

    data = request.get_json()
    if 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': 'اسم العميل مطلوب'}), 400
        client.name = name
    if 'phone' in data:
        client.phone = (data.get('phone') or '').strip()
    if 'company' in data:
        client.company = (data.get('company') or '').strip()
    if 'oldBalance' in data:
        try:
            client.old_balance = float(data.get('oldBalance') or 0)
        except:
            pass

    db.session.commit()
    return jsonify(client.to_dict())


@app.route('/api/clients/<client_id>', methods=['DELETE'])
def delete_client(client_id):
    client = Client.query.filter_by(client_id=client_id).first()
    if not client:
        return jsonify({'error': 'العميل غير موجود'}), 404

    trash = Trash(type='client', data=client.to_dict())
    db.session.add(trash)
    db.session.delete(client)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/invoices', methods=['GET'])
def get_invoices():
    client_id = request.args.get('clientId')
    full = request.args.get('full', 'false').lower() == 'true'
    if client_id:
        client = Client.query.filter_by(client_id=client_id).first()
        if client:
            invoices = Invoice.query.filter_by(client_db_id=client.id).order_by(Invoice.date.asc(), Invoice.id.asc()).all()
        else:
            invoices = []
    else:
        invoices = Invoice.query.order_by(Invoice.date.asc(), Invoice.id.asc()).all()
    if full:
        return jsonify([i.to_dict_full() for i in invoices])
    return jsonify([i.to_dict() for i in invoices])


@app.route('/api/invoices', methods=['POST'])
def add_invoice():
    data = request.get_json()
    client_id = (data.get('clientId') or '').strip()

    client = Client.query.filter_by(client_id=client_id).first()
    if not client:
        return jsonify({'error': 'العميل غير موجود'}), 404

    invoice_id = get_next_id('INV', Invoice, 'invoice_id')
    invoice = Invoice(
        invoice_id=invoice_id,
        client_db_id=client.id,
        date=(data.get('date') or '').strip(),
        note=(data.get('note') or '').strip() or '—',
        amount=float(data.get('amount') or 0)
    )
    db.session.add(invoice)
    db.session.commit()
    return jsonify(invoice.to_dict()), 201


@app.route('/api/invoices/<invoice_id>', methods=['DELETE'])
def delete_invoice(invoice_id):
    invoice = Invoice.query.filter_by(invoice_id=invoice_id).first()
    if not invoice:
        return jsonify({'error': 'الوصل غير موجود'}), 404

    trash = Trash(type='invoice', data=invoice.to_dict_full())
    db.session.add(trash)
    
    for driver in invoice.drivers:
        driver.invoice_db_id = None
    for payment in invoice.payments:
        payment.invoice_db_id = None
    
    db.session.delete(invoice)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/payments', methods=['GET'])
def get_payments():
    client_id = request.args.get('client') or request.args.get('clientId')
    if client_id:
        client = Client.query.filter_by(client_id=client_id).first()
        if client:
            payments = Payment.query.filter_by(client_db_id=client.id).all()
        else:
            payments = []
    else:
        payments = Payment.query.all()
    return jsonify([p.to_dict() for p in payments])


@app.route('/api/payments', methods=['POST'])
def add_payment():
    data = request.get_json()
    client_id = (data.get('clientId') or '').strip()
    invoice_id = (data.get('invoiceId') or '').strip()

    client = Client.query.filter_by(client_id=client_id).first()
    if not client:
        return jsonify({'error': 'العميل غير موجود'}), 404

    invoice = None
    if invoice_id:
        invoice = Invoice.query.filter_by(invoice_id=invoice_id).first()
        if invoice and invoice.client_db_id != client.id:
            return jsonify({'error': 'الفاتورة لا تنتمي لهذا العميل'}), 400

    payment_id = get_next_id('PAY', Payment, 'payment_id')
    payment = Payment(
        payment_id=payment_id,
        client_db_id=client.id,
        invoice_db_id=invoice.id if invoice else None,
        date=(data.get('date') or '').strip(),
        note=(data.get('note') or '').strip() or '—',
        amount=float(data.get('amount') or 0)
    )
    db.session.add(payment)
    db.session.commit()
    return jsonify(payment.to_dict()), 201


@app.route('/api/payments/<payment_id>', methods=['DELETE'])
def delete_payment(payment_id):
    payment = Payment.query.filter_by(payment_id=payment_id).first()
    if not payment:
        return jsonify({'error': 'القبض غير موجود'}), 404

    trash = Trash(type='payment', data=payment.to_dict())
    db.session.add(trash)
    db.session.delete(payment)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/drivers', methods=['GET'])
def get_drivers():
    client_id = request.args.get('client')
    invoice_id = request.args.get('invoice')
    
    query = Driver.query
    if client_id:
        client = Client.query.filter_by(client_id=client_id).first()
        if client:
            query = query.filter_by(client_db_id=client.id)
    if invoice_id:
        invoice = Invoice.query.filter_by(invoice_id=invoice_id).first()
        if invoice:
            query = query.filter_by(invoice_db_id=invoice.id)
    
    drivers = query.order_by(Driver.id).all()
    return jsonify([d.to_dict() for d in drivers])


@app.route('/api/drivers', methods=['POST'])
def add_driver():
    data = request.get_json()
    client_id = (data.get('clientId') or '').strip()
    invoice_id = (data.get('invoiceId') or '').strip()
    
    client = Client.query.filter_by(client_id=client_id).first()
    if not client:
        return jsonify({'error': 'العميل غير موجود'}), 404
    
    invoice = None
    if invoice_id:
        invoice = Invoice.query.filter_by(invoice_id=invoice_id).first()
        if invoice and invoice.client_db_id != client.id:
            return jsonify({'error': 'الفاتورة لا تنتمي لهذا العميل'}), 400
    
    driver_id = get_next_id('DRV', Driver, 'driver_id')
    driver = Driver(
        driver_id=driver_id,
        client_db_id=client.id,
        invoice_db_id=invoice.id if invoice else None,
        name=(data.get('name') or '').strip(),
        car=(data.get('car') or '').strip(),
        date=(data.get('date') or '').strip(),
        day=(data.get('day') or '').strip(),
        amount=float(data.get('amount') or 0),
        city=(data.get('city') or '').strip()
    )
    db.session.add(driver)
    db.session.commit()
    return jsonify(driver.to_dict()), 201


@app.route('/api/drivers/<driver_id>', methods=['PUT'])
def update_driver(driver_id):
    driver = Driver.query.filter_by(driver_id=driver_id).first()
    if not driver:
        return jsonify({'error': 'السائق غير موجود'}), 404
    
    data = request.get_json()
    if 'name' in data:
        driver.name = (data.get('name') or '').strip()
    if 'car' in data:
        driver.car = (data.get('car') or '').strip()
    if 'date' in data:
        driver.date = (data.get('date') or '').strip()
    if 'day' in data:
        driver.day = (data.get('day') or '').strip()
    if 'amount' in data:
        driver.amount = float(data.get('amount') or 0)
    if 'city' in data:
        driver.city = (data.get('city') or '').strip()
    
    db.session.commit()
    return jsonify(driver.to_dict())


@app.route('/api/drivers/<driver_id>', methods=['DELETE'])
def delete_driver(driver_id):
    driver = Driver.query.filter_by(driver_id=driver_id).first()
    if not driver:
        return jsonify({'error': 'السائق غير موجود'}), 404
    
    trash = Trash(type='driver', data=driver.to_dict())
    db.session.add(trash)
    db.session.delete(driver)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    expenses = Expense.query.all()
    return jsonify([e.to_dict() for e in expenses])


@app.route('/api/expenses', methods=['POST'])
def add_expense():
    data = request.get_json()

    expense_id = get_next_id('EXP', Expense, 'expense_id')
    expense = Expense(
        expense_id=expense_id,
        title=(data.get('title') or '').strip() or '—',
        category=(data.get('category') or '').strip(),
        amount=float(data.get('amount') or 0),
        date=(data.get('date') or '').strip()
    )
    db.session.add(expense)
    db.session.commit()
    return jsonify(expense.to_dict()), 201


@app.route('/api/expenses/<expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    expense = Expense.query.filter_by(expense_id=expense_id).first()
    if not expense:
        return jsonify({'error': 'المصروف غير موجود'}), 404

    trash = Trash(type='expense', data=expense.to_dict())
    db.session.add(trash)
    db.session.delete(expense)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/trash', methods=['GET'])
def get_trash():
    trash = Trash.query.order_by(Trash.deleted_at.desc()).all()
    return jsonify([t.to_dict() for t in trash])


@app.route('/api/trash/<int:trash_id>/restore', methods=['POST'])
def restore_trash(trash_id):
    trash_item = Trash.query.get(trash_id)
    if not trash_item:
        return jsonify({'error': 'العنصر غير موجود'}), 404

    data = trash_item.data or {}

    if trash_item.type == 'client':
        cid = (data.get('client_id') or data.get('id') or '').strip()
        if cid:
            existing = Client.query.filter_by(client_id=cid).first()
            if not existing:
                client = Client(
                    client_id=cid,
                    name=data.get('name', ''),
                    phone=data.get('phone', ''),
                    company=data.get('company', ''),
                    old_balance=data.get('oldBalance', 0)
                )
                db.session.add(client)

    elif trash_item.type == 'invoice':
        inv_id = data.get('id', '').strip()
        client_id_str = data.get('clientId', '').strip()
        if inv_id and client_id_str:
            client = Client.query.filter_by(client_id=client_id_str).first()
            if client and not Invoice.query.filter_by(invoice_id=inv_id).first():
                invoice = Invoice(
                    invoice_id=inv_id,
                    client_db_id=client.id,
                    date=data.get('date', ''),
                    note=data.get('note', ''),
                    amount=data.get('amount', 0)
                )
                db.session.add(invoice)

    elif trash_item.type == 'payment':
        pay_id = data.get('id', '').strip()
        client_id_str = data.get('clientId', '').strip()
        if pay_id and client_id_str:
            client = Client.query.filter_by(client_id=client_id_str).first()
            if client and not Payment.query.filter_by(payment_id=pay_id).first():
                payment = Payment(
                    payment_id=pay_id,
                    client_db_id=client.id,
                    date=data.get('date', ''),
                    note=data.get('note', ''),
                    amount=data.get('amount', 0)
                )
                db.session.add(payment)

    elif trash_item.type == 'driver':
        drv_id = data.get('id', '').strip()
        client_id_str = data.get('clientId', '').strip()
        if drv_id and client_id_str:
            client = Client.query.filter_by(client_id=client_id_str).first()
            if client and not Driver.query.filter_by(driver_id=drv_id).first():
                driver = Driver(
                    driver_id=drv_id,
                    client_db_id=client.id,
                    name=data.get('name', ''),
                    car=data.get('car', ''),
                    date=data.get('date', ''),
                    day=data.get('day', ''),
                    amount=data.get('amount', 0),
                    city=data.get('city', '')
                )
                db.session.add(driver)

    elif trash_item.type == 'expense':
        exp_id = data.get('id', '').strip()
        if exp_id and not Expense.query.filter_by(expense_id=exp_id).first():
            expense = Expense(
                expense_id=exp_id,
                title=data.get('title', ''),
                category=data.get('category', ''),
                amount=data.get('amount', 0),
                date=data.get('date', '')
            )
            db.session.add(expense)

    elif trash_item.type == 'note':
        note_id = data.get('id', '').strip()
        if note_id and not Note.query.filter_by(note_id=note_id).first():
            note = Note(
                note_id=note_id,
                title=data.get('title', ''),
                content=data.get('content', ''),
                category=data.get('category', ''),
                priority=data.get('priority', 'normal')
            )
            db.session.add(note)

    elif trash_item.type == 'status':
        status_id = data.get('id', '').strip()
        if status_id and not Status.query.filter_by(status_id=status_id).first():
            status = Status(
                status_id=status_id,
                title=data.get('title', ''),
                description=data.get('description', ''),
                status_type=data.get('statusType', 'pending'),
                client_id=data.get('clientId', ''),
                date=data.get('date', '')
            )
            db.session.add(status)

    db.session.delete(trash_item)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/trash/<int:trash_id>', methods=['DELETE'])
def delete_trash(trash_id):
    trash_item = Trash.query.get(trash_id)
    if not trash_item:
        return jsonify({'error': 'العنصر غير موجود'}), 404

    db.session.delete(trash_item)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/notes', methods=['GET'])
def get_notes():
    notes = Note.query.order_by(Note.created_at.desc()).all()
    return jsonify([n.to_dict() for n in notes])


@app.route('/api/notes', methods=['POST'])
def add_note():
    data = request.get_json()

    note_id = get_next_id('NOTE', Note, 'note_id')
    note = Note(
        note_id=note_id,
        title=(data.get('title') or '').strip() or '—',
        content=(data.get('content') or '').strip(),
        category=(data.get('category') or '').strip(),
        priority=(data.get('priority') or 'normal').strip()
    )
    db.session.add(note)
    db.session.commit()
    return jsonify(note.to_dict()), 201


@app.route('/api/notes/<note_id>', methods=['PUT'])
def update_note(note_id):
    note = Note.query.filter_by(note_id=note_id).first()
    if not note:
        return jsonify({'error': 'الملاحظة غير موجودة'}), 404

    data = request.get_json()
    if 'title' in data:
        note.title = (data.get('title') or '').strip() or '—'
    if 'content' in data:
        note.content = (data.get('content') or '').strip()
    if 'category' in data:
        note.category = (data.get('category') or '').strip()
    if 'priority' in data:
        note.priority = (data.get('priority') or 'normal').strip()

    db.session.commit()
    return jsonify(note.to_dict())


@app.route('/api/notes/<note_id>', methods=['DELETE'])
def delete_note(note_id):
    note = Note.query.filter_by(note_id=note_id).first()
    if not note:
        return jsonify({'error': 'الملاحظة غير موجودة'}), 404

    trash = Trash(type='note', data=note.to_dict())
    db.session.add(trash)
    db.session.delete(note)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/statuses', methods=['GET'])
def get_statuses():
    statuses = Status.query.order_by(Status.created_at.desc()).all()
    return jsonify([s.to_dict() for s in statuses])


@app.route('/api/statuses', methods=['POST'])
def add_status():
    data = request.get_json()

    status_id = get_next_id('STATUS', Status, 'status_id')
    status = Status(
        status_id=status_id,
        title=(data.get('title') or '').strip() or '—',
        description=(data.get('description') or '').strip(),
        status_type=(data.get('statusType') or 'pending').strip(),
        client_id=(data.get('clientId') or '').strip(),
        date=(data.get('date') or '').strip()
    )
    db.session.add(status)
    db.session.commit()
    return jsonify(status.to_dict()), 201


@app.route('/api/statuses/<status_id>', methods=['PUT'])
def update_status(status_id):
    status = Status.query.filter_by(status_id=status_id).first()
    if not status:
        return jsonify({'error': 'الحالة غير موجودة'}), 404

    data = request.get_json()
    if 'title' in data:
        status.title = (data.get('title') or '').strip() or '—'
    if 'description' in data:
        status.description = (data.get('description') or '').strip()
    if 'statusType' in data:
        status.status_type = (data.get('statusType') or 'pending').strip()
    if 'clientId' in data:
        status.client_id = (data.get('clientId') or '').strip()
    if 'date' in data:
        status.date = (data.get('date') or '').strip()

    db.session.commit()
    return jsonify(status.to_dict())


@app.route('/api/statuses/<status_id>', methods=['DELETE'])
def delete_status(status_id):
    status = Status.query.filter_by(status_id=status_id).first()
    if not status:
        return jsonify({'error': 'الحالة غير موجودة'}), 404

    trash = Trash(type='status', data=status.to_dict())
    db.session.add(trash)
    db.session.delete(status)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    client_id = request.args.get('clientId')
    if client_id:
        client = Client.query.filter_by(client_id=client_id).first()
        if client:
            transactions = Transaction.query.filter_by(client_db_id=client.id).order_by(Transaction.date.desc()).all()
        else:
            transactions = []
    else:
        transactions = Transaction.query.order_by(Transaction.date.desc()).all()
    return jsonify([t.to_dict() for t in transactions])


@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    data = request.get_json()

    client_id = data.get('clientId')
    client = Client.query.filter_by(client_id=client_id).first()
    if not client:
        return jsonify({'error': 'العميل غير موجود'}), 404

    transaction_id = get_next_id('TXN', Transaction, 'transaction_id')
    transaction = Transaction(
        transaction_id=transaction_id,
        client_db_id=client.id,
        date=(data.get('date') or '').strip(),
        amount=float(data.get('amount') or 0),
        type=(data.get('type') or 'debit').strip(),
        description=(data.get('description') or '').strip(),
        ref_type=(data.get('refType') or 'manual').strip(),
        ref_id=(data.get('refId') or '').strip()
    )
    db.session.add(transaction)
    db.session.commit()
    return jsonify(transaction.to_dict()), 201


@app.route('/api/transactions/<transaction_id>', methods=['PUT'])
def update_transaction(transaction_id):
    transaction = Transaction.query.filter_by(transaction_id=transaction_id).first()
    if not transaction:
        return jsonify({'error': 'المعاملة غير موجودة'}), 404

    data = request.get_json()
    if 'date' in data:
        transaction.date = (data.get('date') or '').strip()
    if 'amount' in data:
        transaction.amount = float(data.get('amount') or 0)
    if 'type' in data:
        transaction.type = (data.get('type') or 'debit').strip()
    if 'description' in data:
        transaction.description = (data.get('description') or '').strip()
    if 'refType' in data:
        transaction.ref_type = (data.get('refType') or 'manual').strip()
    if 'refId' in data:
        transaction.ref_id = (data.get('refId') or '').strip()

    db.session.commit()
    return jsonify(transaction.to_dict())


@app.route('/api/transactions/<transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    transaction = Transaction.query.filter_by(transaction_id=transaction_id).first()
    if not transaction:
        return jsonify({'error': 'المعاملة غير موجودة'}), 404

    trash = Trash(type='transaction', data=transaction.to_dict())
    db.session.add(trash)
    db.session.delete(transaction)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/clients/<client_id>/balance', methods=['GET'])
def get_client_balance(client_id):
    client = Client.query.filter_by(client_id=client_id).first()
    if not client:
        return jsonify({'error': 'العميل غير موجود'}), 404

    transactions = Transaction.query.filter_by(client_db_id=client.id).all()
    total_debit = sum(t.amount for t in transactions if t.type == 'debit')
    total_credit = sum(t.amount for t in transactions if t.type == 'credit')
    balance = total_debit - total_credit

    return jsonify({
        'clientId': client_id,
        'totalDebit': total_debit,
        'totalCredit': total_credit,
        'balance': balance
    })


def arabic_text(text):
    if not text:
        return ''
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)

pdfmetrics.registerFont(TTFont('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))


@app.route('/api/client-pdf/<client_id>', methods=['POST'])
def generate_client_pdf(client_id):
    try:
        from datetime import datetime
        from reportlab.lib.units import mm
        from reportlab.graphics.shapes import Drawing, Rect, Line
        
        data = request.get_json() or {}
        client_name = data.get('clientName', 'عميل')
        client_phone = data.get('clientPhone', '')
        receipts = data.get('receipts', [])
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
        
        dark_blue = colors.HexColor('#0d1b2a')
        gold = colors.HexColor('#c9a227')
        light_gold = colors.HexColor('#f4e4ba')
        
        elements = []
        
        logo_data = [
            ['', arabic_text('شركة الغدير'), ''],
            ['', arabic_text('للنقل والتخليص المكرمي'), ''],
        ]
        logo_table = Table(logo_data, colWidths=[180, 180, 180])
        logo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
            ('FONTNAME', (0, 1), (-1, 1), 'DejaVuSans'),
            ('FONTSIZE', (0, 0), (-1, 0), 26),
            ('FONTSIZE', (0, 1), (-1, 1), 14),
            ('TEXTCOLOR', (0, 0), (-1, 0), dark_blue),
            ('TEXTCOLOR', (0, 1), (-1, 1), gold),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(logo_table)
        
        line_data = [['']]
        line_table = Table(line_data, colWidths=[540])
        line_table.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 3, gold),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(line_table)
        
        title_data = [[arabic_text('كشف حساب')]]
        title_table = Table(title_data, colWidths=[540])
        title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), dark_blue),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 18),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 15))
        
        info_data = [
            [arabic_text(datetime.now().strftime('%Y-%m-%d')), arabic_text('التاريخ'), arabic_text(client_phone or '-'), arabic_text('الهاتف')],
            ['', '', arabic_text(client_name), arabic_text('اسم العميل')],
        ]
        info_table = Table(info_data, colWidths=[130, 80, 200, 100])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, -1), light_gold),
            ('BACKGROUND', (3, 0), (3, -1), light_gold),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (1, 0), (1, -1), 'DejaVuSans-Bold'),
            ('FONTNAME', (3, 0), (3, -1), 'DejaVuSans-Bold'),
            ('FONTNAME', (0, 0), (0, -1), 'DejaVuSans'),
            ('FONTNAME', (2, 0), (2, -1), 'DejaVuSans'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (-1, -1), 1.5, dark_blue),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 20))
        
        total_drivers = 0
        total_payments = 0
        old_balance = 0
        
        for receipt in receipts:
            receipt_name = receipt.get('name', 'وصل')
            receipt_date = receipt.get('date', '')
            drivers = receipt.get('drivers', [])
            payments = receipt.get('payments', [])
            prev_balance = receipt.get('previousBalance', 0)
            
            if prev_balance > 0:
                old_balance = prev_balance
            
            receipt_header = [[arabic_text(receipt_date), arabic_text(receipt_name)]]
            receipt_table = Table(receipt_header, colWidths=[150, 390])
            receipt_table.setStyle(TableStyle([
                ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#1a5f2a')),
                ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#2e8540')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(receipt_table)
            
            if drivers:
                driver_data = [[arabic_text('المبلغ'), arabic_text('المحافظة'), arabic_text('السيارة'), arabic_text('السائق'), arabic_text('التاريخ'), arabic_text('#')]]
                for i, d in enumerate(drivers, 1):
                    driver_data.append([
                        f"${d.get('amount', 0):,.2f}",
                        arabic_text(d.get('city', '')),
                        d.get('car', ''),
                        arabic_text(d.get('name', '')),
                        d.get('date', ''),
                        str(i)
                    ])
                    total_drivers += d.get('amount', 0)
                
                driver_table = Table(driver_data, colWidths=[90, 80, 80, 130, 90, 40])
                driver_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5f2a')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'DejaVuSans'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#1a5f2a')),
                    ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#1a5f2a')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#e8f5e9')]),
                ]))
                elements.append(driver_table)
            
            if payments:
                elements.append(Spacer(1, 10))
                payment_header = [[arabic_text('القبوضات')]]
                payment_header_table = Table(payment_header, colWidths=[540])
                payment_header_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#8b0000')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 11),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ]))
                elements.append(payment_header_table)
                
                payment_data = [[arabic_text('المبلغ'), arabic_text('الوصف'), arabic_text('التاريخ'), arabic_text('#')]]
                for i, p in enumerate(payments, 1):
                    payment_data.append([
                        f"${p.get('amount', 0):,.2f}",
                        arabic_text(p.get('description', '')),
                        p.get('date', ''),
                        str(i)
                    ])
                    total_payments += p.get('amount', 0)
                
                payment_table = Table(payment_data, colWidths=[100, 280, 100, 40])
                payment_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#b71c1c')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'DejaVuSans'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#8b0000')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ffebee')]),
                ]))
                elements.append(payment_table)
            
            elements.append(Spacer(1, 20))
        
        total_receipts = old_balance + total_drivers
        final_balance = total_receipts - total_payments
        
        summary_title = [[arabic_text('ملخص الحساب النهائي')]]
        summary_title_table = Table(summary_title, colWidths=[540])
        summary_title_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), gold),
            ('TEXTCOLOR', (0, 0), (-1, -1), dark_blue),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(summary_title_table)
        
        summary_data = [
            [f"${old_balance:,.2f}", arabic_text('الحساب القديم')],
            [f"${total_drivers:,.2f}", arabic_text('مجموع السواق (+)')],
            [f"${total_receipts:,.2f}", arabic_text('مجموع الوصولات (=)')],
            [f"${total_payments:,.2f}", arabic_text('القبوضات (-)')],
        ]
        
        summary_table = Table(summary_data, colWidths=[200, 340])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 1, dark_blue),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor('#cccccc')),
            ('LINEBELOW', (0, 1), (-1, 1), 0.5, colors.HexColor('#cccccc')),
            ('LINEBELOW', (0, 2), (-1, 2), 0.5, colors.HexColor('#cccccc')),
            ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#f5f5f5')),
        ]))
        elements.append(summary_table)
        
        final_data = [[f"${final_balance:,.2f}", arabic_text('الرصيد النهائي')]]
        final_table = Table(final_data, colWidths=[200, 340])
        final_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), dark_blue),
            ('TEXTCOLOR', (0, 0), (-1, -1), gold),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 16),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(final_table)
        
        elements.append(Spacer(1, 30))
        footer_data = [[arabic_text('شكراً لتعاملكم معنا')]]
        footer_table = Table(footer_data, colWidths=[540])
        footer_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (-1, -1), gold),
        ]))
        elements.append(footer_table)
        
        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'statement_{client_id}.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)