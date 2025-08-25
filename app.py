from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from models import db, User, Profile, Subscription, Message
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello Railway"



# Home page
@app.route("/")
def index():
    return render_template("index.html")

# Register
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        role = request.form.get("role", "user")  # default role user
        user = User(email=email, password=password, role=role)
        db.session.add(user)
        db.session.commit()
        flash("Account created! Please login.")
        return redirect(url_for("login"))
    return render_template("register.html")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            return redirect(url_for("dashboard"))
        flash("Invalid login.")
    return render_template("login.html")

# Dashboard
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    
    if user.role == "admin":
        return render_template("admin.html", user=user)  # match with your template
    return render_template("dashboard.html", user=user)  # match with your template

# Logout
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("You have been logged out.")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
