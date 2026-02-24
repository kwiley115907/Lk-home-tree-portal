# app.py

from flask import Flask, render_template, redirect, url_for, request
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from flask import send_file

from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, ServiceRequest
from invoice_generator import generate_invoice
from datetime import datetime
from config import Config

@app.context_processor
def inject_year() -> dict[str, int]:
    """Inject current year into all templates."""
    return {"current_year": datetime.utcnow().year}

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return User.query.get(int(user_id))


@app.route("/")
@login_required
def dashboard():
    if current_user.is_admin:
        requests = ServiceRequest.query.all()
        return render_template("admin_dashboard.html", requests=requests)
    return render_template("dashboard.html", requests=requests)

@app.route("/submit", methods=["POST"])
@login_required
def submit_request():
    """Handle new service request submission."""

    description = request.form.get("description", "").strip()

    if not description:
        return "Description is required", 400

    try:
        hours = float(request.form.get("hours"))
        rate = float(request.form.get("rate"))
    except (TypeError, ValueError):
        return "Invalid hours or rate", 400

    new_request = ServiceRequest(
        description=description,
        hours=hours,
        rate=rate,
        user_id=current_user.id
    )

    db.session.add(new_request)
    db.session.commit()

    return redirect(url_for("dashboard"))
@app.route("/generate/<int:request_id>")
@login_required
def generate(request_id: int):
    if not current_user.is_admin:
        return "Unauthorized", 403

    service_request = ServiceRequest.query.get_or_404(request_id)
    filepath = generate_invoice(service_request)

    service_request.completed = True
    db.session.commit()

    return f"Invoice generated: {filepath}"

@app.route("/download/<int:request_id>")
@login_required
def download_invoice(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)

    if not service_request.invoice_file:
        return "Invoice not generated", 400

    return send_file(service_request.invoice_file, as_attachment=True)

if __name__ == "__main__":
    app.run()
