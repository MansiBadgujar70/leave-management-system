"""
models.py - Database Models
============================
Defines the SQLAlchemy ORM models (Python classes → MySQL tables).
Each class represents one database table.
"""

from datetime import datetime, timezone, timedelta, date, time

def get_ist_now():
    """Return the current datetime in Indian Standard Time (IST)."""
    utc_now = datetime.now(timezone.utc)
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    return utc_now.astimezone(ist_tz)

def get_ist_today():
    """Return the current date in Indian Standard Time (IST)."""
    return get_ist_now().date()

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer as Serializer



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
    role = db.Column(
    db.Enum('admin', 'employee', name='role_enum'),
    nullable=False,
    default='employee'
)
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

    # ─── Password reset token helpers ────────────────────────────────────────
    def get_reset_token(self):
        """Generate a secure, signed timed token for password resets."""
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.user_id}, salt='password-reset-salt')

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        """Verify the password reset token and return the user if valid."""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, salt='password-reset-salt', max_age=expires_sec)
        except Exception:
            return None
        return User.query.get(data.get('user_id'))

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

    # One-to-many: one employee → many attendance records
    attendances     = db.relationship('Attendance', backref='employee',
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

    leave_id    = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id', ondelete='CASCADE'), nullable=False)

    leave_type = db.Column(
        db.Enum(
            'Sick Leave',
            'Casual Leave',
            'Emergency Leave',
            'Vacation Leave',
            name='leave_type_enum'
        ),
        nullable=False
    )

    start_date = db.Column(db.Date, nullable=False)
    end_date   = db.Column(db.Date, nullable=False)
    total_days = db.Column(db.Integer, nullable=False)
    reason     = db.Column(db.Text, nullable=False)

    status = db.Column(
        db.Enum('Pending', 'Approved', 'Rejected', name='status_enum'),
        nullable=False,
        default='Pending'
    )

    admin_remarks = db.Column(db.Text, nullable=True)
    applied_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<LeaveRequest #{self.leave_id} | {self.leave_type} | {self.status}>'


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 4 : attendance
# Tracks daily check-in / check-out for each employee
# Business Rules:
#   - Office hours: 9:00 AM → 5:00 PM (standard 8-hour day)
#   - On Time  : check-in at or before 09:00
#   - Late     : check-in after 09:00 (late_minutes > 0)
#   - Half Day : total work_hours < 4.0
#   - Absent   : no record / admin-marked
# ─────────────────────────────────────────────────────────────────────────────
class Attendance(db.Model):
    """Represents a single day's attendance record for an employee."""
    __tablename__ = 'attendance'

    attendance_id  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id    = db.Column(db.Integer, db.ForeignKey('employees.employee_id', ondelete='CASCADE'), nullable=False)
    date           = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    check_in_time  = db.Column(db.Time, nullable=True)   # e.g. 09:03:00
    check_out_time = db.Column(db.Time, nullable=True)   # e.g. 17:22:00
    work_hours     = db.Column(db.Float, nullable=True)  # e.g. 8.32 hours

    # Status: On Time / Late / Absent / Half Day
    status = db.Column(
        db.Enum('On Time', 'Late', 'Absent', 'Half Day', name='attendance_status_enum'),
        nullable=False,
        default='Absent'
    )

    late_minutes   = db.Column(db.Integer, nullable=False, default=0)  # Minutes late past 9 AM
    notes          = db.Column(db.String(255), nullable=True)          # Admin notes / edits

    # Unique constraint: one record per employee per day
    __table_args__ = (db.UniqueConstraint('employee_id', 'date', name='uq_employee_date'),)

    def calculate_work_hours(self):
        """Auto-calculate work hours from check-in and check-out times."""
        if self.check_in_time and self.check_out_time:
            from datetime import datetime as dt
            cin  = dt.combine(self.date, self.check_in_time)
            cout = dt.combine(self.date, self.check_out_time)
            delta = cout - cin
            return round(delta.total_seconds() / 3600, 2)
        return None

    def calculate_late_minutes(self):
        """Return how many minutes past 9:00 AM the employee checked in."""
        if self.check_in_time:
            from datetime import time
            deadline = time(9, 0, 0)
            if self.check_in_time > deadline:
                from datetime import datetime as dt
                cin      = dt.combine(self.date, self.check_in_time)
                deadline_dt = dt.combine(self.date, deadline)
                return int((cin - deadline_dt).total_seconds() / 60)
        return 0

    def __repr__(self):
        return f'<Attendance emp={self.employee_id} date={self.date} status={self.status}>'


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 5 : messages
# Stores peer-to-peer and employee-manager chat messages
# ─────────────────────────────────────────────────────────────────────────────
class Message(db.Model):
    """
    Represents a workspace message between two users.
    """
    __tablename__ = 'messages'

    message_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_id    = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    content      = db.Column(db.Text, nullable=False)
    timestamp    = db.Column(db.DateTime, nullable=False, default=get_ist_now)
    is_read      = db.Column(db.Boolean, nullable=False, default=False)

    # Relationships
    sender    = db.relationship('User', foreign_keys=[sender_id], backref=db.backref('sent_messages', lazy='dynamic', cascade='all, delete-orphan'))
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref=db.backref('received_messages', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<Message id={self.message_id} from={self.sender_id} to={self.recipient_id}>'