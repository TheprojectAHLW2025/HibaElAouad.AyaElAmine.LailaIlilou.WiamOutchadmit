import os
import random
import json
from datetime import datetime, timedelta
import string
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from models import db, User, TempUser ,TempDeleteUser

app = Flask(__name__)
app.secret_key = 'thepowerpuffGIRLS_2025'

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fraudeapp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)

# Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'theproject.aalw.2025@gmail.com'
app.config['MAIL_PASSWORD'] = 'iucl lcvj kfzc ymjs'
mail = Mail(app)

# Create upload folder if missing
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Load locations once
with open('locations.json', 'r', encoding='utf-8') as f:
    locations = json.load(f)

# Create tables if not exist (optional)
with app.app_context():
    db.create_all()

# -------------- ROUTES --------------

@app.route('/')
def root():
    if 'email' in session:
        return render_template('index.html')
    return render_template('welcome.html')

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form['email'].lower()
        username = request.form['username']

        # Check if email already exists
        if User.query.get(email):
            countries = sorted([(code, data["country"]) for code, data in locations.items()], key=lambda x: x[1])
            return render_template("register.html", error="Email already in use", countries=countries)

        # Check if username already exists
        if User.query.filter_by(username=username).first():
            countries = sorted([(code, data["country"]) for code, data in locations.items()], key=lambda x: x[1])
            return render_template("register.html", error="Username already taken", countries=countries)

        code = str(random.randint(100000, 999999))
        temp = TempUser(email=email, code=code)
        db.session.merge(temp)
        db.session.commit()

        msg = Message("Verification code",
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[email])
        msg.body = f"Your verification code is: {code}"
        mail.send(msg)

        session['pending_email'] = email
        session['form_data'] = request.form.to_dict()
        return redirect(url_for("verify"))

    countries = sorted([(code, data["country"]) for code, data in locations.items()], key=lambda x: x[1])
    return render_template("register.html", countries=countries)

@app.route('/get_cities/<country_code>')
def get_cities(country_code):
    country = locations.get(country_code.upper())
    if country:
        return jsonify(country["cities"])
    return jsonify([])

last_code_sent = {}

@app.route('/resend_code', methods=['POST'])
def resend_code():
    email = session.get('pending_email')
    if not email:
        return jsonify({"error": "No email in session"}), 400

    now = datetime.now()
    if email in last_code_sent and (now - last_code_sent[email]) < timedelta(seconds=60):
        return jsonify({"error": "Wait before resending the code"}), 429

    temp = TempUser.query.get(email)
    if not temp:
        return jsonify({"error": "No temp data for this email"}), 400

    new_code = str(random.randint(100000, 999999))
    temp.code = new_code
    db.session.commit()

    msg = Message("Verification code - resend",
                  sender=app.config['MAIL_USERNAME'],
                  recipients=[email])
    msg.body = f"Your new verification code is: {new_code}"
    mail.send(msg)

    last_code_sent[email] = now
    return jsonify({"message": "Verification code resent successfully"})

@app.route("/verify", methods=["GET", "POST"])
def verify():
    email = session.get("pending_email")
    if not email:
        return redirect(url_for("register"))

    temp = TempUser.query.get(email)
    if not temp:
        return redirect(url_for("register"))

    if request.method == "POST":
        if request.form["code"] == temp.code:
            form = session.get("form_data")
            if not form:
                return redirect(url_for("register"))

            user = User(
                email=email,
                fullname=form["fullname"],
                username=form["username"],
                phone=form["phone"],
                country=form["country"],
                city=form["city"],
                business=form["business"]
            )
            user.set_password(form["password"])
            db.session.add(user)
            db.session.delete(temp)
            db.session.commit()

            session.pop("pending_email", None)
            session.pop("form_data", None)
            session['email'] = user.email
            session['username'] = user.username
            return redirect(url_for("home"))

        else:
            return render_template("verify.html", error="Code incorrect")
    return render_template("verify.html")

#------------------login----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']
        user = User.query.get(email)
        if user and user.check_password(password):
            session['email'] = user.email
            session['username'] = user.username
            return redirect(url_for('home'))
        else:
            error = "Invalid email or password"
    return render_template('login.html', error=error)

#------------------logout ----------------
@app.route('/logout')
def logout():
    session.pop('email', None)
    session.pop('username', None)
    return render_template('welcome.html')


#------------------home----------------
@app.route('/home')
def home():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

#------------------profile----------------
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['email'])

    # Load countries list (like sign-up)
    with open('locations.json', encoding='utf-8') as f:
        location_data = json.load(f)
    countries = sorted([(code, data["country"]) for code, data in location_data.items()], key=lambda x: x[1])

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            # Update user info
            user.fullname = request.form.get('fullname')
            user.username = request.form.get('username')
            user.phone = request.form.get('phone')
            user.country = request.form.get('country')
            user.city = request.form.get('city')
            user.business = request.form.get('business')

            file = request.files.get('profile_picture')
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{user.email}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                user.profile_picture = filename

            db.session.commit()
            return redirect(url_for('profile'))

        elif action == 'request_delete':
            # User submitted email and password to request deletion code
            email = request.form.get('delete_email').lower()
            password = request.form.get('delete_password')

            if email != user.email:
                error_delete = "Email does not match your logged-in email."
                return render_template('profile.html', user=user, countries=countries, error_delete=error_delete)

            if not user.check_password(password):
                error_delete = "Incorrect password."
                return render_template('profile.html', user=user, countries=countries, error_delete=error_delete)

            # Generate and store code
            code = str(random.randint(100000, 999999))
            temp_del_user = TempDeleteUser(email=email, code=code)
            db.session.merge(temp_del_user)
            db.session.commit()

            # Send code by email
            msg = Message("Account deletion verification code",
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[email])
            msg.body = f"Your account deletion verification code is: {code}"
            mail.send(msg)

            return render_template('profile.html', user=user, countries=countries, delete_step=2, delete_email=email)

        elif action == 'confirm_delete':
            # User submitted verification code to confirm deletion
            email = request.form.get('delete_email').lower()
            input_code = request.form.get('delete_code')

            temp_del_user = TempDeleteUser.query.get(email)
            if not temp_del_user or temp_del_user.code != input_code:
                error_delete_code = "Incorrect verification code."
                return render_template('profile.html', user=user, countries=countries, delete_step=2, delete_email=email, error_delete_code=error_delete_code)

            # Delete user account
            db.session.delete(user)
            db.session.delete(temp_del_user)
            db.session.commit()

            session.clear()
            return render_template('delete_success.html')  # Or redirect to a "goodbye" page

    # GET
    return render_template('profile.html', user=user, countries=countries)

@app.context_processor
def inject_current_user():
    from flask import session
    if 'email' in session:
        user = User.query.get(session['email'])
    else:
        user = None
    return dict(current_user=user)

#------------------predict----------------
@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if 'email' not in session:
        return redirect(url_for('login'))

    result = None
    if request.method == 'POST':
        amount = float(request.form['amount'])
        frequency = int(request.form['frequency'])
        location = request.form['location']
        if amount > 3000 and frequency < 2 and location.lower() == 'unknown':
            result = "Transaction potentiellement frauduleuse"
        else:
            result = "Transaction légitime"
    return render_template('predict.html', result=result)


#------------------delete-account----------------


@app.route('/delete_request', methods=['GET', 'POST'])
def delete_request():
    if 'email' not in session:
        return redirect(url_for('login'))

    error = None

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if email and password:  # only check if both fields are filled
            user = User.query.get(email)

            if user and user.check_password(password):
                # Generate and send code
                code = ''.join(random.choices(string.digits, k=6))
                session['delete_code'] = code
                session['delete_email'] = email

                msg = Message('Your account deletion code', sender=app.config['MAIL_USERNAME'], recipients=[email])
                msg.body = f'Your deletion verification code is: {code}'
                mail.send(msg)

                return redirect(url_for('delete_verify'))
            else:
                error = 'Invalid email or password.'

    return render_template('delete_request.html', error=error)


@app.route('/delete_verify', methods=['GET', 'POST'])
def delete_verify():
    if 'delete_code' not in session or 'delete_email' not in session:
        return redirect(url_for('profile'))  # No verification initiated

    error = None

    if request.method == 'POST':
        entered_code = request.form.get('code')

        if entered_code == session['delete_code']:
            user = User.query.get(session['delete_email'])

            if user:
                db.session.delete(user)
                db.session.commit()

            # Remove user-related session data
            session.pop('delete_code', None)
            session.pop('delete_email', None)
            session.pop('email', None)  # if used for login session
            session.pop('username', None)  # if you store this

            return redirect(url_for('welcome'))  # Goodbye or homepage
        else:
            error = "Incorrect verification code."

    return render_template('delete_verify.html', error=error)
4
#------------------about----------------
@app.route('/about')
def about():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)
