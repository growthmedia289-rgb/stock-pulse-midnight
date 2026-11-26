from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    portfolios = db.relationship('Portfolio', backref='user', lazy=True, cascade='all, delete-orphan')
    watchlists = db.relationship('Watchlist', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Portfolio(db.Model):
    __tablename__ = 'portfolios'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ticker     = db.Column(db.String(20), nullable=False)
    company    = db.Column(db.String(100))
    buy_price  = db.Column(db.Float, nullable=False)
    quantity   = db.Column(db.Float, nullable=False)
    buy_date   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes      = db.Column(db.Text)

    @property
    def invested(self):
        return self.buy_price * self.quantity

    def __repr__(self):
        return f'<Portfolio {self.ticker} x{self.quantity}>'


class Watchlist(db.Model):
    __tablename__ = 'watchlists'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ticker     = db.Column(db.String(20), nullable=False)
    added_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    alert_price = db.Column(db.Float)

    def __repr__(self):
        return f'<Watchlist {self.ticker}>'


class Trade(db.Model):
    __tablename__ = 'trades'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ticker       = db.Column(db.String(20), nullable=False)
    action       = db.Column(db.String(4), nullable=False)  # BUY / SELL
    price        = db.Column(db.Float, nullable=False)
    quantity     = db.Column(db.Float, nullable=False)
    timestamp    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    pnl          = db.Column(db.Float)

    def __repr__(self):
        return f'<Trade {self.action} {self.ticker}>'


class ScanResult(db.Model):
    __tablename__ = 'scan_results'
    id                  = db.Column(db.Integer, primary_key=True)
    ticker              = db.Column(db.String(20))
    breakout_prob       = db.Column(db.Float)
    sentiment_score     = db.Column(db.Float)
    rsi                 = db.Column(db.Float)
    macd                = db.Column(db.Float)
    signal              = db.Column(db.String(10))
    scanned_at          = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
