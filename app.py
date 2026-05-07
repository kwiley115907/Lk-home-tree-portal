from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from invoice_generator import generate_invoice_pdf
from models import db, User, ServiceRequest, Invoice, InvoiceItem


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@app.context_processor
def inject_year() -> dict[str, int]:
    return {"current_year": datetime.utcnow().year}


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return User.query.get(int(user_id))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))

        return "Invalid credentials", 401

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return "Email and password required", 400

        if User.query.filter_by(email=email).first():
            return "Email already registered", 400

        user = User(
            email=email,
            password=generate_password_hash(password),
            is_admin=False,
        )

        db.session.add(user)
        db.session.commit()
        login_user(user)

        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    if current_user.is_admin:
        requests = ServiceRequest.query.order_by(ServiceRequest.created_at.desc()).all()
        invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(5).all()
        return render_template(
            "admin_dashboard.html",
            requests=requests,
            invoices=invoices,
        )

    requests = ServiceRequest.query.filter_by(
        user_id=current_user.id
    ).order_by(ServiceRequest.created_at.desc()).all()

    return render_template("dashboard.html", requests=requests)


@app.route("/submit", methods=["POST"])
@login_required
def submit_request():
    description = request.form.get("description", "").strip()

    if not description:
        return "Description is required", 400

    service_request = ServiceRequest(
        description=description,
        user_id=current_user.id,
        status="Pending",
    )

    db.session.add(service_request)
    db.session.commit()

    return redirect(url_for("dashboard"))


@app.route("/status/<int:request_id>/<string:new_status>")
@login_required
def update_status(request_id: int, new_status: str):
    if not current_user.is_admin:
        return "Unauthorized", 403

    allowed_statuses = {"Pending", "In Progress", "Completed"}

    if new_status not in allowed_statuses:
        return "Invalid status", 400

    service_request = ServiceRequest.query.get_or_404(request_id)
    service_request.status = new_status
    db.session.commit()

    return redirect(url_for("dashboard"))


@app.route("/create-invoice", methods=["GET", "POST"])
@login_required
def create_invoice():
    if not current_user.is_admin:
        return "Unauthorized", 403

    if request.method == "POST":
        client_name = request.form.get("client_name", "").strip()
        client_email = request.form.get("client_email", "").strip().lower()
        tax_rate_raw = request.form.get("tax_rate", "0.07").strip()

        if not client_name:
            return "Client name required", 400

        try:
            tax_rate = float(tax_rate_raw)
        except ValueError:
            return "Invalid tax rate", 400

        year = datetime.now().year
        last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
        next_number = 1 if not last_invoice else last_invoice.id + 1
        invoice_number = f"INV-{year}-{next_number:04d}"

        invoice = Invoice(
            invoice_number=invoice_number,
            client_name=client_name,
            client_email=client_email,
            tax_rate=tax_rate,
        )

        db.session.add(invoice)
        db.session.commit()

        return redirect(url_for("edit_invoice", invoice_id=invoice.id))

    return render_template("create_invoice.html")


@app.route("/invoice/<int:invoice_id>", methods=["GET", "POST"])
@login_required
def edit_invoice(invoice_id: int):
    if not current_user.is_admin:
        return "Unauthorized", 403

    invoice = Invoice.query.get_or_404(invoice_id)

    if request.method == "POST":
        description = request.form.get("description", "").strip()

        try:
            quantity = float(request.form.get("quantity", ""))
            rate = float(request.form.get("rate", ""))
        except ValueError:
            return "Invalid quantity or rate", 400

        if not description or quantity <= 0 or rate <= 0:
            return "Description, quantity, and rate are required", 400

        item = InvoiceItem(
            description=description,
            quantity=quantity,
            rate=rate,
            invoice=invoice,
        )

        db.session.add(item)
        db.session.commit()

        return redirect(url_for("edit_invoice", invoice_id=invoice.id))

    return render_template("edit_invoice.html", invoice=invoice)


@app.route("/invoice/<int:invoice_id>/generate")
@login_required
def generate_invoice_pdf_route(invoice_id: int):
    if not current_user.is_admin:
        return "Unauthorized", 403

    invoice = Invoice.query.get_or_404(invoice_id)

    if not invoice.items:
        return "Add at least one item before generating PDF", 400

    filepath = generate_invoice_pdf(invoice)

    return send_file(filepath, as_attachment=True)


@app.route("/invoice/<int:invoice_id>/toggle-paid")
@login_required
def toggle_paid(invoice_id: int):
    if not current_user.is_admin:
        return "Unauthorized", 403

    invoice = Invoice.query.get_or_404(invoice_id)
    invoice.is_paid = not invoice.is_paid
    db.session.commit()

    return redirect(url_for("edit_invoice", invoice_id=invoice.id))


@app.route("/invoices")
@login_required
def invoice_list():
    if not current_user.is_admin:
        return "Unauthorized", 403

    invoices = Invoice.query.order_by(Invoice.created_at.desc()).all()
    return render_template("invoice_list.html", invoices=invoices)


@app.route("/item/<int:item_id>/delete")
@login_required
def delete_item(item_id: int):
    if not current_user.is_admin:
        return "Unauthorized", 403

    item = InvoiceItem.query.get_or_404(item_id)
    invoice_id = item.invoice_id

    db.session.delete(item)
    db.session.commit()

    return redirect(url_for("edit_invoice", invoice_id=invoice_id))


if __name__ == "__main__":
    app.run()

@app.route("/gallery")
def gallery():
    jobs = [
        {
            "title": "Palm Trim",
            "before": "gallery/before/job1.jpg",
            "after": "gallery/after/job1.jpg",
        },
        {
            "title": "Palm Trim",
            "before": "gallery/before/job2.jpg",
            "after": "gallery/after/job2.jpg",
        },
        {
            "title": "Palm Trim",
            "before": "gallery/before/job3.jpg",
            "after": "gallery/after/job3.jpg",
        },
    ]

    return render_template("gallery.html", jobs=jobs)
