"""
routes/auth_routes.py - Authentication Routes
================================================
Handles:
  - GET/POST /login    → Login page
  - GET/POST /register → Employee self-registration
  - GET      /logout   → Log the user out
  - GET      /         → Redirect root URL to the correct dashboard
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Employee
from forms import LoginForm, RegisterForm, ForgotUsernameForm, ForgotPasswordRequestForm, ResetPasswordForm
from datetime import date

# Create a Blueprint named 'auth'
auth_bp = Blueprint('auth', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# HOME  →  redirect based on role
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/')
def index():
    """Root URL: send logged-in users to their dashboard, others to login."""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('employee.dashboard'))
    return redirect(url_for('auth.login'))


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Display login form and authenticate the user."""

    # Already logged in? Redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    form = LoginForm()

    if form.validate_on_submit():   # Form submitted + all validators passed
        # Look up the user by username
        user = User.query.filter_by(username=form.username.data.strip()).first()

        if user and user.check_password(form.password.data):
            # Credentials are correct → log in
            login_user(user)
            flash(f'Welcome back, {user.username}! 👋', 'success')

            # Redirect to the page the user originally tried to visit (if any)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)

            # Otherwise go to the role-specific dashboard
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('employee.dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html', form=form, title='Login')


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER  (Employee self-registration)
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Allow a new employee to register their own account."""

    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    form = RegisterForm()

    if form.validate_on_submit():
        # ── Check for duplicate username / email ──────────────────────────────
        existing_username = User.query.filter_by(username=form.username.data.strip()).first()
        existing_email    = User.query.filter_by(email=form.email.data.strip()).first()

        if existing_username:
            flash('Username already taken. Please choose another.', 'danger')
            return render_template('register.html', form=form, title='Register')

        if existing_email:
            flash('Email already registered. Please use a different email.', 'danger')
            return render_template('register.html', form=form, title='Register')

        # ── Create the User account ────────────────────────────────────────────
        new_user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip(),
            role='employee'
        )
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.flush()   # Get the new user_id before committing

        # ── Create the Employee profile ────────────────────────────────────────
        new_employee = Employee(
            user_id=new_user.user_id,
            full_name=form.full_name.data.strip(),
            department=form.department.data,
            phone_number=form.phone_number.data.strip() if form.phone_number.data else None,
            joining_date=date.today(),
            total_leaves=20,
            remaining_leaves=20
        )
        db.session.add(new_employee)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', form=form, title='Register')


# ─────────────────────────────────────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/logout')
@login_required
def logout():
    """Log the current user out and redirect to login page."""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


# ─────────────────────────────────────────────────────────────────────────────
# FORGOT USERNAME
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/forgot-username', methods=['GET', 'POST'])
def forgot_username():
    """Look up a username by email and simulate/display it."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    form = ForgotUsernameForm()
    recovered_username = None
    email_submitted = None

    if form.validate_on_submit():
        email = form.email.data.strip()
        user = User.query.filter_by(email=email).first()
        if user:
            recovered_username = user.username
            email_submitted = email
            flash("Recovery email simulated successfully! See preview below.", "success")
        else:
            flash("No account associated with that email was found.", "danger")

    return render_template('forgot_username.html', form=form, title='Recover Username',
                           recovered_username=recovered_username, email=email_submitted)


# ─────────────────────────────────────────────────────────────────────────────
# FORGOT PASSWORD REQUEST
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request a password reset link and simulate/display it."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    form = ForgotPasswordRequestForm()
    demo_reset_link = None
    email_submitted = None

    if form.validate_on_submit():
        email = form.email.data.strip()
        user = User.query.filter_by(email=email).first()
        if user:
            token = user.get_reset_token()
            demo_reset_link = url_for('auth.reset_password', token=token, _external=True)
            email_submitted = email
            flash("Password reset link generated successfully! Click the button below.", "success")
        else:
            flash("No account associated with that email was found.", "danger")

    return render_template('forgot_password.html', form=form, title='Forgot Password',
                           demo_reset_link=demo_reset_link, email=email_submitted)


# ─────────────────────────────────────────────────────────────────────────────
# RESET PASSWORD
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Verify reset token and let user set a new password."""
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    user = User.verify_reset_token(token)
    if not user:
        flash("The password reset link is invalid, expired, or has already been used.", "danger")
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been reset successfully! You can now log in.", "success")
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', form=form, user=user, token=token, title='Reset Password')

