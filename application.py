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

		# query db for book reviewed by user
		# add it to session["reviewed"] for easy access
		reviewed = db.execute("SELECT library.id, library.title, library.year FROM reviews JOIN library ON library.id = reviews.book_id WHERE user_id = :id ORDER BY date_posted DESC", {"id" : session["user_id"]}).fetchall()

		if len(reviewed) == 0:
			pass
		else:
			for book in reviewed:
				session.setdefault("reviews",[]).append((book.id, book.title, book.year))

		# redirect to search page
		return redirect(url_for("search"))

	# when user reaches login via GET
	else:	
		return render_template("login.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
	"""Visit user profile page."""

	# when user submits form to change password
	if request.method == "POST":

		# query database
		user = db.execute("SELECT * FROM users WHERE username = :username", {"username" : session["user"]}).fetchone()

		# verify user-password from db
		if not pwd_context.verify(request.form.get("oldPass"), user["hash"]) or request.form.get("newPass") != request.form.get("checkPass"):
			flash("❌ Mismatch found. Please fill up the form correctly.")
			return redirect(url_for("search"))

		# hash user password
		hash = pwd_context.hash(request.form.get("newPass"))

		# change old password
		db.execute("UPDATE users SET hash = :hash WHERE username = :username", {"hash" : hash, "username" : session["user"]})
		db.commit()

		flash("✅ Password successfully updated!")
		return redirect(url_for("search"))

	else:
		return redirect(url_for("search"))


@app.route("/search", methods=["GET", "POST"])
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


	# find book in library db
	book = db.execute("SELECT * FROM library WHERE id = :id", {"id" : book_id}).fetchone()

	# if user submits a review via the form
	if request.method == "POST":

		# get review details
		rating = request.form.get("star")
		comment = request.form.get("comment")

		# verify if user has made a review for this book already
		check = db.execute("SELECT * from reviews WHERE user_id = :user_id AND book_id = :book_id", {"user_id" : session["user_id"], "book_id" : book_id}).fetchone()
		if check:
			flash("Sorry. You have reviewed this book already. 💔")
			return redirect(url_for("book",book_id=book_id))

		# add review to database
		db.execute("INSERT INTO reviews (rating, review_text, user_id, book_id) VALUES (:rating, :review_text, :user_id, :book_id)", {"rating" : rating, "review_text" : comment, "user_id" : session["user_id"], "book_id" : book_id})
		db.commit()

		# add book to session["reviewed"]
		book = (book_id, book.title, book.year)
		session.setdefault("reviews",[]).append(book)

		flash("Awesome! Your review has been added. ❤️")
		return redirect(url_for("book", book_id=book_id))

	# user reaches route via GET
	else:

		if book is None or len(book) == 0:
			return redirect(url_for("search"))

		# get Goodreads data
		res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "***REMOVED***", "isbns": book.isbn})
		
		# Goodreads API data
		goodreads = res.json()['books'][0]
		avg_rating = goodreads['average_rating']
		rev_count = goodreads['work_ratings_count']

		# get plot & thumbnail from Google Books API
		googleAPI = requests.get("https://www.googleapis.com/books/v1/volumes?q="f'{book.isbn}'"").json()["items"][0]["volumeInfo"]
		plot = googleAPI["description"]
		
		thumbnail = "http://covers.openlibrary.org/b/isbn/"f'{book.isbn}'"-L.jpg"

		# get user reviews from db
		reviews = db.execute("SELECT username, date_posted, rating, review_text FROM reviews JOIN users ON users.id = reviews.user_id WHERE book_id = :book_id ORDER BY date_posted DESC", {"book_id" : book_id}).fetchall()

		# track user browsing history
		if session.get("history") is None:
			session.setdefault("history",[]).append({book.title : book.id})
		elif {book.title : book.id} in session["history"]:
			print("Book is already in browsing history.")
		else:
			session.setdefault("history",[]).append({book.title : book.id})
		
		return render_template("book.html", book=book, rating=avg_rating, count=rev_count, plot=plot, thumbnail=thumbnail, reviews=reviews)


@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("index"))


@app.route("/api/<isbn>")
def api(isbn):
	"""Provide access to API."""

	# query database for book using isbn
	book = db.execute("SELECT * FROM library WHERE isbn = :isbn", {"isbn" : isbn}).fetchone()

	# return 404 eror if book can't be found in db
	if book is None:
		return jsonify({"error": "Invalid ISBN"}), 404

	# query db for review count and rating
	booksdb = db.execute("SELECT COUNT(*), ROUND(AVG(rating),2) FROM reviews WHERE book_id = :book_id", {"book_id" : book.id}).fetchone()
	
	return jsonify({
		    "title": book.title,
		    "author": book.author,
		    "year": book.year,
		    "isbn": book.isbn,
		    "review_count": f'{booksdb[0]}',
		    "average_score": "0" if booksdb[1] is None else f'{booksdb[1]}'
		})