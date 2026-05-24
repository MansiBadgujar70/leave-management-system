"""
test_app.py - Automated Unit & Integration Tests
==================================================
Tests the Leave Management System backend logic:
  - Authentication (Login, Register, Logout)
  - Leave Application (Validations, overlap checks, balance checks)
  - Admin operations (Approve, Reject, Revoke, Employee CRUD)
  - Role-based Access Control (RBAC)

Run this file using:
    venv\\Scripts\\python test_app.py
"""

import unittest
from datetime import date, timedelta
from app import create_app
from models import db, User, Employee, LeaveRequest


class LeaveSystemTestCase(unittest.TestCase):
    """Test suite for the Leave Management System."""

    def setUp(self):
        """Set up test database and test client."""
        # Create Flask app and configure for testing
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        # Use an in-memory SQLite database for fast, isolated testing
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        # Create all tables in the in-memory database
        db.create_all()

        # Set up a default Admin and Employees
        self.seed_test_data()

    def tearDown(self):
        """Clean up database after each test."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def seed_test_data(self):
        """Helper to seed initial users and employees for testing."""
        # 1. Admin
        self.admin_user = User(username='test_admin', email='admin@test.com', role='admin')
        self.admin_user.set_password('adminpwd')
        db.session.add(self.admin_user)

        # 2. Employee 1 (Alice)
        self.emp_user1 = User(username='test_alice', email='alice@test.com', role='employee')
        self.emp_user1.set_password('alicepwd')
        db.session.add(self.emp_user1)
        db.session.flush()

        self.emp1 = Employee(
            user_id=self.emp_user1.user_id,
            full_name='Alice Tester',
            department='IT',
            phone_number='1234567890',
            joining_date=date.today() - timedelta(days=100),
            total_leaves=20,
            remaining_leaves=20
        )
        db.session.add(self.emp1)

        # 3. Employee 2 (Bob)
        self.emp_user2 = User(username='test_bob', email='bob@test.com', role='employee')
        self.emp_user2.set_password('bobpwd')
        db.session.add(self.emp_user2)
        db.session.flush()

        self.emp2 = Employee(
            user_id=self.emp_user2.user_id,
            full_name='Bob Tester',
            department='HR',
            phone_number='0987654321',
            joining_date=date.today() - timedelta(days=50),
            total_leaves=20,
            remaining_leaves=15
        )
        db.session.add(self.emp2)
        db.session.commit()

    # ─── HELPER LOGIN FUNCTIONS ──────────────────────────────────────────────
    def login(self, username, password):
        """Helper to perform a login request."""
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def logout(self):
        """Helper to perform a logout request."""
        return self.client.get('/logout', follow_redirects=True)

    # ─── AUTHENTICATION TESTS ────────────────────────────────────────────────
    def test_login_success(self):
        """Test successful login for admin and employee."""
        # Employee login
        response = self.login('test_alice', 'alicepwd')
        self.assertIn(b'My Dashboard', response.data)
        self.assertIn(b'Alice Tester', response.data)

        self.logout()

        # Admin login
        response = self.login('test_admin', 'adminpwd')
        self.assertIn(b'Admin Dashboard', response.data)
        self.assertIn(b'test_admin', response.data)

    def test_login_failure(self):
        """Test login with incorrect credentials."""
        response = self.login('test_alice', 'wrongpwd')
        self.assertIn(b'Invalid username or password', response.data)

    def test_employee_registration(self):
        """Test employee self-registration route."""
        response = self.client.post('/register', data=dict(
            username='new_emp',
            email='new@test.com',
            password='password123',
            confirm_pwd='password123',
            full_name='New Employee',
            department='Finance',
            phone_number='5555555555'
        ), follow_redirects=True)

        self.assertIn(b'Registration successful', response.data)

        # Verify user and employee exist in database
        user = User.query.filter_by(username='new_emp').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role, 'employee')
        self.assertEqual(user.employee.full_name, 'New Employee')
        self.assertEqual(user.employee.department, 'Finance')

    # ─── BUSINESS LOGIC & LEAVE VALIDATION TESTS ─────────────────────────────
    def test_apply_leave_success(self):
        """Test applying for a leave request with valid parameters."""
        self.login('test_alice', 'alicepwd')

        # Apply for 3 days of Casual Leave
        start = date.today() + timedelta(days=2)
        end = date.today() + timedelta(days=4)

        response = self.client.post('/employee/apply-leave', data=dict(
            leave_type='Casual Leave',
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d'),
            reason='Need time off for family function'
        ), follow_redirects=True)

        self.assertIn(b'Leave application submitted successfully', response.data)

        # Check database record
        lr = LeaveRequest.query.filter_by(employee_id=self.emp1.employee_id).first()
        self.assertIsNotNone(lr)
        self.assertEqual(lr.leave_type, 'Casual Leave')
        self.assertEqual(lr.total_days, 3)
        self.assertEqual(lr.status, 'Pending')

    def test_apply_leave_overlap(self):
        """Test that overlapping leave requests are blocked."""
        self.login('test_alice', 'alicepwd')

        start1 = date.today() + timedelta(days=5)
        end1 = date.today() + timedelta(days=8)

        # Submit first leave
        self.client.post('/employee/apply-leave', data=dict(
            leave_type='Sick Leave',
            start_date=start1.strftime('%Y-%m-%d'),
            end_date=end1.strftime('%Y-%m-%d'),
            reason='First request reasons here'
        ))

        # Attempt to submit overlapping leave (ends after first starts, and starts before first ends)
        start2 = date.today() + timedelta(days=6)
        end2 = date.today() + timedelta(days=7)

        response = self.client.post('/employee/apply-leave', data=dict(
            leave_type='Casual Leave',
            start_date=start2.strftime('%Y-%m-%d'),
            end_date=end2.strftime('%Y-%m-%d'),
            reason='Overlapping request reasons'
        ), follow_redirects=True)

        self.assertIn(b'overlaps with the selected dates', response.data)
        # Check that only 1 leave exists in the database
        count = LeaveRequest.query.filter_by(employee_id=self.emp1.employee_id).count()
        self.assertEqual(count, 1)

    def test_apply_leave_insufficient_balance(self):
        """Test that applying for leaves exceeding remaining balance is blocked."""
        self.login('test_alice', 'alicepwd')

        # Alice has 20 remaining leaves. Request 25 days.
        start = date.today() + timedelta(days=2)
        end = date.today() + timedelta(days=26)

        response = self.client.post('/employee/apply-leave', data=dict(
            leave_type='Vacation Leave',
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d'),
            reason='Long vacation request'
        ), follow_redirects=True)

        self.assertIn(b'Insufficient leave balance', response.data)
        count = LeaveRequest.query.filter_by(employee_id=self.emp1.employee_id).count()
        self.assertEqual(count, 0)

    # ─── ADMIN APPROVAL / REJECTION TESTS ────────────────────────────────────
    def test_admin_approve_leave(self):
        """Test that admin can approve a pending leave, and leave balance is deducted."""
        # 1. Employee applies
        self.login('test_alice', 'alicepwd')
        start = date.today() + timedelta(days=2)
        end = date.today() + timedelta(days=4)  # 3 days
        self.client.post('/employee/apply-leave', data=dict(
            leave_type='Vacation Leave',
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d'),
            reason='Checking approval logic'
        ))
        lr = LeaveRequest.query.filter_by(employee_id=self.emp1.employee_id).first()
        self.assertEqual(self.emp1.remaining_leaves, 20)  # Remains 20 while pending
        self.logout()

        # 2. Admin logs in and approves
        self.login('test_admin', 'adminpwd')
        response = self.client.post(f'/admin/leaves/approve/{lr.leave_id}', data=dict(
            admin_remarks='Have fun!'
        ), follow_redirects=True)

        self.assertIn(b'approved successfully', response.data)

        # Refresh db models
        db.session.refresh(lr)
        db.session.refresh(self.emp1)

        self.assertEqual(lr.status, 'Approved')
        self.assertEqual(lr.admin_remarks, 'Have fun!')
        self.assertEqual(self.emp1.remaining_leaves, 17)  # 20 - 3 = 17

    def test_admin_reject_leave(self):
        """Test that admin can reject a pending leave request, keeping balance intact."""
        # 1. Employee applies
        self.login('test_alice', 'alicepwd')
        start = date.today() + timedelta(days=2)
        end = date.today() + timedelta(days=4)  # 3 days
        self.client.post('/employee/apply-leave', data=dict(
            leave_type='Vacation Leave',
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d'),
            reason='Checking rejection logic'
        ))
        lr = LeaveRequest.query.filter_by(employee_id=self.emp1.employee_id).first()
        self.logout()

        # 2. Admin logs in and rejects
        self.login('test_admin', 'adminpwd')
        response = self.client.post(f'/admin/leaves/reject/{lr.leave_id}', data=dict(
            admin_remarks='Rejected due to project deadlines'
        ), follow_redirects=True)

        self.assertIn(b'rejected', response.data)

        # Refresh db models
        db.session.refresh(lr)
        db.session.refresh(self.emp1)

        self.assertEqual(lr.status, 'Rejected')
        self.assertEqual(lr.admin_remarks, 'Rejected due to project deadlines')
        self.assertEqual(self.emp1.remaining_leaves, 20)  # Balance remains 20

    def test_admin_revoke_approved_leave(self):
        """Test revoking an approved leave restores the employee's leave balance."""
        # 1. Employee applies
        self.login('test_alice', 'alicepwd')
        start = date.today() + timedelta(days=2)
        end = date.today() + timedelta(days=4)  # 3 days
        self.client.post('/employee/apply-leave', data=dict(
            leave_type='Vacation Leave',
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d'),
            reason='Testing revoke logic'
        ))
        lr = LeaveRequest.query.filter_by(employee_id=self.emp1.employee_id).first()
        self.logout()

        # 2. Admin approves
        self.login('test_admin', 'adminpwd')
        self.client.post(f'/admin/leaves/approve/{lr.leave_id}')

        db.session.refresh(self.emp1)
        self.assertEqual(self.emp1.remaining_leaves, 17)

        # 3. Admin revokes (rejects the approved leave)
        response = self.client.post(f'/admin/leaves/reject/{lr.leave_id}', data=dict(
            admin_remarks='Revoking approval because of client issue'
        ), follow_redirects=True)

        db.session.refresh(lr)
        db.session.refresh(self.emp1)

        self.assertEqual(lr.status, 'Rejected')
        self.assertEqual(self.emp1.remaining_leaves, 20)  # Balance restored

    # ─── ROLE-BASED ACCESS CONTROL (RBAC) TESTS ─────────────────────────────
    def test_rbac_admin_routes_blocked_for_employee(self):
        """Verify employees cannot access admin panel endpoints."""
        self.login('test_alice', 'alicepwd')

        # Try to view admin dashboard
        response = self.client.get('/admin/dashboard', follow_redirects=True)
        self.assertIn(b'Access denied', response.data)
        self.assertNotIn(b'Admin Dashboard', response.data)

        # Try to list employees
        response = self.client.get('/admin/employees', follow_redirects=True)
        self.assertIn(b'Access denied', response.data)

    def test_rbac_employee_routes_blocked_for_admin(self):
        """Verify admin accounts cannot access employee panel endpoints."""
        self.login('test_admin', 'adminpwd')

        # Try to view employee dashboard
        response = self.client.get('/employee/dashboard', follow_redirects=True)
        self.assertIn(b'Access denied', response.data)

        # Try to apply for leave
        response = self.client.get('/employee/apply-leave', follow_redirects=True)
        self.assertIn(b'Access denied', response.data)

    def test_password_reset_token(self):
        """Verify token generation and verification logic."""
        user = User.query.filter_by(username='test_alice').first()
        token = user.get_reset_token()
        self.assertIsNotNone(token)

        verified_user = User.verify_reset_token(token)
        self.assertEqual(verified_user.user_id, user.user_id)

    def test_forgot_username_route(self):
        """Verify forgot username endpoint correctly displays recovered username."""
        # 1. GET page
        response = self.client.get('/forgot-username')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Recover Username', response.data)

        # 2. POST valid email
        response = self.client.post('/forgot-username', data={
            'email': 'alice@test.com'
        }, follow_redirects=True)
        self.assertIn(b'Recovery email simulated successfully', response.data)
        self.assertIn(b'test_alice', response.data)

        # 3. POST invalid email
        response = self.client.post('/forgot-username', data={
            'email': 'nonexistent@test.com'
        }, follow_redirects=True)
        self.assertIn(b'No account associated with that email was found', response.data)

    def test_forgot_password_and_reset_route(self):
        """Verify forgot password link generation and reset workflow."""
        # 1. POST valid email to request reset link
        response = self.client.post('/forgot-password', data={
            'email': 'alice@test.com'
        }, follow_redirects=True)
        self.assertIn(b'Password reset link generated successfully', response.data)
        self.assertIn(b'/reset-password/', response.data)

        # Extract token from response to simulate user clicking link
        user = User.query.filter_by(email='alice@test.com').first()
        token = user.get_reset_token()

        # 2. GET reset page with valid token
        response = self.client.get(f'/reset-password/{token}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Choose New Password', response.data)

        # 3. POST new password
        response = self.client.post(f'/reset-password/{token}', data={
            'password': 'newalicepwd',
            'confirm_pwd': 'newalicepwd'
        }, follow_redirects=True)
        self.assertIn(b'Your password has been reset successfully', response.data)

        # 4. Confirm new password works for login
        response = self.login('test_alice', 'newalicepwd')
        self.assertIn(b'Welcome back', response.data)

    def test_chat_system_flow(self):
        """Verify message creation, JSON history retrieval, and read state updates."""
        # Log in as test employee Alice
        self.login('test_alice', 'alicepwd')

        # 1. GET Chat Workspace index page
        response = self.client.get('/chat')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Workspace Chat', response.data)
        self.assertIn(b'Test_admin', response.data)  # Should list admin in directory

        # Get user records to map IDs
        alice = User.query.filter_by(username='test_alice').first()
        admin = User.query.filter_by(username='test_admin').first()

        # 2. POST Message to admin
        response = self.client.post('/chat/send', json={
            'recipient_id': admin.user_id,
            'content': 'Hello Admin! This is a test message.'
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['message']['content'], 'Hello Admin! This is a test message.')

        # Log out Alice, log in Admin
        self.client.get('/logout', follow_redirects=True)
        self.login('test_admin', 'adminpwd')

        # 3. Verify Admin has 1 unread message on index page
        response = self.client.get('/chat')
        self.assertEqual(response.status_code, 200)
        # Unread badge indicator for Alice's user id should contain '1' unread count
        self.assertIn(f'id="unread-{alice.user_id}"'.encode(), response.data)

        # 4. Fetch history between Admin and Alice (should mark message as read)
        response = self.client.get(f'/chat/history/{alice.user_id}')
        self.assertEqual(response.status_code, 200)
        history_data = response.get_json()
        self.assertEqual(history_data['status'], 'success')
        self.assertTrue(len(history_data['messages']) >= 1)
        self.assertEqual(history_data['messages'][0]['content'], 'Hello Admin! This is a test message.')

        # 5. Verify unread status has changed to True (read) in DB
        from models import Message
        msg = Message.query.get(data['message']['message_id'])
        self.assertTrue(msg.is_read)


if __name__ == '__main__':
    unittest.main()


