from functools import wraps

from flask import flash, redirect, session, url_for


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") != role or not session.get("user_id"):
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("auth.admin_login" if role == "admin" else "auth.employee_login"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


employee_required = role_required("employee")
admin_required = role_required("admin")
