import os

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
	"""Render the landing page."""

	return render_template("index.html")

@app.route("/register",  methods=["GET", "POST"])
def register():
	"""Register user."""

	# when user signs up using the form
	if request.method == "POST":

		# ensure passwords match
		if request.form.get("password") != request.form.get("password_check"):
			flash("Passwords do not match. 😕")
			return redirect(url_for("register"))

		# hash user password
		hash = pwd_context.hash(request.form.get("password"))

		# add user to db & check if unique
		try:
			result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", {"username": request.form.get("username"), "hash": hash})
		except:
			flash("Username is taken. 😕")
			return redirect(url_for("register"))
		db.commit()

		# when register succeeds
		flash("Successfully registered! You can now sign in.")
		return redirect(url_for("login"))

	# when user reaches register via GET
	else:
		return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
	return render_template("login.html")

@app.route("/search")
def search():
	return render_template("search.html")

@app.route("/book")
def book():
	return render_template("book.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))