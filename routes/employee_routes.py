"""
routes/employee_routes.py - Employee Panel Routes
===================================================
All routes are prefixed with /employee (set in app.py).
Only logged-in employees (role='employee') can access these routes.

Routes:
  GET      /employee/dashboard
  GET/POST /employee/apply-leave
  GET      /employee/leave-history
  GET/POST /employee/profile
  POST     /employee/leave/cancel/<id>
"""

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request)
from flask_login import login_required, current_user
from functools import wraps
from models import db, Employee, LeaveRequest
from forms import ApplyLeaveForm, EditProfileForm
from datetime import date, timedelta

employee_bp = Blueprint('employee', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# ACCESS CONTROL DECORATOR
# ─────────────────────────────────────────────────────────────────────────────
def employee_required(f):
    """Ensure only employees (not admins) can access these routes."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'employee':
            flash('Access denied. Employee account required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_employee():
    """Helper: fetch the Employee record for the currently logged-in user."""
    return Employee.query.filter_by(user_id=current_user.user_id).first()


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
@employee_bp.route('/dashboard')
@employee_required
def dashboard():
    """
    Employee dashboard showing:
    - Leave balance summary
    - Recent leave applications
    """
    employee = get_current_employee()
    if not employee:
        flash('Employee profile not found. Please contact admin.', 'danger')
        return redirect(url_for('auth.logout'))

    # Count leaves by status
    approved_count = employee.leave_requests.filter_by(status='Approved').count()
    pending_count  = employee.leave_requests.filter_by(status='Pending').count()
    rejected_count = employee.leave_requests.filter_by(status='Rejected').count()

    # Last 5 recent applications for the dashboard table
    recent_leaves = (employee.leave_requests
                     .order_by(LeaveRequest.applied_at.desc())
                     .limit(5).all())

    return render_template(
        'employee_dashboard.html',
        title='My Dashboard',
        employee=employee,
        approved_count=approved_count,
        pending_count=pending_count,
        rejected_count=rejected_count,
        recent_leaves=recent_leaves
    )


# ─────────────────────────────────────────────────────────────────────────────
# APPLY FOR LEAVE
# ─────────────────────────────────────────────────────────────────────────────
@employee_bp.route('/apply-leave', methods=['GET', 'POST'])
@employee_required
def apply_leave():
    """
    Let an employee submit a new leave application.
    Validates:
      1. End date >= start date
      2. No overlapping leave requests
      3. Sufficient remaining leave balance
    """
    employee = get_current_employee()
    form     = ApplyLeaveForm()

    if form.validate_on_submit():
        start = form.start_date.data
        end   = form.end_date.data

        # ── Calculate total working days (inclusive) ──────────────────────────
        total_days = (end - start).days + 1

        # ── Overlap check ──────────────────────────────────────────────────────
        # A leave overlaps if: new_start <= existing_end AND new_end >= existing_start
        overlapping = (employee.leave_requests
                       .filter(LeaveRequest.status != 'Rejected')   # Ignore rejected
                       .filter(LeaveRequest.start_date <= end)
                       .filter(LeaveRequest.end_date   >= start)
                       .first())

        if overlapping:
            flash(
                f'You already have a leave request (#{overlapping.leave_id}) '
                f'that overlaps with the selected dates '
                f'({overlapping.start_date} → {overlapping.end_date}). '
                f'Please choose different dates.',
                'danger'
            )
            return render_template('apply_leave.html', form=form, employee=employee, title='Apply for Leave')

        # ── Leave balance check ────────────────────────────────────────────────
        if employee.remaining_leaves < total_days:
            flash(
                f'Insufficient leave balance. You have {employee.remaining_leaves} days remaining, '
                f'but requested {total_days} days.',
                'danger'
            )
            return render_template('apply_leave.html', form=form, employee=employee, title='Apply for Leave')

        # ── Create the leave request ────────────────────────────────────────────
        new_leave = LeaveRequest(
            employee_id=employee.employee_id,
            leave_type=form.leave_type.data,
            start_date=start,
            end_date=end,
            total_days=total_days,
            reason=form.reason.data.strip(),
            status='Pending'
        )
        db.session.add(new_leave)
        db.session.commit()

        flash(
            f'Leave application submitted successfully! '
            f'({total_days} day{"s" if total_days > 1 else ""} of {form.leave_type.data})',
            'success'
        )
        return redirect(url_for('employee.leave_history'))

    return render_template('apply_leave.html', form=form, employee=employee, title='Apply for Leave')


# ─────────────────────────────────────────────────────────────────────────────
# LEAVE HISTORY
# ─────────────────────────────────────────────────────────────────────────────
@employee_bp.route('/leave-history')
@employee_required
def leave_history():
    """
    Show all past and present leave applications for the current employee.
    Optional filter by status via query param: ?status=Pending|Approved|Rejected
    """
    employee      = get_current_employee()
    status_filter = request.args.get('status', 'All')

    query = employee.leave_requests

    if status_filter in ('Pending', 'Approved', 'Rejected'):
        query = query.filter_by(status=status_filter)

    leaves = query.order_by(LeaveRequest.applied_at.desc()).all()

    return render_template(
        'leave_history.html',
        title='Leave History',
        employee=employee,
        leaves=leaves,
        status_filter=status_filter
    )


# ─────────────────────────────────────────────────────────────────────────────
# CANCEL LEAVE  (employee can cancel their own Pending leave)
# ─────────────────────────────────────────────────────────────────────────────
@employee_bp.route('/leave/cancel/<int:leave_id>', methods=['POST'])
@employee_required
def cancel_leave(leave_id):
    """
    Allow an employee to cancel a Pending leave request.
    Only Pending leaves can be cancelled (Approved/Rejected cannot).
    """
    employee = get_current_employee()
    leave    = LeaveRequest.query.get_or_404(leave_id)

    # Security: ensure this leave belongs to the current employee
    if leave.employee_id != employee.employee_id:
        flash('You are not authorized to cancel this leave request.', 'danger')
        return redirect(url_for('employee.leave_history'))

    if leave.status != 'Pending':
        flash('Only pending leaves can be cancelled.', 'warning')
        return redirect(url_for('employee.leave_history'))

    db.session.delete(leave)
    db.session.commit()
    flash(f'Leave request #{leave_id} cancelled successfully.', 'info')
    return redirect(url_for('employee.leave_history'))


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────────────────────────────────────
@employee_bp.route('/profile', methods=['GET', 'POST'])
@employee_required
def profile():
    """Let the employee view and edit their own profile details."""
    employee = get_current_employee()
    form     = EditProfileForm()

    if request.method == 'GET':
        # Pre-fill the form with current data
        form.full_name.data    = employee.full_name
        form.email.data        = employee.user.email
        form.phone_number.data = employee.phone_number

    if form.validate_on_submit():
        from models import User
        # Check if new email is taken by another user
        existing = User.query.filter_by(email=form.email.data.strip()).first()
        if existing and existing.user_id != current_user.user_id:
            flash('That email is already in use by another account.', 'danger')
            return render_template('profile.html', form=form, employee=employee, title='My Profile')

        # Apply updates
        employee.full_name    = form.full_name.data.strip()
        employee.phone_number = form.phone_number.data.strip() if form.phone_number.data else None
        employee.user.email   = form.email.data.strip()

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('employee.profile'))

    return render_template('profile.html', form=form, employee=employee, title='My Profile')
