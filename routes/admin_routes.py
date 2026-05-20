"""
routes/admin_routes.py - Admin Panel Routes
=============================================
All routes are prefixed with /admin (set in app.py).
Only logged-in admins can access these routes.

Routes:
  GET  /admin/dashboard
  GET  /admin/employees
  POST /admin/employees/add
  GET  /admin/employees/edit/<id>
  POST /admin/employees/edit/<id>
  POST /admin/employees/delete/<id>
  GET  /admin/leaves
  POST /admin/leaves/approve/<id>
  POST /admin/leaves/reject/<id>
  GET  /admin/leaves/<id>
"""

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort, jsonify)
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, Employee, LeaveRequest
from forms import AddEmployeeForm, EditEmployeeForm, AdminRemarkForm
from datetime import date

admin_bp = Blueprint('admin', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# ACCESS CONTROL DECORATOR
# Ensures only admin users can access admin routes
# ─────────────────────────────────────────────────────────────────────────────
def admin_required(f):
    """
    Custom decorator that:
    1. Requires the user to be logged in (via @login_required)
    2. Requires the user to have role='admin'
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """
    Admin dashboard showing key statistics:
    - Total employees
    - Total leave requests
    - Counts by status (Pending / Approved / Rejected)
    """
    total_employees = Employee.query.count()
    total_leaves    = LeaveRequest.query.count()
    pending_leaves  = LeaveRequest.query.filter_by(status='Pending').count()
    approved_leaves = LeaveRequest.query.filter_by(status='Approved').count()
    rejected_leaves = LeaveRequest.query.filter_by(status='Rejected').count()

    # Recent 5 leave requests for the quick-view table
    recent_leaves = (LeaveRequest.query
                     .order_by(LeaveRequest.applied_at.desc())
                     .limit(5).all())

    # Department-wise employee count for the chart
    dept_data = (db.session.query(Employee.department, db.func.count(Employee.employee_id))
                 .group_by(Employee.department).all())
    dept_labels  = [d[0] for d in dept_data]
    dept_counts  = [d[1] for d in dept_data]

    return render_template(
        'admin_dashboard.html',
        title='Admin Dashboard',
        total_employees=total_employees,
        total_leaves=total_leaves,
        pending_leaves=pending_leaves,
        approved_leaves=approved_leaves,
        rejected_leaves=rejected_leaves,
        recent_leaves=recent_leaves,
        dept_labels=dept_labels,
        dept_counts=dept_counts
    )


# ─────────────────────────────────────────────────────────────────────────────
# EMPLOYEE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route('/employees')
@admin_required
def manage_employees():
    """
    List all employees with search functionality.
    Query param: ?search=keyword
    """
    search  = request.args.get('search', '').strip()
    query   = Employee.query.join(User)  # Join so we can search by username/email too

    if search:
        like_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                Employee.full_name.ilike(like_pattern),
                Employee.department.ilike(like_pattern),
                User.email.ilike(like_pattern),
                User.username.ilike(like_pattern)
            )
        )

    employees = query.order_by(Employee.full_name).all()
    form      = AddEmployeeForm()   # For the "Add Employee" modal

    return render_template(
        'manage_employees.html',
        title='Manage Employees',
        employees=employees,
        form=form,
        search=search
    )


@admin_bp.route('/employees/add', methods=['POST'])
@admin_required
def add_employee():
    """Handle the Add Employee form submission (modal form on manage_employees page)."""
    form = AddEmployeeForm()

    if form.validate_on_submit():
        # Check for duplicate username / email
        if User.query.filter_by(username=form.username.data.strip()).first():
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('admin.manage_employees'))

        if User.query.filter_by(email=form.email.data.strip()).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('admin.manage_employees'))

        # Create user account
        new_user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip(),
            role='employee'
        )
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.flush()

        # Create employee profile
        new_emp = Employee(
            user_id=new_user.user_id,
            full_name=form.full_name.data.strip(),
            department=form.department.data,
            phone_number=form.phone_number.data.strip() if form.phone_number.data else None,
            joining_date=form.joining_date.data,
            total_leaves=form.total_leaves.data,
            remaining_leaves=form.total_leaves.data   # Initially equal to total
        )
        db.session.add(new_emp)
        db.session.commit()
        flash(f'Employee "{new_emp.full_name}" added successfully!', 'success')
    else:
        # Collect all validation errors and flash them
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')

    return redirect(url_for('admin.manage_employees'))


@admin_bp.route('/employees/edit/<int:emp_id>', methods=['GET', 'POST'])
@admin_required
def edit_employee(emp_id):
    """Edit an existing employee's details."""
    employee = Employee.query.get_or_404(emp_id)
    form     = EditEmployeeForm(obj=employee)

    # Pre-fill email from the related user
    if request.method == 'GET':
        form.email.data = employee.user.email

    if form.validate_on_submit():
        # Check if new email is taken by a different user
        existing = User.query.filter_by(email=form.email.data.strip()).first()
        if existing and existing.user_id != employee.user_id:
            flash('That email is already in use by another account.', 'danger')
            return render_template('edit_employee.html', form=form, employee=employee, title='Edit Employee')

        # Update employee profile fields
        employee.full_name    = form.full_name.data.strip()
        employee.department   = form.department.data
        employee.phone_number = form.phone_number.data.strip() if form.phone_number.data else None

        # Adjust remaining leaves if total leaves changed
        old_total     = employee.total_leaves
        new_total     = form.total_leaves.data
        diff          = new_total - old_total
        employee.total_leaves    = new_total
        employee.remaining_leaves = max(0, employee.remaining_leaves + diff)

        # Update email on the User record
        employee.user.email = form.email.data.strip()

        db.session.commit()
        flash(f'Employee "{employee.full_name}" updated successfully!', 'success')
        return redirect(url_for('admin.manage_employees'))

    return render_template('edit_employee.html', form=form, employee=employee, title='Edit Employee')


@admin_bp.route('/employees/delete/<int:emp_id>', methods=['POST'])
@admin_required
def delete_employee(emp_id):
    """Delete an employee (and their user account) from the system."""
    employee = Employee.query.get_or_404(emp_id)
    name     = employee.full_name
    user     = employee.user

    # Deleting the user cascades to the employee profile and leave requests
    db.session.delete(user)
    db.session.commit()
    flash(f'Employee "{name}" has been deleted successfully.', 'success')
    return redirect(url_for('admin.manage_employees'))


# ─────────────────────────────────────────────────────────────────────────────
# LEAVE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route('/leaves')
@admin_required
def manage_leaves():
    """
    View all leave requests with optional status filter.
    Query param: ?status=Pending|Approved|Rejected
    """
    status_filter = request.args.get('status', 'All')

    query = LeaveRequest.query.join(Employee).join(User)

    if status_filter in ('Pending', 'Approved', 'Rejected'):
        query = query.filter(LeaveRequest.status == status_filter)

    leaves = query.order_by(LeaveRequest.applied_at.desc()).all()
    form   = AdminRemarkForm()

    return render_template(
        'manage_leaves.html',
        title='Manage Leave Requests',
        leaves=leaves,
        form=form,
        status_filter=status_filter
    )


@admin_bp.route('/leaves/approve/<int:leave_id>', methods=['POST'])
@admin_required
def approve_leave(leave_id):
    """
    Approve a pending leave request.
    Deducts total_days from employee's remaining_leaves.
    """
    leave    = LeaveRequest.query.get_or_404(leave_id)
    employee = leave.employee
    form     = AdminRemarkForm()

    if leave.status != 'Pending':
        flash('Only pending leaves can be approved.', 'warning')
        return redirect(url_for('admin.manage_leaves'))

    # Check if employee has enough remaining leaves
    if employee.remaining_leaves < leave.total_days:
        flash(f'Cannot approve: {employee.full_name} only has '
              f'{employee.remaining_leaves} remaining leave days.', 'danger')
        return redirect(url_for('admin.manage_leaves'))

    # Deduct leave days
    employee.remaining_leaves -= leave.total_days

    # Update leave status
    leave.status        = 'Approved'
    
    # Retrieve remarks from WTForm or direct fallback
    remarks = None
    if form.admin_remarks.data:
        remarks = form.admin_remarks.data.strip()
    elif 'admin_remarks' in request.form:
        remarks = request.form.get('admin_remarks', '').strip()
    leave.admin_remarks = remarks if remarks else None

    db.session.commit()
    flash(f'Leave #{leave_id} approved successfully.', 'success')
    return redirect(url_for('admin.manage_leaves'))


@admin_bp.route('/leaves/reject/<int:leave_id>', methods=['POST'])
@admin_required
def reject_leave(leave_id):
    """
    Reject a leave request.
    If the leave was previously Approved, restore the leave days.
    """
    leave    = LeaveRequest.query.get_or_404(leave_id)
    employee = leave.employee
    form     = AdminRemarkForm()

    if leave.status == 'Rejected':
        flash('This leave is already rejected.', 'warning')
        return redirect(url_for('admin.manage_leaves'))

    # Restore leave days if it was previously approved
    if leave.status == 'Approved':
        employee.remaining_leaves = min(
            employee.total_leaves,
            employee.remaining_leaves + leave.total_days
        )

    leave.status        = 'Rejected'
    
    # Retrieve remarks from WTForm or direct fallback
    remarks = None
    if form.admin_remarks.data:
        remarks = form.admin_remarks.data.strip()
    elif 'admin_remarks' in request.form:
        remarks = request.form.get('admin_remarks', '').strip()
    leave.admin_remarks = remarks if remarks else None

    db.session.commit()
    flash(f'Leave #{leave_id} rejected.', 'info')
    return redirect(url_for('admin.manage_leaves'))


@admin_bp.route('/leaves/<int:leave_id>')
@admin_required
def view_leave(leave_id):
    """View full details of a single leave request."""
    leave = LeaveRequest.query.get_or_404(leave_id)
    form  = AdminRemarkForm()
    return render_template('view_leave.html', leave=leave, form=form, title='Leave Details')
