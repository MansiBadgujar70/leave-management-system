# 🚀 Deployment Guide: Deploying to GitHub and Render

This guide provides step-by-step instructions to deploy the **Leave Management System** to the cloud using **GitHub** and **Render**. 

By completing this guide, your application will be securely accessible over the internet from any device (mobile, tablet, desktop) on any network.

---

## 📋 Prerequisites
Before you start, make sure you have:
1. A [GitHub Account](https://github.com/) (free).
2. [Git Installed](https://git-scm.com/) on your local machine.
3. A [Render Account](https://render.com/) (free, signing in with GitHub is recommended).

---

## 🛠️ Step 1 — Prepare Your Local Repository

The codebase has already been configured with production-grade configurations, including:
- A `Procfile` telling Render how to start the app using Gunicorn.
- A `.gitignore` file that automatically excludes local databases and secrets (`.env`, `instance/`, `*.db`).
- Auto-fallback to SQLite when `DATABASE_URL` is absent, making it 100% plug-and-play.

1. Open your VS Code terminal and initialize Git (if not already initialized):
   ```bash
   git init
   ```

2. Stage all your project files:
   ```bash
   git add .
   ```

3. Commit the files locally:
   ```bash
   git commit -m "chore: prepare codebase for cloud deployment to Render"
   ```

---

## 🐙 Step 2 — Push the Code to GitHub

1. Go to [GitHub](https://github.com/) and click the **New** repository button.
2. Name your repository (e.g., `leave-management-system`).
3. Leave it as **Public** (or **Private** depending on your preference) and do **NOT** check any boxes like "Add a README" or "Add .gitignore" (we already have them!).
4. Click **Create repository**.
5. Copy the command list under *"…or push an existing repository from the command line"*. It will look like this:
   ```bash
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/leave-management-system.git
   git push -u origin main
   ```
6. Run those commands in your VS Code terminal to upload your project to GitHub.

---

## 🗄️ Step 3 — Create a PostgreSQL Database on Render

Render provides free PostgreSQL databases that integrate seamlessly with your web services.

1. Log in to your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** (top right) and select **PostgreSQL**.
3. Configure the database settings:
   - **Name**: `leave-management-db`
   - **Database Name**: `leave_management` (or leave default)
   - **User**: (leave default)
   - **Region**: Choose the region closest to you (e.g., Oregon, Frankfurt, Singapore)
   - **Instance Type**: Select **Free**
4. Click **Create Database**.
5. Wait 2-3 minutes for the database status to turn green/active.
6. Once active, scroll down to the **Connections** section and copy the **Internal Database URL** (e.g., `postgres://user:password@host/db`). 
   *Note: We will use this in the next step to connect our Flask app.*

---

## 🌐 Step 4 — Create a Web Service on Render

Now, we'll deploy the Flask web application and connect it to our database.

1. From the Render Dashboard, click **New +** and select **Web Service**.
2. Choose **Build and deploy from a Git repository**.
3. Under **Connect a repository**, select your newly created GitHub repository. If it's not shown, click *Connect window* to authorize Render to access your GitHub repositories.
4. Set the following details:
   - **Name**: `leave-management-system` (this will form your URL, e.g., `leave-management-system.onrender.com`)
   - **Region**: Choose the same region as your PostgreSQL database.
   - **Branch**: `main`
   - **Runtime**: `Python`
   - **Build Command**: 
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**: 
     ```bash
     gunicorn app:app
     ```
   - **Instance Type**: Select **Free**

---

## 🔒 Step 5 — Configure Environment Variables on Render

We must configure the database credentials and production settings securely on Render.

1. Under the web service configuration, click on the **Environment** tab.
2. Click **Add Environment Variable** and add the following keys:

| Key | Value | Purpose |
| :--- | :--- | :--- |
| `FLASK_ENV` | `production` | Enforces production configurations and secure cookies. |
| `SECRET_KEY` | *[Generate a random hex value]* | Signs session cookies securely. (Generate using: `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_URL` | *[Your PostgreSQL Internal Database URL]* | Directs SQLAlchemy to connect to your PostgreSQL instance instead of SQLite. |
| `PYTHON_VERSION` | `3.10.12` | Tells Render which Python runtime to install (recommending 3.10+). |

3. Click **Save Changes**.

---

## 🚀 Step 6 — Monitor and Access

1. Render will automatically trigger a new deployment. You can monitor the logs in the **Events** or **Logs** tab of your Web Service.
2. Render will download your code, install dependencies listed in `requirements.txt`, run the Gunicorn server, and automatically create the PostgreSQL tables and seed sample data.
3. Once the deployment finishes, the log will show `Gunicorn listening...` and the status will change to **Live** (green).
4. Click the URL generated at the top of the Render Dashboard (e.g., `https://leave-management-system.onrender.com`) to open your live application!

---

## 🛠️ Local Verification & Development

If you want to run the project locally after these configurations:
1. Make sure virtual environment is active: `venv\Scripts\activate` (on Windows).
2. Copy `.env.example` to `.env` and fill it out:
   ```env
   FLASK_ENV=development
   FLASK_DEBUG=True
   SECRET_KEY=local-dev-secret-key
   # DATABASE_URL can be omitted or commented out to use SQLite locally
   ```
3. Run the development server:
   ```bash
   python app.py
   ```
   The app will run at `http://127.0.0.1:5000` using your local SQLite database (`instance/leave_management.db`), ensuring you don't overwrite production cloud data.

---

## 🩺 Troubleshooting

### 1. Database Connection Errors
- **Symptom**: App crashes or redirects to the Custom Database Error page.
- **Fix**: Verify your `DATABASE_URL` env variable matches the Render PostgreSQL Internal Database URL. Ensure there are no typos, leading spaces, or wrong passwords.

### 2. Gunicorn Startup Fails
- **Symptom**: Logs show `gunicorn: command not found` or `ModuleNotFoundError`.
- **Fix**: Verify that `gunicorn` and `psycopg2-binary` are listed in `requirements.txt` and they were correctly pushed to GitHub.

### 3. Login Sessions Keep Expiring / "Secure Cookie" issues
- **Symptom**: User logs in but gets redirected to the login page immediately.
- **Fix**: Render serves applications over HTTPS by default, which is compatible with `SESSION_COOKIE_SECURE = True`. If you are testing locally using HTTPS or a custom subdomain, verify that `FLASK_ENV` is set to `development` or `production` appropriately.
