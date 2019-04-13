import os
import requests

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
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
	"""Render landing page."""

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
			result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", {"username": request.form.get("username").lower(), "hash": hash})
		except:
			flash("Username is taken. 😕")
			return redirect(url_for("register"))
		db.commit()

		# when register succeeds
		flash("Successfully registered! 👍 You can now sign in.")
		return redirect(url_for("login"))

	# when user reaches register via GET
	else:
		return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
	"""Sign in user."""

	if len(session) > 1:
		session.clear()

	if request.method == "POST":

		# query database
		user = db.execute("SELECT * FROM users WHERE username = :username", {"username" : request.form.get("username").lower()}).fetchone()

		# verify user-password from db
		if user is None or not pwd_context.verify(request.form.get("password"), user["hash"]):
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

@app.route("/search", methods=["GET"])
@login_required
def search():
	"""Search library for books."""

	# if user submits form
	if request.args.get("category") and request.args.get("q"):

		category = request.args.get("category")
		search = request.args.get("q")
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

@app.route("/book/<int:book_id>", methods=["GET", "POST"])
@login_required
def book(book_id):
	"""Show individual book pages."""
	
	# if user submits a review via the form
	if request.method == "POST":

		# get review details
		rating = request.form.get("star")
		comment = request.form.get("comment")
		user_id = session["user_id"]
		book_id = book_id

		# verify if user has made a review for this book already
		check = db.execute("SELECT * from reviews WHERE user_id = :user_id AND book_id = :book_id", {"user_id" : session["user_id"], "book_id" : book_id}).fetchone()
		if check:
			flash("Sorry. You have reviewed this book already. 💔")
			return redirect(url_for("book",book_id=book_id))

		# add review to database
		db.execute("INSERT INTO reviews (rating, review_text, user_id, book_id) VALUES (:rating, :review_text, :user_id, :book_id)", {"rating" : rating, "review_text" : comment, "user_id" : user_id, "book_id" : book_id})
		db.commit()

		flash("Awesome! Your review has been added. ❤️")
		return redirect(url_for("book",book_id=book_id))

	# user reaches route via GET
	else:

		# find book in library db
		book = db.execute("SELECT * FROM library WHERE id = :id", {"id" : book_id}).fetchone()
		if book is None or len(book) == 0:
			return redirect(url_for("search"))

		res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "***REMOVED***", "isbns": book.isbn})
		
		# Goodreads API data
		goodreads = res.json()['books'][0]
		avg_rating = goodreads['average_rating']
		rev_count = goodreads['work_ratings_count']


		# get plot & thumbnail from Google Books API
		googleAPI = requests.get("https://www.googleapis.com/books/v1/volumes?q="f'{book.title}'"").json()["items"][0]["volumeInfo"]
		plot = googleAPI["description"]
		thumbnail = googleAPI["imageLinks"]["thumbnail"]


		# get user reviews from db
		reviews = db.execute("SELECT username, date_posted, rating, review_text FROM reviews JOIN users ON users.id = reviews.user_id WHERE book_id = :book_id ORDER BY date_posted DESC", {"book_id" : book_id}).fetchall()

		return render_template("book.html", book=book, rating=avg_rating, count=rev_count, plot=plot, thumbnail=thumbnail, reviews=reviews)


@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("index"))


@app.route("/api/<isbn>")
@login_required
def api(isbn):
	"""Provide access to API."""


	# query database for book using isbn
	book = db.execute("SELECT * FROM library WHERE isbn = :isbn", {"isbn" : isbn}).fetchone()

	# return 404 eror if book can't be found in db
	if book is None:
		return jsonify({"error": "Invalid ISBN"}), 404

	# query Goodreads
	res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "***REMOVED***", "isbns": book.isbn})	
	goodreads = res.json()['books'][0]
	avg_rating = goodreads['average_rating']
	rev_count = goodreads['work_ratings_count']

	return jsonify({
		    "title": book.title,
		    "author": book.author,
		    "year": book.year,
		    "isbn": book.isbn,
		    "review_count": rev_count,
		    "average_score": avg_rating
		})