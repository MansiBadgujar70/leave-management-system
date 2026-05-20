"""
models.py - Database Models
============================
Defines the SQLAlchemy ORM models (Python classes → MySQL tables).
Each class represents one database table.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Create the SQLAlchemy db object (will be linked to the Flask app in app.py)
db = SQLAlchemy()


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 1 : users
# Stores login credentials and role (admin / employee)
# ─────────────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    """
    Represents a system user (admin or employee).
    UserMixin provides default implementations required by Flask-Login.
    """
    __tablename__ = 'users'

    user_id    = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role       = db.Column(db.Enum('admin', 'employee'), nullable=False, default='employee')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One-to-one relationship: one user → one employee profile
    employee   = db.relationship('Employee', backref='user', uselist=False, cascade='all, delete-orphan')

    # Flask-Login needs get_id() to return a string
    def get_id(self):
        return str(self.user_id)

    # ─── Password helpers ────────────────────────────────────────────────────
    def set_password(self, password):
        """Hash and store the password securely."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Return True if the given password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 2 : employees
# Stores employee-specific details; linked to users via user_id FK
# ─────────────────────────────────────────────────────────────────────────────
class Employee(db.Model):
    """
    Stores extended information about an employee.
    Each employee record belongs to exactly one user account.
    """
    __tablename__ = 'employees'

    employee_id     = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), unique=True, nullable=False)
    full_name       = db.Column(db.String(150), nullable=False)
    department      = db.Column(db.String(100), nullable=False)
    phone_number    = db.Column(db.String(20),  nullable=True)
    joining_date    = db.Column(db.Date,        nullable=False, default=datetime.utcnow)
    total_leaves    = db.Column(db.Integer,     nullable=False, default=20)
    remaining_leaves = db.Column(db.Integer,   nullable=False, default=20)

    # One-to-many: one employee → many leave requests
    leave_requests  = db.relationship('LeaveRequest', backref='employee',
                                       lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Employee {self.full_name} | Dept: {self.department}>'


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 3 : leave_requests
# Stores every leave application submitted by employees
# ─────────────────────────────────────────────────────────────────────────────
class LeaveRequest(db.Model):
    """
    Represents a single leave application.
    Status lifecycle: Pending → Approved / Rejected
    """
    __tablename__ = 'leave_requests'

    leave_id      = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id   = db.Column(db.Integer, db.ForeignKey('employees.employee_id', ondelete='CASCADE'), nullable=False)
    leave_type    = db.Column(db.Enum('Sick Leave', 'Casual Leave', 'Emergency Leave', 'Vacation Leave'),
                              nullable=False)
    start_date    = db.Column(db.Date,    nullable=False)
    end_date      = db.Column(db.Date,    nullable=False)
    total_days    = db.Column(db.Integer, nullable=False)
    reason        = db.Column(db.Text,    nullable=False)
    status        = db.Column(db.Enum('Pending', 'Approved', 'Rejected'),
                              nullable=False, default='Pending')
    admin_remarks = db.Column(db.Text,    nullable=True)
    applied_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<LeaveRequest #{self.leave_id} | {self.leave_type} | {self.status}>'
