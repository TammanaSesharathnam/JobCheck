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
app.config["JWT_ERROR_MESSAGE_KEY"] = "error"

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
    job_title = db.Column(db.String(200), nullable=True)
    company = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=False)
    result = db.Column(db.String(50), nullable=False)
    confidence = db.Column(db.String(10), nullable=False)
    is_flagged = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())

# Initialize database
with app.app_context():
    db.create_all()
    
    # Migration helper for existing DB - adding columns individually
    from sqlalchemy import text
    columns_to_add = [
        ("users", "is_admin", "BOOLEAN DEFAULT 0"),
        ("job_logs", "job_title", "VARCHAR(200)"),
        ("job_logs", "company", "VARCHAR(100)"),
        ("job_logs", "is_flagged", "BOOLEAN DEFAULT 0")
    ]
    
    for table, column, col_type in columns_to_add:
        try:
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            db.session.commit()
            print(f"Added column {column} to {table}")
        except Exception:
            db.session.rollback()
            # Column likely already exists, ignore
            pass

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
    login_id = data.get("email") # The field is labeled 'email' in frontend but we'll accept username too
    password = data.get("password")

    if not login_id or not password:
        return jsonify({"error": "Credentials required"}), 400

    # Try finding by email first, then by username
    user = User.query.filter_by(email=login_id).first()
    if not user:
        user = User.query.filter_by(username=login_id).first()

    if user and check_password_hash(user.password, password):
        access_token = create_access_token(identity=user.username)
        print(f"Login success: {user.username} ({'Admin' if user.is_admin else 'User'})")
        return jsonify({
            "token": access_token, 
            "username": user.username,
            "email": user.email,
            "fullname": user.fullname or user.username,
            "is_admin": user.is_admin
        })
    else:
        if not user:
            print(f"Login failure: User not found for '{login_id}'")
        else:
            print(f"Login failure: Password mismatch for user '{user.username}'")
        return jsonify({"error": "Invalid credentials"}), 401

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
    is_admin = user and user.is_admin
    print(f"Checking admin for '{username}': {'FOUND' if user else 'NOT FOUND'}, is_admin={is_admin}")
    return is_admin

@app.route("/admin/stats", methods=["GET"])
@jwt_required()
def admin_stats():
    current_user = get_jwt_identity()
    print(f"ADMIN REQUEST: /admin/stats from user '{current_user}'")
    if not check_admin(current_user):
        print(f"ADMIN DENIED: /admin/stats for user '{current_user}'")
        return jsonify({"error": f"Admin access required for user '{current_user}'"}), 403
    
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
        "created_at": f.created_at.strftime("%Y-%m-%d %H:%M:%S") if f.created_at else "Unknown"
    } for f in feedbacks]
    
    return jsonify(feedback_list)

@app.route("/admin/activity", methods=["GET"])
@jwt_required()
def admin_activity():
    current_user = get_jwt_identity()
    print(f"ADMIN REQUEST: /admin/activity from user '{current_user}'")
    if not check_admin(current_user):
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        logs = db.session.query(JobLog, User).join(User, JobLog.user_id == User.id).order_by(JobLog.timestamp.desc()).all()
        print(f"Retrieved {len(logs)} activity logs")
    except Exception as e:
        print(f"DATABASE ERROR in admin_activity: {e}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    log_list = [{
        "id": log.JobLog.id,
        "username": log.User.username,
        "job_title": log.JobLog.job_title or "Untitled Analysis",
        "company": log.JobLog.company or "N/A",
        "description": log.JobLog.description,
        "result": log.JobLog.result,
        "confidence": log.JobLog.confidence,
        "is_flagged": log.JobLog.is_flagged,
        "timestamp": log.JobLog.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.JobLog.timestamp else "Unknown"
    } for log in logs]
    
    return jsonify(log_list)

@app.route("/admin/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    current_admin = get_jwt_identity()
    if not check_admin(current_admin):
        return jsonify({"error": "Admin access required"}), 403
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    if user.username == current_admin:
        return jsonify({"error": "You cannot delete your own admin account"}), 400

    try:
        # Delete related logs and feedback first if needed, 
        # but here we'll just delete the user
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/admin/jobs/<int:job_id>/flag", methods=["POST"])
@jwt_required()
def toggle_flag(job_id):
    current_user = get_jwt_identity()
    if not check_admin(current_user):
        return jsonify({"error": "Admin access required"}), 403
    
    log = JobLog.query.get(job_id)
    if not log:
        return jsonify({"error": "Log not found"}), 404
    
    log.is_flagged = not log.is_flagged
    db.session.commit()
    return jsonify({"message": "Status updated", "is_flagged": log.is_flagged})

@app.route("/admin/retrain", methods=["POST"])
@jwt_required()
def retrain_model():
    current_user = get_jwt_identity()
    if not check_admin(current_user):
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        # Run the training script logic
        import subprocess
        # Using sys.executable to run with the current python environment
        import sys
        result = subprocess.run([sys.executable, "train_model.py"], capture_output=True, text=True)
        
        if result.returncode == 0:
            # Reload models
            global model, vectorizer
            model = pickle.load(open("model.pkl", "rb"))
            vectorizer = pickle.load(open("vectorizer.pkl", "rb"))
            return jsonify({"message": "Intelligence retrained and reloaded successfully!"})
        else:
            return jsonify({"error": f"Retraining failed: {result.stderr}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Global Error Handler
@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if hasattr(e, 'code') and hasattr(e, 'description'):
        return jsonify({"error": e.description}), e.code
    return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

# ------------------ PREDICT (Protected) ------------------

@app.route("/predict", methods=["POST"])
@jwt_required()
def predict():
    current_username = get_jwt_identity()
    user = User.query.filter_by(username=current_username).first()
    
    data = request.json.get("description")
    job_title = request.json.get("job_title", "")
    company = request.json.get("company", "")

    if not data:
        return jsonify({"error": "No description provided"}), 400

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
            job_title=job_title,
            company=company,
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
    app.run(debug=True, host='0.0.0.0', port=5000)
