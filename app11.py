import os
import random
import json
from datetime import datetime, timedelta
import string
from flask import Flask, render_template, request, redirect, session, url_for, jsonify ,flash
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from models import db, User, TempUser ,TempDeleteUser, PredictionHistory

import joblib
import numpy as np


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


if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


with open('locations.json', 'r', encoding='utf-8') as f:
    locations = json.load(f)


with app.app_context():
    db.create_all()

# -------------- ROUTES --------------

@app.route('/')
def root():
    if 'email' in session:
        return render_template('index.html')
    return render_template('welcome.html')

# -------------- welcome --------------
@app.route('/welcome')
def welcome():
    return render_template('welcome.html')
# -------------- register --------------
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

# -------------- get_cities --------------
@app.route('/get_cities/<country_code>')
def get_cities(country_code):
    country = locations.get(country_code.upper())
    if country:
        return jsonify(country["cities"])
    return jsonify([])

last_code_sent = {}

# -------------- resend_code --------------
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

# -------------- verify --------------
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

    
    return render_template('profile.html', user=user, countries=countries)

@app.context_processor
def inject_current_user():
    if 'email' in session:
        user = User.query.get(session['email'])
    else:
        user = None
    return dict(current_user=user)

#------------------predict----------------
model = joblib.load("logreg_calibrated_model.pkl")
le = joblib.load("location_encoder.pkl")

risky_countries = ['Bangladesh', 'Nigeria', 'Pakistan', 'Venezuela', 'Afghanistan', 'Russia', 'Ukraine']

# Charger le fichier locations.json
with open("locations.json", "r", encoding="utf-8") as f:
    locations = json.load(f)

# Créer la liste des pays (pour affichage et validation)
country_names = [data["country"] for data in locations.values()]

@app.route("/predict", methods=["GET", "POST"])
def predict():
    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
            frequency = float(request.form["frequency"])
            country_code = request.form["country_code"]
            time_spent = float(request.form["time_spent"])
            account_age = int(request.form["account_age"])

            # Validate country code exists in locations
            if country_code not in locations:
                result = "Error: Selected country is not recognized."
                return render_template("predict.html", result=result, locations=locations)

            # Get country name and encode based on country code index
            country_name = locations[country_code]["country"]
            location_encoded = list(locations.keys()).index(country_code)

            input_data = np.array([[amount, frequency, location_encoded, time_spent, account_age]])
            prediction = model.predict(input_data)[0]
            prob = model.predict_proba(input_data)[0][1]

            if prob > 0.3:
                reasons = []
                if amount > 100000:
                    reasons.append("The amount is very high")
                if frequency < 2:
                    reasons.append("Transaction frequency is low")
                if country_name in risky_countries:
                    reasons.append(f"The country of origin ({country_name}) is considered risky")
                if time_spent < 10:
                    reasons.append("Time spent on website is very short")
                if account_age < 50:
                    reasons.append("The account is recent")
                explanation = " and ".join(reasons) if reasons else "No significant risk factors detected"
            else:
                explanation = "Risk is low, no significant factors to display."

            result = f"Estimated fraud risk: {prob * 100:.1f}%<br><br>Reason(s): {explanation}."

            # ----------- SAVE TO HISTORY -----------
            if 'email' in session:
                user_email = session['email']
                history_entry = PredictionHistory(
                    user_email=user_email,
                    amount=amount,
                    frequency=frequency,
                    country_code=country_code,
                    time_spent=time_spent,
                    account_age=account_age,
                    prediction=prediction,
                    probability=prob
                )
                db.session.add(history_entry)
                db.session.commit()
            # -----------------------------------------
            return render_template("predict.html", result=result, locations=locations, country_code=country_code)
        except ValueError as e:
            result = "Error: Please ensure all fields are filled correctly."
            return render_template("predict.html", result=result, locations=locations)
    return render_template("predict.html", locations=locations, country_names=country_names)

#------------------delete-account----------------


@app.route('/delete_request', methods=['GET', 'POST'])
def delete_request():
    if 'email' not in session:
        return redirect(url_for('login'))

    error = None

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if email and password:  
            user = User.query.get(email)

            if user and user.check_password(password):
                
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
        return redirect(url_for('profile'))  

    error = None

    if request.method == 'POST':
        entered_code = request.form.get('code')

        if entered_code == session['delete_code']:
            user = User.query.get(session['delete_email'])

            if user:
                db.session.delete(user)
                db.session.commit()

            
            session.pop('delete_code', None)
            session.pop('delete_email', None)
            session.pop('email', None)  
            session.pop('username', None)  

            return redirect(url_for('welcome'))  
        else:
            error = "Incorrect verification code."

    return render_template('delete_verify.html', error=error)

#------------------about----------------
@app.route("/about", methods=["GET", "POST"])
def about():
    error = None
    success = None
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        if not name or not email or not message:
            error = "Please fill in all fields."
        else:
            success = "Thank you for your message! We will get back to you shortly."

    return render_template("about.html", error=error, success=success)


#------------------history----------------

@app.route('/history')
def history():
    if 'email' not in session:
        return redirect(url_for('login'))
    user_history = PredictionHistory.query.filter_by(user_email=session['email']).order_by(PredictionHistory.id.desc()).all()
    with open('locations.json', 'r', encoding='utf-8') as f:
        locations = json.load(f)
    return render_template('history.html', history=user_history, locations=locations)

            
#------------------main----------------
if __name__ == '__main__':
    app.run(debug=True)
