from datetime import datetime
from dotenv import load_dotenv

from flask import Flask, render_template, request, redirect, url_for, send_file
import os
from flask_wtf.csrf import CSRFProtect
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
load_dotenv()

from models import db, User, ServiceRequest, Invoice, InvoiceItem, JobPhoto, Estimate, GalleryJob


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
csrf = CSRFProtect(app)

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




# =========================
# CUSTOMER INVOICE PORTAL
# =========================

@app.route("/my-invoices")
@login_required
def customer_invoices():
    invoices = Invoice.query.filter_by(
        client_email=current_user.email
    ).order_by(Invoice.created_at.desc()).all()

    return render_template("customer_invoices.html", invoices=invoices)


# =========================
# ADMIN ANALYTICS
# =========================

@app.route("/analytics")
@login_required
def analytics():
    if not current_user.is_admin:
        return "Unauthorized", 403

    invoices = Invoice.query.all()
    requests_count = ServiceRequest.query.count()
    estimates_count = Estimate.query.count()

    revenue = 0.0
    unpaid_total = 0.0

    for invoice in invoices:
        subtotal = sum(item.quantity * item.rate for item in invoice.items)
        total = subtotal + (subtotal * invoice.tax_rate)

        if invoice.is_paid:
            revenue += total
        else:
            unpaid_total += total

    return render_template(
        "analytics.html",
        invoices=invoices,
        requests_count=requests_count,
        estimates_count=estimates_count,
        revenue=revenue,
        unpaid_total=unpaid_total,
    )




# =========================
# ESTIMATES
# =========================

@app.route("/estimates")
@login_required
def estimate_list():
    if not current_user.is_admin:
        return "Unauthorized", 403

    estimates = Estimate.query.order_by(Estimate.created_at.desc()).all()
    return render_template("estimate_list.html", estimates=estimates)


@app.route("/estimate/create", methods=["GET", "POST"])
@login_required
def create_estimate():
    if not current_user.is_admin:
        return "Unauthorized", 403

    if request.method == "POST":
        estimate = Estimate(
            client_name=request.form.get("client_name", "").strip(),
            client_email=request.form.get("client_email", "").strip().lower(),
            client_phone=request.form.get("client_phone", "").strip(),
            description=request.form.get("description", "").strip(),
            estimated_total=float(request.form.get("estimated_total", "0")),
        )

        db.session.add(estimate)
        db.session.commit()

        return redirect(url_for("estimate_list"))

    return render_template("create_estimate.html")


@app.route("/estimate/<int:estimate_id>/convert")
@login_required
def convert_estimate(estimate_id: int):
    if not current_user.is_admin:
        return "Unauthorized", 403

    estimate = Estimate.query.get_or_404(estimate_id)

    year = datetime.now().year
    next_number = Invoice.query.count() + 1
    invoice_number = f"INV-{year}-{next_number:04d}"

    invoice = Invoice(
        invoice_number=invoice_number,
        client_name=estimate.client_name,
        client_email=estimate.client_email,
        client_phone=estimate.client_phone,
        tax_rate=0.07,
    )

    db.session.add(invoice)
    db.session.commit()

    item = InvoiceItem(
        description=estimate.description,
        quantity=1,
        rate=estimate.estimated_total,
        invoice=invoice,
    )

    estimate.accepted = True

    db.session.add(item)
    db.session.commit()

    return redirect(url_for("edit_invoice", invoice_id=invoice.id))


# =========================
# SMS NOTIFICATIONS
# =========================

def send_sms(to_number: str, message: str) -> None:
    from twilio.rest import Client

    client = Client(
        os.environ.get("TWILIO_ACCOUNT_SID"),
        os.environ.get("TWILIO_AUTH_TOKEN"),
    )

    client.messages.create(
        body=message,
        from_=os.environ.get("TWILIO_PHONE_NUMBER"),
        to=to_number,
    )


@app.route("/invoice/<int:invoice_id>/send-sms")
@login_required
def send_invoice_sms(invoice_id: int):
    if not current_user.is_admin:
        return "Unauthorized", 403

    invoice = Invoice.query.get_or_404(invoice_id)

    if not invoice.client_phone:
        return "No client phone number saved", 400

    send_sms(
        invoice.client_phone,
        f"Your invoice {invoice.invoice_number} from LK Home & Tree Co. is ready.",
    )

    return redirect(url_for("edit_invoice", invoice_id=invoice.id))


# =========================
# JOB SCHEDULING
# =========================

@app.route("/invoice/<int:invoice_id>/schedule", methods=["POST"])
@login_required
def schedule_invoice(invoice_id: int):
    if not current_user.is_admin:
        return "Unauthorized", 403

    invoice = Invoice.query.get_or_404(invoice_id)
    date_raw = request.form.get("scheduled_date")

    invoice.scheduled_date = datetime.fromisoformat(date_raw)
    db.session.commit()

    return redirect(url_for("edit_invoice", invoice_id=invoice.id))


# =========================
# DIGITAL SIGNATURES
# =========================

@app.route("/invoice/<int:invoice_id>/signature", methods=["GET", "POST"])
@login_required
def sign_invoice(invoice_id: int):
    import base64

    invoice = Invoice.query.get_or_404(invoice_id)

    if request.method == "POST":
        signature_data = request.form.get("signature_data", "")

        if "," not in signature_data:
            return "Invalid signature", 400

        header, encoded = signature_data.split(",", 1)

        os.makedirs("static/signatures", exist_ok=True)

        filename = f"signature_invoice_{invoice.id}.png"
        path = os.path.join("static/signatures", filename)

        with open(path, "wb") as file:
            file.write(base64.b64decode(encoded))

        invoice.signature_file = filename
        db.session.commit()

        return redirect(url_for("customer_invoices"))

    return render_template("signature.html", invoice=invoice)




@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")








@app.route("/invoice/<int:invoice_id>/payment-options")
@login_required
def payment_options(invoice_id: int):
    invoice = Invoice.query.get_or_404(invoice_id)

    if not current_user.is_admin and invoice.client_email != current_user.email:
        return "Unauthorized", 403

    subtotal = sum(item.quantity * item.rate for item in invoice.items)
    tax = subtotal * invoice.tax_rate
    total = subtotal + tax

    return render_template(
        "payment_options.html",
        invoice=invoice,
        subtotal=subtotal,
        tax=tax,
        total=total,
        cashapp_url=os.environ.get("CASHAPP_URL"),
        venmo_url=os.environ.get("VENMO_URL"),
        apple_pay_note=os.environ.get("APPLE_PAY_NOTE"),
    )




# =========================
# ADMIN GALLERY MANAGEMENT
# =========================

@app.route("/admin/gallery", methods=["GET", "POST"])
@login_required
def admin_gallery():
    from werkzeug.utils import secure_filename

    if not current_user.is_admin:
        return "Unauthorized", 403

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        before_file = request.files.get("before_image")
        after_file = request.files.get("after_image")

        if not title or not before_file or not after_file:
            return "Title, before image, and after image are required", 400

        allowed = {"jpg", "jpeg", "png", "webp"}

        def allowed_file(filename):
            return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed

        if not allowed_file(before_file.filename) or not allowed_file(after_file.filename):
            return "Only JPG, JPEG, PNG, or WEBP images allowed", 400

        os.makedirs("static/gallery/before", exist_ok=True)
        os.makedirs("static/gallery/after", exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        before_name = secure_filename(f"{timestamp}_before_{before_file.filename}")
        after_name = secure_filename(f"{timestamp}_after_{after_file.filename}")

        before_path = os.path.join("static/gallery/before", before_name)
        after_path = os.path.join("static/gallery/after", after_name)

        before_file.save(before_path)
        after_file.save(after_path)

        gallery_job = GalleryJob(
            title=title,
            before_image=f"gallery/before/{before_name}",
            after_image=f"gallery/after/{after_name}",
        )

        db.session.add(gallery_job)
        db.session.commit()

        return redirect(url_for("admin_gallery"))

    jobs = GalleryJob.query.order_by(GalleryJob.created_at.desc()).all()
    return render_template("admin_gallery.html", jobs=jobs)


@app.route("/admin/gallery/<int:job_id>/delete")
@login_required
def delete_gallery_job(job_id: int):
    if not current_user.is_admin:
        return "Unauthorized", 403

    job = GalleryJob.query.get_or_404(job_id)

    before_path = os.path.join("static", job.before_image)
    after_path = os.path.join("static", job.after_image)

    for image_path in [before_path, after_path]:
        if os.path.exists(image_path):
            os.remove(image_path)

    db.session.delete(job)
    db.session.commit()

    return redirect(url_for("admin_gallery"))


@app.route("/gallery")
def gallery():
    jobs = GalleryJob.query.order_by(GalleryJob.created_at.desc()).all()
    return render_template("gallery.html", jobs=jobs)


if __name__ == "__main__":
    app.run()

