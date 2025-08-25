import os
from flask import Flask, request, redirect, url_for, session, render_template, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecret")

# Database setup
_db_url = os.environ.get("DATABASE_URL", "sqlite:///matrimony.db")
# Render/Heroku often provide postgres://; SQLAlchemy prefers postgresql://
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(120))
    gender = db.Column(db.String(20))
    age = db.Column(db.Integer)
    bio = db.Column(db.Text)
    approved = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    reason = db.Column(db.String(200))

with app.app_context():
    db.create_all()
    # Create default admin if not exists
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@local")
    admin_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
    if not User.query.filter_by(email=admin_email).first():
        admin = User(
            email=admin_email,
            password_hash=generate_password_hash(admin_pass),
            name="Admin",
            is_admin=True,
            approved=True
        )
        db.session.add(admin)
        db.session.commit()

def current_user():
    if "user_id" in session:
        return User.query.get(session["user_id"])
    return None

@app.route("/")
def index():
    u = current_user()
    if u:
        return redirect(url_for("admin" if u.is_admin else "dashboard"))
    return render_template("index.html", title="Welcome")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        name = request.form.get("name","").strip()
        gender = request.form.get("gender","").strip()
        age = request.form.get("age","0").strip()
        bio = request.form.get("bio","").strip()
        if not email or not password:
            flash("Email and password are required.")
            return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return redirect(url_for("register"))
        try:
            age_val = int(age)
        except ValueError:
            age_val = None
        u = User(email=email, password_hash=generate_password_hash(password),
                 name=name, gender=gender, age=age_val, bio=bio)
        db.session.add(u)
        db.session.commit()
        flash("Registered! Please wait for admin approval.")
        return redirect(url_for("login"))
    return render_template("register.html", title="Register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        u = User.query.filter_by(email=email).first()
        if u and check_password_hash(u.password_hash, password):
            if not u.approved and not u.is_admin:
                flash("Your account is pending approval.")
                return redirect(url_for("login"))
            session["user_id"] = u.id
            return redirect(url_for("index"))
        flash("Invalid credentials.")
        return redirect(url_for("login"))
    return render_template("login.html", title="Login")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out.")
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    if u.is_admin:
        return redirect(url_for("admin"))
    profiles = User.query.filter(User.approved == True, User.id != u.id, User.is_admin == False).order_by(User.id.desc()).all()
    return render_template("dashboard.html", title="Dashboard", me=u, profiles=profiles)

@app.route("/report/<int:uid>", methods=["POST"])
def report(uid):
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    if not User.query.get(uid):
        flash("User not found.")
        return redirect(url_for("dashboard"))
    reason = request.form.get("reason","Flagged by user")
    r = Report(user_id=uid, reason=reason[:200])
    db.session.add(r)
    db.session.commit()
    flash("Reported user to admin.")
    return redirect(url_for("dashboard"))

@app.route("/admin")
def admin():
    u = current_user()
    if not u or not u.is_admin:
        return redirect(url_for("dashboard") if u else url_for("login"))
    pending = User.query.filter_by(approved=False, is_admin=False).all()
    reports = Report.query.order_by(Report.id.desc()).all()
    return render_template("admin.html", title="Admin", pending=pending, reports=reports)

@app.route("/approve/<int:uid>", methods=["POST"])
def approve(uid):
    u = current_user()
    if not u or not u.is_admin:
        return redirect(url_for("login"))
    p = User.query.get(uid)
    if p:
        p.approved = True
        db.session.commit()
        flash("Approved user.")
    return redirect(url_for("admin"))

# --- Minimal JSON APIs (for future mobile app) ---
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    email, password = (data.get("email","").lower(), data.get("password",""))
    u = User.query.filter_by(email=email).first()
    if u and check_password_hash(u.password_hash, password) and (u.is_admin or u.approved):
        return jsonify({"ok": True, "user": {"id": u.id, "name": u.name, "email": u.email}})
    return jsonify({"ok": False, "error": "Invalid credentials or not approved"}), 401

@app.route("/api/profiles")
def api_profiles():
    profiles = User.query.filter(User.approved == True, User.is_admin == False).all()
    return jsonify([{"id": p.id, "name": p.name, "age": p.age, "gender": p.gender, "bio": p.bio} for p in profiles])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
