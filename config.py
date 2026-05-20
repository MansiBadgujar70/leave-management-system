"""
config.py - Application Configuration
=====================================
This file holds all configuration settings for the Flask application.
Modify database credentials here before running the app.
"""

import os

class Config:
    """Base configuration class with all settings."""

    # ─── Secret Key ────────────────────────────────────────────────────────────
    # Used to sign session cookies. Change this to something random in production!
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'leave-mgmt-super-secret-key-2024'

    # ─── Database Settings ──────────────────────────────────────────────────────
    # XAMPP MySQL default settings:
    #   Host     : localhost
    #   Port     : 3306
    #   Username : root
    #   Password : (empty by default in XAMPP)
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = ''          # Change this if you set a MySQL root password
    MYSQL_DB = 'leave_management_system'

    # SQLAlchemy database URI  (mysql+pymysql://user:password@host/dbname)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    # Disable modification tracking (saves memory)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ─── Leave Settings ─────────────────────────────────────────────────────────
    DEFAULT_TOTAL_LEAVES = 20    # Every new employee starts with 20 leaves/year
