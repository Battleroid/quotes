from flask import Flask, request, g, url_for, redirect, abort, render_template, flash, jsonify
from wtforms import StringField, validators, ValidationError
from postmarkup import render_bbcode, strip_bbcode
import stripe, datetime, re
from flask_wtf import Form
import sqlite3 as sql

# Flask

app = Flask(__name__)
app.config.from_pyfile('config.py')

# Stripe

stripe.api_key = app.config['STRIPE_API_KEY']

# Jinja2

@app.template_filter('datetimefmt')
def datetimefmt(date):
	return date.strftime('%Y-%m-%d')

# SQLite

def connect_db():
	return sql.connect(app.config['DATABASE'], detect_types=sql.PARSE_DECLTYPES)

def grab_db():
	db = getattr(g, '_database', None)
	if db is None:
		db = g._database = connect_db()
	return db

@app.teardown_appcontext
def close_db(exception):
	db = getattr(g, '_database', None)
	if db is not None:
		db.close()

def query_db(query, args=(), one=False):
	cur = grab_db().execute(query, args)
	rv = cur.fetchall()
	cur.close()
	return (rv[0] if rv else None) if one else rv

def insert_db(query, args=()):
	cur = grab_db()
	cur.execute(query, args)
	cur.commit()
	cur.close()

def dict_query(query, args=()):
	def _query(cursor, row):
		d = {}
		for id, col, in enumerate(cur.description):
			d[col[0]] = row[id]
		return d
	con = grab_db()
	con.row_factory = _query
	cur = con.cursor()
	cur.execute(query, args)
	return cur.fetchall()

# Forms

def render_quote(input, strip=False):
	patterns = {
			'&[rl]dquo;': '"',
			'&lt;': '<',
			'&gt;': '>'
			}
	if strip:
		input = strip_bbcode(spoiler(input, True))
		for pat, repl in patterns.items():
			input = re.sub(pat, '', input)
	else:
		input = render_bbcode(spoiler(input))
		for pat, repl in patterns.items():
			input = re.sub(pat, repl, input)
	return input.strip()

def spoiler(input, strip=False):
	if not strip:
		return re.sub(r'\[spoiler\](.*?)\[\/spoiler\]', r'<span class="spoiler">\1</span>', input)
	else:
		return re.sub(r'\[spoiler\](.*?)\[\/spoiler\]', r'\1', input)

def real_length(form, field):
	stripped = render_quote(field.data, True)
	if len(stripped) > 140 or len(stripped) < 1:
		raise ValidationError('Quote is not a valid length (%s characters).' % len(stripped))

def original_quote(form, field):
	result = query_db('SELECT 1 WHERE EXISTS(SELECT 1 FROM quotes WHERE quote = ?)', (render_quote(field.data, True), ), True)
	if result is not None:
		raise ValidationError('Quote exists, come up with something original.')

class QuoteForm(Form):
	quote = StringField('Quote', validators=[original_quote, real_length, validators.InputRequired(), validators.Required()])
	author = StringField('Name', description={'placeholder': 'Anonymous'}, validators=[validators.length(max=32), validators.Optional()])

class PreviewForm(Form):
	quote = StringField('Quote', validators=[validators.length(min=1), original_quote, real_length])
	author = StringField('Name (blank is <strong>Anonymous</strong>)', validators=[validators.length(max=32), validators.Optional()])

# Routing & Purchasing

@app.route('/buy', methods=['GET', 'POST'])
def buy():
	form = QuoteForm(request.form)
	if request.method == 'POST' and form.validate():
		stripe_token = request.form['stripeToken']
		try:
			quote = render_quote(form.quote.data.strip())
			author = form.author.data.strip()
			if not author:
				author = 'Anonymous'
			created = datetime.datetime.now()
			stripe_charge = stripe.Charge.create(
					amount=100,
					currency='usd',
					card=stripe_token,
					description='Quote'
			)
			insert_db('INSERT INTO quotes (quote, author, created) VALUES (?, ?, ?)', (quote, author, created, ))
			flash('Your quote has been added!')
		except (stripe.InvalidRequestError, stripe.AuthenticationError, stripe.APIConnectionError, stripe.CardError), e:
			flash('There was a problem charging your card.')
			return redirect(url_for('buy'))
		except (sql.IntegrityError, ValidationError), e:
			flash('That quote already exists, come up with something original.')
			return redirect(url_for('buy'))
	return render_template('buy.html', form=form)

@app.route('/quote')
def quote():
	random = dict_query('SELECT id, quote, author, created FROM quotes ORDER BY RANDOM() LIMIT 1')
	if not random:
		result = {'id': -1, 'quote': 'No quotes! Someone should buy one.', 'author': 'Anonymous', 'created': 'just now'}
		return jsonify(result)
	else:
		return jsonify(random[0])

@app.route('/preview', methods=['GET', 'POST'])
def preview():
	form = PreviewForm(request.form)
	if request.method == 'POST' and form.validate():
		quote = render_quote(form.quote.data.strip())
		author = form.author.data.strip()
		if not author:
			author = 'Anonymous'
		preview = {'quote': quote, 'author': author, 'now': datetime.datetime.now()}
		flash('Preview updated.')
		return render_template('preview.html', form=form, preview=preview)
	return render_template('preview.html', form=form)

@app.route('/view/id/<id>')
def view_id(id):
	quote = dict_query('SELECT id, quote, author, created FROM quotes WHERE id = ?', (id, ))
	return render_template('viewid.html', quotes=quote, number=id)

@app.route('/view/user/<username>', methods=['GET', 'POST'])
def view_by(username):
	quotes = dict_query('SELECT id, quote, author, created FROM quotes WHERE author = ?', (username, ))
	return render_template('viewby.html', author=username, quotes=quotes, total=len(quotes))

@app.route('/')
def view():
	quotes = dict_query('SELECT id, quote, author, created FROM quotes')
	unique = dict_query('SELECT COUNT(DISTINCT author) FROM quotes')
	return render_template('view.html', quotes=quotes, total=len(quotes), unique=unique[0])

@app.route('/api')
def api():
	return render_template('api.html')

if __name__ == '__main__':
	app.run(host=app.config['HOST'],port=app.config['PORT'])
