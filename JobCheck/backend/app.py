from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
import pickle
import os

app = Flask(__name__)
CORS(app)

# ------------------ CONFIGURATION ------------------

basedir = os.path.abspath(os.path.dirname(__file__))

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "jobcheck-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", 
    "sqlite:///" + os.path.join(basedir, "users.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
jwt = JWTManager(app)

# ------------------ DATABASE MODELS ------------------

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Feedback(db.Model):
    __tablename__ = 'feedback'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

class JobLog(db.Model):
    __tablename__ = 'job_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    result = db.Column(db.String(50), nullable=False)
    confidence = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())

# Initialize database
with app.app_context():
    db.create_all()
    
    # Migration helper for existing DB
    from sqlalchemy import text
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
        db.session.commit()
    except Exception:
        db.session.rollback()

# Load ML Model
try:
    model = pickle.load(open("model.pkl", "rb"))
    vectorizer = pickle.load(open("vectorizer.pkl", "rb"))
except Exception as e:
    print(f"Error loading model: {e}")

# ------------------ REGISTER ------------------

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    fullname = data.get("name")
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    is_admin = data.get("is_admin", False)

    if not username or not email or not password:
        return jsonify({"error": "Fields are required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "This Username is already taken"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "This Email is already registered"}), 400

    if not fullname:
        fullname = username

    hashed_password = generate_password_hash(password)

    try:
        new_user = User(fullname=fullname, username=username, email=email, password=hashed_password, is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User registered successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ------------------ LOGIN ------------------
# (Login remains same but is_admin is already in response)

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password, password):
        access_token = create_access_token(identity=user.username)
        return jsonify({
            "token": access_token, 
            "username": user.username,
            "email": user.email,
            "fullname": user.fullname or user.username,
            "is_admin": user.is_admin
        })
    else:
        return jsonify({"error": "Invalid email or password"}), 401

# ------------------ FEEDBACK ------------------

@app.route("/feedback", methods=["POST"])
@jwt_required()
def submit_feedback():
    current_username = get_jwt_identity()
    user = User.query.filter_by(username=current_username).first()
    user_id = user.id if user else None

    data = request.json
    name = data.get("name")
    email = data.get("email")
    subject = data.get("subject")
    message = data.get("message")

    if not name or not email or not message:
        return jsonify({"error": "Name, email and message are required"}), 400

    try:
        new_feedback = Feedback(
            user_id=user_id,
            name=name,
            email=email,
            subject=subject or "General Feedback",
            message=message
        )
        db.session.add(new_feedback)
        db.session.commit()
        return jsonify({"message": "Feedback submitted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ------------------ ADMIN ROUTES ------------------

def check_admin(username):
    user = User.query.filter_by(username=username).first()
    return user and user.is_admin

@app.route("/admin/stats", methods=["GET"])
@jwt_required()
def admin_stats():
    current_user = get_jwt_identity()
    if not check_admin(current_user):
        return jsonify({"error": "Admin access required"}), 403
    
    user_count = User.query.count()
    feedback_count = Feedback.query.count()
    check_count = JobLog.query.count()
    
    return jsonify({
        "total_users": user_count,
        "total_feedback": feedback_count,
        "total_checks": check_count
    })

@app.route("/admin/users", methods=["GET"])
@jwt_required()
def admin_users():
    current_user = get_jwt_identity()
    if not check_admin(current_user):
        return jsonify({"error": "Admin access required"}), 403
    
    users = User.query.all()
    user_list = [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "fullname": u.fullname,
        "is_admin": u.is_admin
    } for u in users]
    
    return jsonify(user_list)

@app.route("/admin/feedback", methods=["GET"])
@jwt_required()
def admin_feedback():
    current_user = get_jwt_identity()
    if not check_admin(current_user):
        return jsonify({"error": "Admin access required"}), 403
    
    feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).all()
    feedback_list = [{
        "id": f.id,
        "name": f.name,
        "email": f.email,
        "subject": f.subject,
        "message": f.message,
        "created_at": f.created_at.strftime("%Y-%m-%d %H:%M:%S")
    } for f in feedbacks]
    
    return jsonify(feedback_list)

@app.route("/admin/activity", methods=["GET"])
@jwt_required()
def admin_activity():
    current_user = get_jwt_identity()
    if not check_admin(current_user):
        return jsonify({"error": "Admin access required"}), 403
    
    logs = db.session.query(JobLog, User).join(User, JobLog.user_id == User.id).order_by(JobLog.timestamp.desc()).all()
    log_list = [{
        "id": log.JobLog.id,
        "username": log.User.username,
        "description": log.JobLog.description,
        "result": log.JobLog.result,
        "confidence": log.JobLog.confidence,
        "timestamp": log.JobLog.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    } for log in logs]
    
    return jsonify(log_list)

# ------------------ PREDICT (Protected) ------------------

@app.route("/predict", methods=["POST"])
@jwt_required()
def predict():
    current_username = get_jwt_identity()
    user = User.query.filter_by(username=current_username).first()
    
    data = request.json["description"]
    transformed = vectorizer.transform([data])
    
    prediction = model.predict(transformed)[0]
    probabilities = model.predict_proba(transformed)[0]
    confidence_val = probabilities[prediction] * 100
    confidence_str = f"{round(confidence_val)}%"
    result_str = "Fake Job" if prediction == 1 else "Real Job"

    # Save activity log
    try:
        new_log = JobLog(
            user_id=user.id,
            description=data,
            result=result_str,
            confidence=confidence_str
        )
        db.session.add(new_log)
        db.session.commit()
    except Exception as e:
        print(f"Log save error: {e}")
        db.session.rollback()

    return jsonify({
        "user": current_username,
        "result": result_str,
        "confidence": confidence_str
    })

# ------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
