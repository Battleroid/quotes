# quotes

Quotes was a basic web application that allowed users to pay-to-post images as a way of accepting donations. Worked but lack of interest from users kept it from continuing.

# config

You need to have sqlite3, Python 2.7, and `python-sqlite` installed. uWSGI and Supervisor are completely optional, but useful.

You will also to use pip (or pip with virtualenv) to install the requirements: `pip install postmarkup stripe flask-wtf flask wtforms`

1. Create the database using sqlite3 (ex: `sqlite3 quotes.db < quotes.sqlite3`).
2. In `config.py` enter your Stripe API key and the name of the database.
3. Replace the public Stripe API key in the `buy.html` template (`data-key`).

Then run it. That's it. My old supervisor configuration file is included for the hell of it.

# (working) example

![example video](quotes.webm)
