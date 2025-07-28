from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    email = db.Column(db.String(120), primary_key=True)
    fullname = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)  # renamed from password
    phone = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    business = db.Column(db.String(100), nullable=False)
    profile_picture = db.Column(db.String(200), nullable=True) 

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'email': self.email,
            'fullname': self.fullname,
            'username': self.username,
            'phone': self.phone,
            'country': self.country,
            'city': self.city,
            'business': self.business,
            'profile_picture': self.profile_picture
        }

class TempUser(db.Model):
    __tablename__ = 'temp_users'

    email = db.Column(db.String(120), primary_key=True)
    code = db.Column(db.String(6), nullable=False)
    
class TempDeleteUser(db.Model):
    email = db.Column(db.String(120), primary_key=True)
    code = db.Column(db.String(6), nullable=False)
class PredictionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String, db.ForeignKey('users.email'))
    amount = db.Column(db.Float)
    frequency = db.Column(db.Float)
    country_code = db.Column(db.String)
    time_spent = db.Column(db.Float)
    account_age = db.Column(db.Integer)
    prediction = db.Column(db.String)
    probability = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)

