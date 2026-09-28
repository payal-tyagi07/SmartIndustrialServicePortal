from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    email = "payaltyagi727@gmail.com"
    new_password = "admin123"

    user = db.session.scalar(db.select(User).where(User.email == email))
    if not user:
        print("User not found")
    else:
        if hasattr(user, "set_password"):
            user.set_password(new_password)
        else:
            user.password_hash = generate_password_hash(new_password)
        user.role = "admin"
        db.session.commit()
        print(f"Password reset for {user.email}")
        print(f"New password: {new_password}")
        print(f"Role: {user.role}")