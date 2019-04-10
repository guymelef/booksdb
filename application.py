import os

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from functions import *

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
	"""Sign in user."""

	if request.method == "POST":

		# query database
		user = db.execute("SELECT * FROM users WHERE username = :username", {"username" : request.form.get("username")}).fetchone()

		# verify user-password from db
		if len(user) == 0 or not pwd_context.verify(request.form.get("password"), user["hash"]):
			flash("Invalid username and/or password. ☹️")
			return redirect(url_for("login"))

		# remember which user is logged in
		session["user_id"] = user["id"]
		session["user"] = user["username"]

		# redirect to search page
		return redirect(url_for("search"))

	# when user reaches login via GET
	else:	
		return render_template("login.html")

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
	"""Search library for books."""
	
	# if user submits form
	if request.method == "POST":

		category = request.form.get("category")
		search = request.form.get("search")
		rough_search = f'%{search}%'

		#query database
		books = db.execute("SELECT * FROM library WHERE "f'{category}'" ILIKE :rough_search ORDER BY author ASC", {"rough_search" : rough_search}).fetchall()

		# if search returns empty
		if len(books) == 0:
			flash("My magnifying glass broke but still couldn't find anything. 🤔")
			return redirect(url_for("search"))

		# return books to search page
		return render_template("search.html", books = books, number = len(books))

	# if user reaches page via GET	
	else:
		return render_template("search.html")

@app.route("/book/<int:book_id>")
def book(book_id):

	# query database
	book = db.execute("SELECT * FROM library WHERE id = :id", {"id" : book_id}).fetchone()
	if len(book) == 0:
		return redirect(url_for("search"))

	return render_template("book.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("index"))