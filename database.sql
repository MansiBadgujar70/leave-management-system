-- ════════════════════════════════════════════════════════════════════════════
-- database.sql — Leave Management System
-- MySQL Schema + Sample Data
-- ════════════════════════════════════════════════════════════════════════════
-- HOW TO USE:
--   1. Open phpMyAdmin (http://localhost/phpmyadmin)
--   2. Click "Import" tab
--   3. Choose this file and click "Go"
-- OR run in MySQL CLI:
--   mysql -u root -p < database.sql
-- ════════════════════════════════════════════════════════════════════════════

-- Create and select the database
CREATE DATABASE IF NOT EXISTS leave_management_system
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE leave_management_system;

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE 1: users
-- Stores login credentials and role for each system user
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id       INT          AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(80)  NOT NULL UNIQUE,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role          ENUM('admin', 'employee') NOT NULL DEFAULT 'employee',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_users_username (username),
    INDEX idx_users_email    (email),
    INDEX idx_users_role     (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE 2: employees
-- Extended profile for each employee user
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS employees (
    employee_id      INT         AUTO_INCREMENT PRIMARY KEY,
    user_id          INT         NOT NULL UNIQUE,
    full_name        VARCHAR(150) NOT NULL,
    department       VARCHAR(100) NOT NULL,
    phone_number     VARCHAR(20)  DEFAULT NULL,
    joining_date     DATE         NOT NULL,
    total_leaves     INT          NOT NULL DEFAULT 20,
    remaining_leaves INT          NOT NULL DEFAULT 20,
    CONSTRAINT fk_employee_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_emp_department (department),
    INDEX idx_emp_user_id    (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE 3: leave_requests
-- Each leave application submitted by an employee
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leave_requests (
    leave_id      INT  AUTO_INCREMENT PRIMARY KEY,
    employee_id   INT  NOT NULL,
    leave_type    ENUM('Sick Leave','Casual Leave','Emergency Leave','Vacation Leave') NOT NULL,
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL,
    total_days    INT  NOT NULL,
    reason        TEXT NOT NULL,
    status        ENUM('Pending','Approved','Rejected') NOT NULL DEFAULT 'Pending',
    admin_remarks TEXT DEFAULT NULL,
    applied_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_leave_employee
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_dates CHECK (end_date >= start_date),
    INDEX idx_leave_status      (status),
    INDEX idx_leave_employee_id (employee_id),
    INDEX idx_leave_dates       (start_date, end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ════════════════════════════════════════════════════════════════════════════
-- SAMPLE DATA
-- NOTE: The Flask app seeds data automatically on first run.
-- Only import this if you want raw SQL data without running the app first.
-- Passwords below use Werkzeug pbkdf2 hashes.
-- ════════════════════════════════════════════════════════════════════════════

-- Admin account (username: admin, password: admin123)
INSERT IGNORE INTO users (username, email, password_hash, role) VALUES
('admin', 'admin@leavesystem.com',
 'pbkdf2:sha256:600000$x5example$hashedvalue',   -- use app.py to seed real hash
 'admin');

-- ════════════════════════════════════════════════════════════════════════════
-- USEFUL QUERIES FOR VIVA / DEMONSTRATION
-- ════════════════════════════════════════════════════════════════════════════

-- 1. List all employees with their leave balances
-- SELECT e.full_name, e.department, e.remaining_leaves, e.total_leaves
-- FROM employees e JOIN users u ON e.user_id = u.user_id;

-- 2. All pending leave requests
-- SELECT lr.leave_id, e.full_name, lr.leave_type, lr.start_date, lr.end_date, lr.total_days
-- FROM leave_requests lr
-- JOIN employees e ON lr.employee_id = e.employee_id
-- WHERE lr.status = 'Pending';

-- 3. Count of leaves by status
-- SELECT status, COUNT(*) AS total FROM leave_requests GROUP BY status;

-- 4. Employees with less than 5 remaining leaves
-- SELECT full_name, department, remaining_leaves FROM employees WHERE remaining_leaves < 5;

-- 5. Total approved leave days per department
-- SELECT e.department, SUM(lr.total_days) AS total_approved_days
-- FROM leave_requests lr JOIN employees e ON lr.employee_id = e.employee_id
-- WHERE lr.status = 'Approved'
-- GROUP BY e.department ORDER BY total_approved_days DESC;
