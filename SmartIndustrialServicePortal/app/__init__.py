from pathlib import Path

from flask import Flask
from dotenv import load_dotenv

from app.extensions import csrf, db, limiter, mail, migrate


def create_app(config_object=None):
    """Application factory. Only employee and admin blueprints authenticate users."""
    load_dotenv()
    application = Flask(__name__, template_folder="../templates", static_folder="../static")
    application.config.from_object(config_object or "config.Config")
    Path(application.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(application)
    migrate.init_app(application, db)
    csrf.init_app(application)
    limiter.init_app(application)
    mail.init_app(application)
    @application.template_filter("sla_countdown")
    def sla_countdown(due_at):
        from app.services.workflow_service import countdown_text
        return countdown_text(due_at)

    from app.auth.routes import auth_bp
    from app.employee.routes import employee_bp
    from app.admin.routes import admin_bp

    application.register_blueprint(auth_bp)
    application.register_blueprint(employee_bp)
    application.register_blueprint(admin_bp, url_prefix="/admin")
    return application
