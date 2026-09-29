🏭 Smart Industrial Service Portal
A full-stack Flask + MySQL web application that digitizes industrial maintenance and service complaints. Employees raise service requests with AI-assisted descriptions and incident photos; administrators manage the entire lifecycle — assignment, status tracking, SLA monitoring, analytics, audit logs, and reporting — through a modern admin dashboard.

Live Demo: [Add your Render/Railway URL here]
Demo Admin: admin@example.com / admin123
Demo Employee: employee@example.com / employee123

📌 Problem Statement
Industrial facilities often rely on WhatsApp groups, phone calls, and paper forms to report electrical faults, IT issues, water leaks, equipment breakdowns, and safety hazards. This leads to:

Lost complaints and no audit trail

No priority triage — critical issues get buried

No visibility into response times or SLA compliance

Zero analytics on recurring issues or department performance

No accountability for who fixed what and when

Smart Industrial Service Portal replaces this chaos with a single, secure, role-based web platform that captures, tracks, escalates, and analyzes every service request end-to-end.

✨ Features
👷 Employee Portal
Secure registration & login with hashed passwords and rate limiting

Raise service request across 8 categories — IT Support, Electrical, Water Supply, Equipment Repair, Safety Issue, Housekeeping, Network Problem, Others

Priority selection (Low / Medium / High / Critical) with AI-suggested priority based on keywords

AI Draft Helper — generates a structured description from a short title

Incident file upload — JPG, PNG, PDF, DOCX with MIME + size validation

Smart duplicate detection — warns if a similar active complaint exists within 7 days

Save as draft and resume later

Complaint tracking with a live status timeline and comments

Feedback submission with 1–5 star rating and message

Profile management with secure password change

🛡️ Admin Portal
Operations dashboard with KPI cards: Total, Pending, Assigned, In Progress, Resolved, Critical

Ticket management — view, filter, assign, reassign, and change status

Technician management — add, edit, deactivate (records only, no separate login)

Status workflow enforcement — Pending → Assigned → In Progress → Resolved / Rejected

SLA tracking — Critical: 30 min, High: 2 hrs, Medium: 8 hrs, Low: 24 hrs

Advanced analytics — MTTR, SLA compliance %, technician performance ranking, department heatmap, monthly trends, critical hotspots

Interactive Chart.js visualizations — status, category, priority, department

Soft delete & restore — complaints are never truly deleted

Audit logs — every login, create, assign, status change, delete, restore, and feedback recorded

Employee list & feedback review with CSAT scoring

Filtered reports — by date, department, category, status, priority — with CSV export

🧰 Tech Stack
Layer	Technology
Backend	Python 3.12, Flask, Flask blueprints
Database	MySQL 8, SQLAlchemy ORM, Flask-Migrate (Alembic)
Frontend	Jinja2, HTML5, CSS3, JavaScript, Chart.js
Security	Werkzeug password hashing, Flask-WTF CSRF, Flask-Limiter, secure session cookies
AI / Intelligence	Rule-based priority suggestion, draft generation, duplicate detection
Email	SMTP (technician assignment, password reset)
Testing	pytest, pytest-cov, SQLite in-memory test DB
Deployment	Gunicorn, Render / Railway, environment variables
🏗️ Architecture
text
┌─────────────┐      HTTP       ┌──────────────────┐      ORM       ┌──────────┐
│  Browser    │ ─────────────►  │  Flask App       │ ─────────────► │  MySQL   │
│  (Employee  │                 │  - Blueprints    │                │  users   │
│   / Admin)  │ ◄─────────────  │  - Jinja2        │ ◄───────────── │ complaints│
└─────────────┘   HTML + JSON   │  - SQLAlchemy    │   Rows/Objects │ audit_logs│
                                │  - Services      │                └──────────┘
                                └──────────────────┘
                                        │
                                        ├── services/
                                        │   ├── ai_service.py
                                        │   ├── uploads.py
                                        │   ├── workflow_service.py
                                        │   ├── audit_service.py
                                        │   └── email_service.py
                                        │
                                        └── static/uploads/   (incident files)
🗄️ Entity Relationship Diagram
text
┌──────────┐        ┌──────────────┐        ┌───────────────┐
│  users   │───1:N──│  complaints  │───1:1──│  assignments  │
│          │        │              │        │               │
│ id (PK)  │        │ id (PK)      │        │ id (PK)       │
│ full_name│        │ employee_id  │        │ technician_id │
│ email    │        │ category_id  │        │ complaint_id  │
│ role     │        │ title        │        │ assigned_by   │
│ password │        │ priority     │        │ completed_at  │
│ hash     │        │ status       │        └───────────────┘
└──────────┘        │ is_deleted   │
     │              │ sla_due_at   │        ┌───────────────┐
     │              │ deleted_by   │───1:N──│  attachments  │
     │              └──────────────┘        └───────────────┘
     │                     │
     │                     ├───1:N──┐
     │                     │        │
     │              ┌──────────────┐│┌──────────────────┐
     │              │status_history│││assignment_history│
     │              └──────────────┘│└──────────────────┘
     │                              │
     ├───1:N──┐                     ├───1:N──┐
     │        │                     │        │
┌─────────┐ ┌──────────┐    ┌──────────────┐ ┌──────────┐
│feedback │ │audit_logs│    │ technicians  │ │categories│
└─────────┘ └──────────┘    └──────────────┘ └──────────┘
📂 Project Structure
text
SmartIndustrialServicePortal/
├── app/
│   ├── __init__.py               # App factory
│   ├── extensions.py             # db, migrate, csrf, limiter
│   ├── models.py                 # SQLAlchemy models
│   ├── decorators.py             # @employee_required, @admin_required
│   ├── auth/                     # Login, register, password reset, 2FA
│   ├── employee/                 # Employee blueprint
│   ├── admin/                    # Admin blueprint
│   ├── services/
│   │   ├── ai_service.py
│   │   ├── uploads.py
│   │   ├── workflow_service.py
│   │   ├── audit_service.py
│   │   └── email_service.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── admin_dashboard.html
│   │   ├── admin_analytics.html
│   │   ├── admin_complaints.html
│   │   ├── admin_audit_logs.html
│   │   ├── admin_reports.html
│   │   ├── raise_complaint.html
│   │   └── ...
│   └── static/
│       ├── css/style.css
│       ├── js/main.js
│       ├── js/priority_ai.js
│       └── uploads/              # Incident files
├── migrations/                   # Alembic migrations
├── tests/                        # pytest suite
├── run.py                        # Entry point
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
🚀 Getting Started
Prerequisites
Python 3.10+

MySQL 8+

pip and virtualenv

1. Clone the repository
bash
git clone https://github.com/your-username/smart-industrial-service-portal.git
cd smart-industrial-service-portal
2. Create a virtual environment
bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
3. Install dependencies
bash
pip install -r requirements.txt
4. Set up MySQL
Log in to MySQL as root and run:

sql
CREATE DATABASE smart_industrial_portal;
CREATE USER 'portal_user'@'localhost' IDENTIFIED BY 'YourStrongPassword';
GRANT ALL PRIVILEGES ON smart_industrial_portal.* TO 'portal_user'@'localhost';
FLUSH PRIVILEGES;
5. Configure environment variables
Copy .env.example to .env and fill in your values:

env
SECRET_KEY=generate-with-secrets-token-hex
DATABASE_URL=mysql+pymysql://portal_user:YourStrongPassword@localhost:3306/smart_industrial_portal
COOKIE_SECURE=false
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=mailer@example.com
MAIL_PASSWORD=your-smtp-password
MAIL_DEFAULT_SENDER=mailer@example.com
Generate a secure SECRET_KEY:

bash
python -c "import secrets; print(secrets.token_hex(32))"
6. Run migrations
bash
flask db upgrade
7. Start the app
bash
flask run
Open http://127.0.0.1:5000

🔑 Demo Credentials
Role	Email	Password
Admin	admin@example.com	admin123
Employee	employee@example.com	employee123
⚠️ Change these in production. Demo credentials are for evaluation only.

🧪 Running Tests
bash
pytest
With coverage:

bash
pytest --cov=app --cov-report=term-missing
Tests cover auth, RBAC, complaint creation, file validation, admin status workflow, and soft delete.

🔒 Security Practices
Password hashing with Werkzeug (generate_password_hash, check_password_hash)

CSRF protection on all POST forms via Flask-WTF

Rate limiting on login, register, and password reset (Flask-Limiter)

Role-based access control with custom decorators (@admin_required, @employee_required)

File upload validation — extension, MIME type, size, UUID-renamed storage

Environment variables for all secrets (.env — never committed)

Soft delete — historical data preserved, never hard-deleted

Audit logs — every critical action traceable to a user + timestamp

📊 Screenshots
Login	Employee Dashboard
https://docs/screenshots/login.png	https://docs/screenshots/employee_dashboard.png
Raise Complaint	Admin Dashboard
https://docs/screenshots/raise_complaint.png	https://docs/screenshots/admin_dashboard.png
Analytics	Audit Logs
https://docs/screenshots/admin_analytics.png	https://docs/screenshots/audit_logs.png
📈 Key Metrics
MTTR (Mean Time To Repair) — average resolution time per complaint

SLA Compliance % — percentage of tickets resolved within deadline

CSAT — average employee satisfaction rating

Department heatmap — status distribution across departments

Critical hotspots — locations with the most Critical complaints

🚢 Deployment
This project is deployable to Render, Railway, or Heroku with a MySQL add-on.

Quick deploy to Render:

Push to GitHub

Create a new Web Service → connect your repo

Build command: pip install -r requirements.txt

Start command: gunicorn run:app

Add environment variables (from .env.example)

Attach a MySQL database add-on

Run flask db upgrade from the shell

🔮 Future Scope
Real LLM integration (OpenAI/Gemini) for complaint drafting and auto-categorization

Real-time notifications with Flask-SocketIO

SMS / WhatsApp alerts via Twilio

Mobile-first PWA for floor workers

Multi-language support (English + Hindi)

Predictive maintenance analytics using historical complaint data

QR codes on industrial equipment — scan to pre-fill complaint forms

Admin 2FA via TOTP (partially built)

🤝 Contributing
This project was developed as part of a 45-day Web Development internship. Contributions, issues, and feature requests are welcome.

Fork the repository

Create a feature branch: git checkout -b feature/amazing-feature

Commit your changes: git commit -m "Add amazing feature"

Push: git push origin feature/amazing-feature

Open a Pull Request

🙏 Acknowledgements
Mentors and reviewers who guided the project

The Flask, SQLAlchemy, and Chart.js communities for excellent documentation

Everyone who tested and gave feedback during development

⭐ If you found this project useful, consider giving it a star on GitHub!
</｜｜DSML｜｜ parameter>
</｜｜DSML｜｜ invoke>
</｜｜DSML｜｜ calls>
