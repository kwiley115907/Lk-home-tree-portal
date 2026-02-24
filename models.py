# models.py

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User account model."""

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class ServiceRequest(db.Model):
    """Customer service request model."""

    id = db.Column(db.Integer, primary_key=True)

    description = db.Column(db.Text, nullable=False)

    hours = db.Column(db.Float, nullable=False)
    rate = db.Column(db.Float, nullable=False)

    invoice_file = db.Column(db.String(200))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed = db.Column(db.Boolean, default=False)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )
