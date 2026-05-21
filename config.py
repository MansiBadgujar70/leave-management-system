"""
config.py - Application Configuration
=====================================
This file holds all configuration settings for the Flask application.
Modify database credentials here before running the app.
"""

import os
from dotenv import load_dotenv

# Load env variables from .env if present
load_dotenv()

class Config:
    """Base configuration class with all settings."""

    # ─── Secret Key ────────────────────────────────────────────────────────────
    # Used to sign session cookies. Change this to something random in production!
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'leave-mgmt-super-secret-key-2024'

    # ─── Database Settings ──────────────────────────────────────────────────────
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # Render/Heroku standard PostgreSQL URI correction
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        # Fallback to local SQLite file when no environment variable is provided
        base_dir = os.path.abspath(os.path.dirname(__file__))
        # Keep instance/ folder for SQLite database file
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(base_dir, 'instance', 'leave_management.db')}"

    # Disable modification tracking (saves memory)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ─── Leave Settings ─────────────────────────────────────────────────────────
    DEFAULT_TOTAL_LEAVES = 20    # Every new employee starts with 20 leaves/year

    # ─── Environment Settings ───────────────────────────────────────────────────
    FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    # ─── Session / Security Settings ───────────────────────────────────────────
    # Enforce secure cookies in production, but disable in development (local HTTP testing)
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() in ('true', '1', 't') if FLASK_ENV == 'production' else False
    REMEMBER_COOKIE_SECURE = os.environ.get('REMEMBER_COOKIE_SECURE', 'True').lower() in ('true', '1', 't') if FLASK_ENV == 'production' else False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

