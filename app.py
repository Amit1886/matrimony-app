import os
from flask import Flask, request, redirect, url_for, session, render_template_string, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecret")

# Database setup
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///matrimony.db")
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

# Layout template
layout = """
<!doctype html>
<title>Matrimony</title>
<h1>{{ title }}</h1>
{% with messages = get_flashed_messages() %}
  {% if messages %}<ul>{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>{% endif %}
{% endwith %}
{{ body|safe }}
"""

@app.route("/")
def index():
    if "user_id" in session:
        u = User.query.get(session["user_id"])
        if u.is_admin:
            return redirect(url_for("admin"))
        else:
            return redirect(url_for("dashboard"))
    return render_template_string(layout, title="Welcome",
        body='<a href="/register">Register</a> | <a href="/login">Login</a>')

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        name = request.form["name"]
        gender = request.form["gender"]
        age = int(request.form["age"])
        bio = request.form["bio"]
        if User.query.filter_by(email=email).first():
            flash("Email already registered")
        else:
            u = User(email=email, password_hash=password,
                     name=name, gender=gender, age=age, bio=bio)
            db.session.add(u)
            db.session.commit()
            flash("Registered! Wait for admin approval.")
            return redirect(url_for("login"))
    body = """<form method='post'>
    Email: <input name='email'><br>
    Password: <input type='password' name='password'><br>
    Name: <input name='name'><br>
    Gender: <input name='gender'><br>
    Age: <input name='age'><br>
    Bio: <textarea name='bio'></textarea><br>
    <button type='submit'>Register</button>
    </form>"""
    return render_template_string(layout, title="Register", body=body)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        u = User.query.filter_by(email=email).first()
        if u and check_password_hash(u.password_hash, password):
            if not u.approved and not u.is_admin:
                flash("Wait for admin approval")
                return redirect(url_for("login"))
            session["user_id"] = u.id
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials")
    body = """<form method='post'>
    Email: <input name='email'><br>
    Password: <input type='password' name='password'><br>
    <button type='submit'>Login</button>
    </form>"""
    return render_template_string(layout, title="Login", body=body)

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session: return redirect(url_for("login"))
    u = User.query.get(session["user_id"])
    if u.is_admin: return redirect(url_for("admin"))
    profiles = User.query.filter(User.approved==True, User.id!=u.id).all()
    body = "<h3>Approved Profiles:</h3><ul>" + "".join([
        f"<li>{p.name}, {p.age}, {p.gender} - {p.bio[:30]}... "
        f"<a href='/report/{p.id}'>Report</a></li>" for p in profiles
    ]) + "</ul>"
    body += '<br><a href="/logout">Logout</a>'
    return render_template_string(layout, title="Dashboard", body=body)

@app.route("/report/<int:uid>")
def report(uid):
    if "user_id" not in session: return redirect(url_for("login"))
    r = Report(user_id=uid, reason="Flagged by user")
    db.session.add(r)
    db.session.commit()
    flash("Reported user to admin")
    return redirect(url_for("dashboard"))

@app.route("/admin")
def admin():
    if "user_id" not in session: return redirect(url_for("login"))
    u = User.query.get(session["user_id"])
    if not u.is_admin: return redirect(url_for("dashboard"))
    pending = User.query.filter_by(approved=False, is_admin=False).all()
    reports = Report.query.all()
    body = "<h3>Pending Approvals:</h3><ul>" + "".join([
        f"<li>{p.name} ({p.email}) <a href='/approve/{p.id}'>Approve</a></li>" for p in pending
    ]) + "</ul>"
    body += "<h3>Reports:</h3><ul>" + "".join([
        f"<li>User {r.user_id} Reason: {r.reason}</li>" for r in reports
    ]) + "</ul>"
    body += '<br><a href="/logout">Logout</a>'
    return render_template_string(layout, title="Admin Dashboard", body=body)

@app.route("/approve/<int:uid>")
def approve(uid):
    if "user_id" not in session: return redirect(url_for("login"))
    u = User.query.get(session["user_id"])
    if not u.is_admin: return redirect(url_for("dashboard"))
    p = User.query.get(uid)
    if p:
        p.approved = True
        db.session.commit()
        flash("Approved user")
    return redirect(url_for("admin"))

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
