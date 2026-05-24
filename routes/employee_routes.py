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
                   flash, request, jsonify)
from flask_login import login_required, current_user
from functools import wraps
from models import db, Employee, LeaveRequest, Attendance
from forms import ApplyLeaveForm, EditProfileForm
from datetime import date, timedelta, datetime, time


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

    # Today's attendance record
    today_attendance = Attendance.query.filter_by(
        employee_id=employee.employee_id,
        date=date.today()
    ).first()

    # Monthly attendance summary (current month)
    from datetime import date as dt_date
    first_of_month = date.today().replace(day=1)
    monthly_records = Attendance.query.filter(
        Attendance.employee_id == employee.employee_id,
        Attendance.date >= first_of_month,
        Attendance.date <= date.today()
    ).all()
    monthly_present  = sum(1 for a in monthly_records if a.status in ('On Time', 'Late', 'Half Day'))
    monthly_late     = sum(1 for a in monthly_records if a.status == 'Late')
    monthly_absent   = sum(1 for a in monthly_records if a.status == 'Absent')
    total_work_hours = sum(a.work_hours or 0 for a in monthly_records)

    return render_template(
        'employee_dashboard.html',
        title='My Dashboard',
        employee=employee,
        approved_count=approved_count,
        pending_count=pending_count,
        rejected_count=rejected_count,
        recent_leaves=recent_leaves,
        today_attendance=today_attendance,
        monthly_present=monthly_present,
        monthly_late=monthly_late,
        monthly_absent=monthly_absent,
        total_work_hours=round(total_work_hours, 1)
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


# ─────────────────────────────────────────────────────────────────────────────
# ATTENDANCE — CHECK IN
# ─────────────────────────────────────────────────────────────────────────────
@employee_bp.route('/attendance/check-in', methods=['POST'])
@employee_required
def check_in():
    """
    Record employee check-in for today.
    Business rules:
      - 9:00 AM deadline → On Time if at/before, Late if after
      - Only one check-in per day allowed
    """
    employee = get_current_employee()
    today    = date.today()
    now_time = datetime.now().time()

    # Check if already checked in today
    existing = Attendance.query.filter_by(employee_id=employee.employee_id, date=today).first()
    if existing and existing.check_in_time:
        flash(f'You have already checked in today at {existing.check_in_time.strftime("%I:%M %p")}.', 'warning')
        return redirect(url_for('employee.dashboard'))

    # Determine late status
    deadline     = time(9, 0, 0)
    late_minutes = 0
    if now_time > deadline:
        from datetime import datetime as dt
        cin_dt       = dt.combine(today, now_time)
        deadline_dt  = dt.combine(today, deadline)
        late_minutes = int((cin_dt - deadline_dt).total_seconds() / 60)
        status = 'Late'
    else:
        status = 'On Time'

    if existing:
        # Update existing Absent record
        existing.check_in_time = now_time
        existing.status        = status
        existing.late_minutes  = late_minutes
    else:
        record = Attendance(
            employee_id   = employee.employee_id,
            date          = today,
            check_in_time = now_time,
            status        = status,
            late_minutes  = late_minutes
        )
        db.session.add(record)

    db.session.commit()

    if late_minutes > 0:
        flash(f'Checked in at {now_time.strftime("%I:%M %p")} — {late_minutes} minutes late.', 'warning')
    else:
        flash(f'Good morning! Checked in at {now_time.strftime("%I:%M %p")} — On Time ✓', 'success')

    return redirect(url_for('employee.dashboard'))


# ─────────────────────────────────────────────────────────────────────────────
# ATTENDANCE — CHECK OUT
# ─────────────────────────────────────────────────────────────────────────────
@employee_bp.route('/attendance/check-out', methods=['POST'])
@employee_required
def check_out():
    """
    Record employee check-out for today and calculate total work hours.
    Half Day: < 4 hours worked.
    """
    employee = get_current_employee()
    today    = date.today()
    now_time = datetime.now().time()

    record = Attendance.query.filter_by(employee_id=employee.employee_id, date=today).first()

    if not record or not record.check_in_time:
        flash('You have not checked in today. Please check in first.', 'danger')
        return redirect(url_for('employee.dashboard'))

    if record.check_out_time:
        flash(f'You have already checked out today at {record.check_out_time.strftime("%I:%M %p")}.', 'warning')
        return redirect(url_for('employee.dashboard'))

    # Calculate work hours
    from datetime import datetime as dt
    cin_dt   = dt.combine(today, record.check_in_time)
    cout_dt  = dt.combine(today, now_time)
    work_hrs = round((cout_dt - cin_dt).total_seconds() / 3600, 2)

    record.check_out_time = now_time
    record.work_hours     = work_hrs

    # If worked less than 4 hours, mark as Half Day
    if work_hrs < 4.0:
        record.status = 'Half Day'

    db.session.commit()
    flash(f'Checked out at {now_time.strftime("%I:%M %p")} — Total: {work_hrs:.1f} hours worked today.', 'success')
    return redirect(url_for('employee.dashboard'))


# ─────────────────────────────────────────────────────────────────────────────
# ATTENDANCE HISTORY — Employee's own records
# ─────────────────────────────────────────────────────────────────────────────
@employee_bp.route('/attendance')
@employee_required
def attendance_history():
    """Show the employee's full attendance history, newest first."""
    employee = get_current_employee()

    # Filter by month if provided
    month_str = request.args.get('month', '')
    if month_str:
        try:
            year, month = map(int, month_str.split('-'))
            from calendar import monthrange
            last_day = monthrange(year, month)[1]
            records = Attendance.query.filter(
                Attendance.employee_id == employee.employee_id,
                Attendance.date >= date(year, month, 1),
                Attendance.date <= date(year, month, last_day)
            ).order_by(Attendance.date.desc()).all()
        except Exception:
            records = Attendance.query.filter_by(employee_id=employee.employee_id).order_by(Attendance.date.desc()).all()
    else:
        records = Attendance.query.filter_by(employee_id=employee.employee_id).order_by(Attendance.date.desc()).all()

    # Summary stats for the filtered period
    total_present  = sum(1 for r in records if r.status in ('On Time', 'Late', 'Half Day'))
    total_late     = sum(1 for r in records if r.status == 'Late')
    total_absent   = sum(1 for r in records if r.status == 'Absent')
    total_hrs      = round(sum(r.work_hours or 0 for r in records), 1)
    avg_late_mins  = round(sum(r.late_minutes for r in records if r.late_minutes > 0) /
                           max(total_late, 1), 0)

    return render_template(
        'employee_attendance.html',
        title='My Attendance',
        employee=employee,
        records=records,
        total_present=total_present,
        total_late=total_late,
        total_absent=total_absent,
        total_hrs=total_hrs,
        avg_late_mins=int(avg_late_mins),
        month_str=month_str
    )

