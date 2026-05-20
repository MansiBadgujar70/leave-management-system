"""
app.py - Application Entry Point
==================================
This is the main file that creates and configures the Flask application.
Run this file to start the development server:
    python app.py
"""

from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
from models import db, User
from datetime import date


def create_app():
    """
    Application Factory Pattern.
    Creates and configures the Flask app instance.
    Returns the configured app.
    """
    app = Flask(__name__)

    # ── Load configuration from config.py ─────────────────────────────────────
    app.config.from_object(Config)

    # ── Initialize extensions ──────────────────────────────────────────────────
    db.init_app(app)         # Connect SQLAlchemy to the app
    CSRFProtect(app)         # Enable global CSRF protection

    # ── Set up Flask-Login ─────────────────────────────────────────────────────
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view      = 'auth.login'   # Redirect here if not logged in
    login_manager.login_message   = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        """Tell Flask-Login how to reload a user from the session."""
        return User.query.get(int(user_id))

    # ── Register Blueprints (route modules) ────────────────────────────────────
    from routes.auth_routes     import auth_bp
    from routes.admin_routes    import admin_bp
    from routes.employee_routes import employee_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp,    url_prefix='/admin')
    app.register_blueprint(employee_bp, url_prefix='/employee')

    # ── Jinja2 global helpers ──────────────────────────────────────────────────
    @app.template_filter('dateformat')
    def dateformat(value, fmt='%d %b %Y'):
        """Custom Jinja filter: format a date object nicely."""
        if value is None:
            return '—'
        if isinstance(value, str):
            return value
        return value.strftime(fmt)

    @app.context_processor
    def inject_today():
        """Make today's date available in every template."""
        return {'today': date.today()}

    # ── Create tables + seed data on first run ────────────────────────────────
    with app.app_context():
        db.create_all()          # Create tables if they don't exist
        seed_initial_data()      # Insert sample admin + employees

    return app


# ─────────────────────────────────────────────────────────────────────────────
# SEED / SAMPLE DATA
# Creates a default admin and two sample employees so the app is usable
# immediately after setup.
# ─────────────────────────────────────────────────────────────────────────────
def seed_initial_data():
    """
    Insert default users and employees if the database is empty.
    Called once at startup; does nothing if data already exists.
    """
    from models import User, Employee, LeaveRequest
    from datetime import date, timedelta

    # Skip if admin already exists
    if User.query.filter_by(role='admin').first():
        return

    print("[Seed] Seeding initial data...")

    # ── Create Admin ──────────────────────────────────────────────────────────
    admin = User(
        username='admin',
        email='admin@leavesystem.com',
        role='admin'
    )
    admin.set_password('admin123')
    db.session.add(admin)

    # ── Create Employee 1: Alice ──────────────────────────────────────────────
    emp_user1 = User(username='alice', email='alice@company.com', role='employee')
    emp_user1.set_password('alice123')
    db.session.add(emp_user1)
    db.session.flush()   # Get the auto-generated user_id before committing

    emp1 = Employee(
        user_id=emp_user1.user_id,
        full_name='Alice Johnson',
        department='IT',
        phone_number='9876543210',
        joining_date=date(2023, 1, 15),
        total_leaves=20,
        remaining_leaves=17
    )
    db.session.add(emp1)
    db.session.flush()

    # ── Sample leave requests for Alice ───────────────────────────────────────
    lr1 = LeaveRequest(
        employee_id=emp1.employee_id,
        leave_type='Sick Leave',
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() - timedelta(days=28),
        total_days=3,
        reason='Fever and flu. Needed rest.',
        status='Approved',
        admin_remarks='Get well soon!',
        applied_at=date.today() - timedelta(days=32)
    )

    lr2 = LeaveRequest(
        employee_id=emp1.employee_id,
        leave_type='Casual Leave',
        start_date=date.today() + timedelta(days=5),
        end_date=date.today() + timedelta(days=5),
        total_days=1,
        reason='Personal work at home.',
        status='Pending',
        applied_at=date.today() - timedelta(days=1)
    )
    db.session.add_all([lr1, lr2])

    # ── Create Employee 2: Bob ────────────────────────────────────────────────
    emp_user2 = User(username='bob', email='bob@company.com', role='employee')
    emp_user2.set_password('bob123')
    db.session.add(emp_user2)
    db.session.flush()

    emp2 = Employee(
        user_id=emp_user2.user_id,
        full_name='Bob Martinez',
        department='HR',
        phone_number='9123456780',
        joining_date=date(2022, 6, 1),
        total_leaves=20,
        remaining_leaves=15
    )
    db.session.add(emp2)
    db.session.flush()

    lr3 = LeaveRequest(
        employee_id=emp2.employee_id,
        leave_type='Vacation Leave',
        start_date=date.today() - timedelta(days=10),
        end_date=date.today() - timedelta(days=6),
        total_days=5,
        reason='Annual family vacation.',
        status='Approved',
        admin_remarks='Approved. Enjoy!',
        applied_at=date.today() - timedelta(days=15)
    )

    lr4 = LeaveRequest(
        employee_id=emp2.employee_id,
        leave_type='Emergency Leave',
        start_date=date.today() - timedelta(days=60),
        end_date=date.today() - timedelta(days=60),
        total_days=1,
        reason='Family emergency.',
        status='Rejected',
        admin_remarks='Insufficient notice given.',
        applied_at=date.today() - timedelta(days=61)
    )
    db.session.add_all([lr3, lr4])

    db.session.commit()
    print("[Seed] Sample data seeded successfully!")
    print("    Admin    -> username: admin   | password: admin123")
    print("    Employee -> username: alice   | password: alice123")
    print("    Employee -> username: bob     | password: bob123")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app = create_app()
    # debug=True enables auto-reloading and better error messages
    # Set debug=False for production
    app.run(debug=True, host='0.0.0.0', port=5000)
