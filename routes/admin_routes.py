"""
routes/admin_routes.py - Admin Panel Routes
=============================================
All routes are prefixed with /admin (set in app.py).
Only logged-in admins can access these routes.

Routes:
  GET  /admin/dashboard
  GET  /admin/employees
  POST /admin/employees/add
  POST /admin/admins/add
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
from models import db, User, Employee, LeaveRequest, Attendance, get_ist_today, get_ist_now
from forms import AddEmployeeForm, AddAdminForm, EditEmployeeForm, AdminRemarkForm
from datetime import date, datetime

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

    # Today's attendance summary
    today = get_ist_today()
    today_records    = Attendance.query.filter_by(date=today).all()
    today_present    = sum(1 for a in today_records if a.status in ('On Time', 'Late', 'Half Day'))
    today_late       = sum(1 for a in today_records if a.status == 'Late')
    today_absent     = total_employees - today_present

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
        dept_counts=dept_counts,
        today_present=today_present,
        today_late=today_late,
        today_absent=today_absent
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

    employees  = query.order_by(Employee.full_name).all()
    form       = AddEmployeeForm()   # For the "Add Employee" modal
    admin_form = AddAdminForm()      # For the "Add Admin" modal

    return render_template(
        'manage_employees.html',
        title='Manage Employees',
        employees=employees,
        form=form,
        admin_form=admin_form,
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


@admin_bp.route('/admins/add', methods=['POST'])
@admin_required
def add_admin():
    """Handle the Add Admin form submission. Creates a user with role='admin'."""
    form = AddAdminForm()

    if form.validate_on_submit():
        # Check for duplicate username
        if User.query.filter_by(username=form.username.data.strip()).first():
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('admin.manage_employees'))

        # Check for duplicate email
        if User.query.filter_by(email=form.email.data.strip()).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('admin.manage_employees'))

        # Create admin user account (no Employee profile needed)
        new_admin = User(
            username=form.username.data.strip(),
            email=form.email.data.strip(),
            role='admin'
        )
        new_admin.set_password(form.password.data)
        db.session.add(new_admin)
        db.session.commit()
        flash(f'Admin account "{new_admin.username}" created successfully!', 'success')
    else:
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


# ─────────────────────────────────────────────────────────────────────────────
# ATTENDANCE MANAGEMENT (Admin)
# ─────────────────────────────────────────────────────────────────────────────
@admin_bp.route('/attendance')
@admin_required
def manage_attendance():
    """
    Admin view of all employee attendance.
    Filters: ?date=YYYY-MM-DD, ?dept=HR, ?status=Late
    """
    filter_date   = request.args.get('date', get_ist_today().strftime('%Y-%m-%d'))
    filter_dept   = request.args.get('dept', '')
    filter_status = request.args.get('status', '')

    try:
        view_date = datetime.strptime(filter_date, '%Y-%m-%d').date()
    except ValueError:
        view_date = get_ist_today()

    query = (db.session.query(Attendance)
             .join(Employee)
             .join(User)
             .filter(Attendance.date == view_date))

    if filter_dept:
        query = query.filter(Employee.department == filter_dept)
    if filter_status:
        query = query.filter(Attendance.status == filter_status)

    records = query.order_by(Employee.full_name).all()

    # Employees with NO attendance record today (absent)
    all_employees = Employee.query.join(User).filter(User.role == 'employee').all()
    checked_in_ids = {r.employee_id for r in records}
    absent_employees = [e for e in all_employees if e.employee_id not in checked_in_ids]

    # Summary stats for this date
    total_present  = sum(1 for r in records if r.status in ('On Time', 'Late', 'Half Day'))
    total_on_time  = sum(1 for r in records if r.status == 'On Time')
    total_late     = sum(1 for r in records if r.status == 'Late')
    total_absent   = len(absent_employees)
    total_employees = Employee.query.join(User).filter(User.role == 'employee').count()

    # Departments for filter dropdown
    departments = [d[0] for d in db.session.query(Employee.department).distinct().all()]

    return render_template(
        'admin_attendance.html',
        title='Attendance Report',
        records=records,
        absent_employees=absent_employees,
        view_date=view_date,
        filter_date=filter_date,
        filter_dept=filter_dept,
        filter_status=filter_status,
        total_present=total_present,
        total_on_time=total_on_time,
        total_late=total_late,
        total_absent=total_absent,
        total_employees=total_employees,
        departments=departments
    )


@admin_bp.route('/attendance/edit/<int:attendance_id>', methods=['POST'])
@admin_required
def edit_attendance(attendance_id):
    """
    Allow admin/manager to edit an attendance record.
    Can update check-in time, check-out time, status, and notes.
    """
    record = Attendance.query.get_or_404(attendance_id)

    check_in_str  = request.form.get('check_in_time', '').strip()
    check_out_str = request.form.get('check_out_time', '').strip()
    new_status    = request.form.get('status', '').strip()
    notes         = request.form.get('notes', '').strip()

    try:
        if check_in_str:
            record.check_in_time = datetime.strptime(check_in_str, '%H:%M').time()
            # Recalculate late minutes
            deadline = datetime.strptime('09:00', '%H:%M').time()
            if record.check_in_time > deadline:
                cin_dt      = datetime.combine(record.date, record.check_in_time)
                dl_dt       = datetime.combine(record.date, deadline)
                record.late_minutes = int((cin_dt - dl_dt).total_seconds() / 60)
            else:
                record.late_minutes = 0

        if check_out_str:
            record.check_out_time = datetime.strptime(check_out_str, '%H:%M').time()

        # Recalculate work hours if both times set
        if record.check_in_time and record.check_out_time:
            cin_dt  = datetime.combine(record.date, record.check_in_time)
            cout_dt = datetime.combine(record.date, record.check_out_time)
            record.work_hours = round((cout_dt - cin_dt).total_seconds() / 3600, 2)

        if new_status in ('On Time', 'Late', 'Absent', 'Half Day'):
            record.status = new_status

        record.notes = notes if notes else None
        db.session.commit()
        flash(f'Attendance record updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating attendance: {str(e)}', 'danger')

    return redirect(url_for('admin.manage_attendance',
                            date=record.date.strftime('%Y-%m-%d')))
