import os

from app import app
from models import db, User
from werkzeug.security import generate_password_hash

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

with app.app_context():
    existing = User.query.filter_by(email=ADMIN_EMAIL).first()

    if not existing:
        admin = User(
            email=ADMIN_EMAIL,
            password=generate_password_hash(ADMIN_PASSWORD),
            is_admin=True,
        )

        db.session.add(admin)
        db.session.commit()

        print("Admin created.")
    else:
        print("Admin already exists.")
