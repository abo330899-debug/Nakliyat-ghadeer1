from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), default='')
    company = db.Column(db.String(200), default='')
    old_balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    invoices = db.relationship('Invoice', backref='client', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='client', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.client_id,
            'name': self.name,
            'phone': self.phone or '',
            'company': self.company or '',
            'oldBalance': self.old_balance or 0,
            'createdAt': int(self.created_at.timestamp() * 1000) if self.created_at else None,
            'updatedAt': int(self.updated_at.timestamp() * 1000) if self.updated_at else None
        }


class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.String(50), unique=True, nullable=False)
    client_db_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    date = db.Column(db.String(20), default='')
    note = db.Column(db.Text, default='')
    amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.invoice_id,
            'clientId': self.client.client_id if self.client else '',
            'date': self.date or '',
            'note': self.note or '',
            'amount': self.amount or 0,
            'createdAt': int(self.created_at.timestamp() * 1000) if self.created_at else None,
            'updatedAt': int(self.updated_at.timestamp() * 1000) if self.updated_at else None
        }
    
    def to_dict_full(self):
        drivers_list = [d.to_dict() for d in self.drivers] if self.drivers else []
        payments_list = [p.to_dict() for p in self.payments] if self.payments else []
        total_receipts = sum(d.amount or 0 for d in self.drivers)
        total_payments = sum(p.amount or 0 for p in self.payments)
        return {
            'id': self.invoice_id,
            'clientId': self.client.client_id if self.client else '',
            'date': self.date or '',
            'note': self.note or '',
            'amount': self.amount or 0,
            'drivers': drivers_list,
            'payments': payments_list,
            'totalReceipts': total_receipts,
            'totalPayments': total_payments,
            'balance': total_receipts - total_payments,
            'createdAt': int(self.created_at.timestamp() * 1000) if self.created_at else None,
            'updatedAt': int(self.updated_at.timestamp() * 1000) if self.updated_at else None
        }


class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.String(50), unique=True, nullable=False)
    client_db_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    invoice_db_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True)
    date = db.Column(db.String(20), default='')
    note = db.Column(db.Text, default='')
    amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    invoice = db.relationship('Invoice', backref=db.backref('payments', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.payment_id,
            'clientId': self.client.client_id if self.client else '',
            'invoiceId': self.invoice.invoice_id if self.invoice else '',
            'date': self.date or '',
            'note': self.note or '',
            'amount': self.amount or 0,
            'createdAt': int(self.created_at.timestamp() * 1000) if self.created_at else None,
            'updatedAt': int(self.updated_at.timestamp() * 1000) if self.updated_at else None
        }


class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), default='')
    category = db.Column(db.String(100), default='')
    amount = db.Column(db.Float, default=0.0)
    date = db.Column(db.String(20), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.expense_id,
            'title': self.title or '',
            'category': self.category or '',
            'amount': self.amount or 0,
            'date': self.date or '',
            'createdAt': int(self.created_at.timestamp() * 1000) if self.created_at else None,
            'updatedAt': int(self.updated_at.timestamp() * 1000) if self.updated_at else None
        }


class Trash(db.Model):
    __tablename__ = 'trash'
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'data': self.data,
            'deletedAt': int(self.deleted_at.timestamp() * 1000) if self.deleted_at else None
        }


class Note(db.Model):
    __tablename__ = 'notes'
    
    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), default='')
    content = db.Column(db.Text, default='')
    category = db.Column(db.String(100), default='')
    priority = db.Column(db.String(20), default='normal')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.note_id,
            'title': self.title or '',
            'content': self.content or '',
            'category': self.category or '',
            'priority': self.priority or 'normal',
            'createdAt': int(self.created_at.timestamp() * 1000) if self.created_at else None,
            'updatedAt': int(self.updated_at.timestamp() * 1000) if self.updated_at else None
        }


class Status(db.Model):
    __tablename__ = 'statuses'
    
    id = db.Column(db.Integer, primary_key=True)
    status_id = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), default='')
    description = db.Column(db.Text, default='')
    status_type = db.Column(db.String(50), default='pending')
    client_id = db.Column(db.String(50), default='')
    date = db.Column(db.String(20), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.status_id,
            'title': self.title or '',
            'description': self.description or '',
            'statusType': self.status_type or 'pending',
            'clientId': self.client_id or '',
            'date': self.date or '',
            'createdAt': int(self.created_at.timestamp() * 1000) if self.created_at else None,
            'updatedAt': int(self.updated_at.timestamp() * 1000) if self.updated_at else None
        }


class Driver(db.Model):
    __tablename__ = 'drivers'
    
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.String(50), unique=True, nullable=False)
    client_db_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    invoice_db_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True)
    name = db.Column(db.String(200), default='')
    car = db.Column(db.String(100), default='')
    date = db.Column(db.String(50), default='')
    day = db.Column(db.String(100), default='')
    amount = db.Column(db.Float, default=0.0)
    city = db.Column(db.String(100), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    client = db.relationship('Client', backref=db.backref('drivers', lazy=True, cascade='all, delete-orphan'))
    invoice = db.relationship('Invoice', backref=db.backref('drivers', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.driver_id,
            'clientId': self.client.client_id if self.client else '',
            'invoiceId': self.invoice.invoice_id if self.invoice else '',
            'name': self.name or '',
            'car': self.car or '',
            'date': self.date or '',
            'day': self.day or '',
            'amount': self.amount or 0,
            'city': self.city or '',
            'createdAt': int(self.created_at.timestamp() * 1000) if self.created_at else None,
            'updatedAt': int(self.updated_at.timestamp() * 1000) if self.updated_at else None
        }


class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(50), unique=True, nullable=False)
    client_db_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    date = db.Column(db.String(20), default='')
    amount = db.Column(db.Float, default=0.0)
    type = db.Column(db.String(20), nullable=False)  # debit / credit
    description = db.Column(db.Text, default='')
    ref_type = db.Column(db.String(20), default='manual')  # invoice / manual
    ref_id = db.Column(db.String(50), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    client = db.relationship('Client', backref=db.backref('transactions', lazy=True, cascade='all, delete-orphan'))
    
    def to_dict(self):
        return {
            'id': self.transaction_id,
            'clientId': self.client.client_id if self.client else '',
            'date': self.date or '',
            'amount': self.amount or 0,
            'type': self.type,
            'description': self.description or '',
            'refType': self.ref_type or 'manual',
            'refId': self.ref_id or '',
            'createdAt': int(self.created_at.timestamp() * 1000) if self.created_at else None,
            'updatedAt': int(self.updated_at.timestamp() * 1000) if self.updated_at else None
        }
