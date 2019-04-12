from functools import wraps
from flask import session, request, redirect, url_for

def login_required(f):
	"""Flask function to require login for some routes"""

	@wraps(f)
	def decorated_function(*args, **kwargs):
		if session.get("user_id") is None:
			return redirect(url_for('index', next=None))
		return f(*args, **kwargs)
	return decorated_function