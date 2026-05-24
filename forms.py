"""
forms.py - WTForms Form Definitions
=====================================
All the HTML forms used in the application are defined here using Flask-WTF.
This provides automatic CSRF protection, field validation, and cleaner templates.
"""

from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, SelectField, TextAreaField,
                     DateField, IntegerField, SubmitField, HiddenField)
from wtforms.validators import (DataRequired, Email, Length, EqualTo,
                                Optional, NumberRange, ValidationError)
from datetime import date


# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION FORMS
# ─────────────────────────────────────────────────────────────────────────────

class LoginForm(FlaskForm):
    """Form for user login (both admin and employee)."""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit   = SubmitField('Login')


class RegisterForm(FlaskForm):
    """Form for employee self-registration."""
    username    = StringField('Username',    validators=[DataRequired(), Length(min=3, max=80)])
    email       = StringField('Email',       validators=[DataRequired(), Email()])
    password    = PasswordField('Password',  validators=[DataRequired(), Length(min=6)])
    confirm_pwd = PasswordField('Confirm Password',
                                validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    full_name   = StringField('Full Name',   validators=[DataRequired(), Length(max=150)])
    department  = SelectField('Department',  choices=[
        ('IT',          'IT / Technology'),
        ('HR',          'Human Resources'),
        ('Finance',     'Finance & Accounting'),
        ('Marketing',   'Marketing'),
        ('Operations',  'Operations'),
        ('Sales',       'Sales'),
        ('Admin',       'Administration'),
    ], validators=[DataRequired()])
    phone_number = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    submit      = SubmitField('Register')


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — EMPLOYEE MANAGEMENT FORMS
# ─────────────────────────────────────────────────────────────────────────────

class AddEmployeeForm(FlaskForm):
    """Admin form to create a new employee (creates user + employee profile)."""
    username      = StringField('Username',       validators=[DataRequired(), Length(min=3, max=80)])
    email         = StringField('Email',          validators=[DataRequired(), Email()])
    password      = PasswordField('Password',     validators=[DataRequired(), Length(min=6)])
    full_name     = StringField('Full Name',      validators=[DataRequired(), Length(max=150)])
    department    = SelectField('Department', choices=[
        ('IT',          'IT / Technology'),
        ('HR',          'Human Resources'),
        ('Finance',     'Finance & Accounting'),
        ('Marketing',   'Marketing'),
        ('Operations',  'Operations'),
        ('Sales',       'Sales'),
        ('Admin',       'Administration'),
    ], validators=[DataRequired()])
    phone_number  = StringField('Phone Number',   validators=[Optional(), Length(max=20)])
    joining_date  = DateField('Joining Date',     validators=[DataRequired()])
    total_leaves  = IntegerField('Total Leaves',  validators=[DataRequired(), NumberRange(min=0, max=365)],
                                 default=20)
    submit        = SubmitField('Add Employee')


class AddAdminForm(FlaskForm):
    """Admin form to create a new admin account."""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email    = StringField('Email',    validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    submit   = SubmitField('Add Admin')



class EditEmployeeForm(FlaskForm):
    """Admin form to edit an existing employee's details."""
    full_name     = StringField('Full Name',      validators=[DataRequired(), Length(max=150)])
    email         = StringField('Email',          validators=[DataRequired(), Email()])
    department    = SelectField('Department', choices=[
        ('IT',          'IT / Technology'),
        ('HR',          'Human Resources'),
        ('Finance',     'Finance & Accounting'),
        ('Marketing',   'Marketing'),
        ('Operations',  'Operations'),
        ('Sales',       'Sales'),
        ('Admin',       'Administration'),
    ], validators=[DataRequired()])
    phone_number  = StringField('Phone Number',   validators=[Optional(), Length(max=20)])
    total_leaves  = IntegerField('Total Leaves',  validators=[DataRequired(), NumberRange(min=0, max=365)])
    submit        = SubmitField('Save Changes')


# ─────────────────────────────────────────────────────────────────────────────
# LEAVE FORMS
# ─────────────────────────────────────────────────────────────────────────────

class ApplyLeaveForm(FlaskForm):
    """Form for employees to apply for leave."""
    leave_type = SelectField('Leave Type', choices=[
        ('Sick Leave',      'Sick Leave'),
        ('Casual Leave',    'Casual Leave'),
        ('Emergency Leave', 'Emergency Leave'),
        ('Vacation Leave',  'Vacation Leave'),
    ], validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date   = DateField('End Date',   validators=[DataRequired()])
    reason     = TextAreaField('Reason', validators=[DataRequired(), Length(min=10, max=500)])
    submit     = SubmitField('Apply for Leave')

    def validate_end_date(self, field):
        """Custom validator: end date must not be before start date."""
        if self.start_date.data and field.data:
            if field.data < self.start_date.data:
                raise ValidationError('End date cannot be before start date.')

    def validate_start_date(self, field):
        """Custom validator: start date cannot be in the past."""
        if field.data and field.data < date.today():
            raise ValidationError('Start date cannot be in the past.')


class AdminRemarkForm(FlaskForm):
    """Small form used by admin to add remarks when approving/rejecting leaves."""
    admin_remarks = TextAreaField('Remarks / Comments', validators=[Optional(), Length(max=500)])
    submit        = SubmitField('Submit')


class EditProfileForm(FlaskForm):
    """Form for employees to edit their own profile."""
    full_name    = StringField('Full Name',    validators=[DataRequired(), Length(max=150)])
    email        = StringField('Email',        validators=[DataRequired(), Email()])
    phone_number = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    submit       = SubmitField('Update Profile')
