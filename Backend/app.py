from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import traceback
import jwt
import datetime
from db import get_db_connection

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

CORS(app, origins=[
    "https://tms.infinityfree.me",
    "http://localhost:5500",
    "http://127.0.0.1:5500"
])

JWT_SECRET = os.getenv("JWT_SECRET", "jwtsecret123")

@app.route("/")
def home():
    return "Backend is running!"

def generate_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    try:
        token = auth_header.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["user_id"]
    except:
        return None

# ---------------- REGISTER ----------------
@app.route("/api/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({"error": "Username already exists"}), 400

        hashed_pw = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hashed_pw)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "User registered successfully"}), 201

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Server error"}), 500

# ---------------- LOGIN ----------------
@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or not check_password_hash(user["password"], password):
            return jsonify({"error": "Invalid credentials"}), 401

        token = generate_token(user["id"])
        return jsonify({"token": token, "username": user["username"]}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Server error"}), 500

# ---------------- ADD TRANSACTION ----------------
@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    user_id = verify_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json()
        stock = data.get("stock_symbol")
        t_type = data.get("transaction_type")
        qty = int(data.get("quantity"))
        price = float(data.get("price"))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if t_type == "SELL":
            cursor.execute("""
                SELECT COALESCE(SUM(
                    CASE
                        WHEN transaction_type = 'BUY' THEN quantity
                        WHEN transaction_type = 'SELL' THEN -quantity
                    END
                ), 0) AS holding
                FROM transactions
                WHERE stock_symbol = %s AND user_id = %s
            """, (stock, user_id))

            holding = cursor.fetchone()["holding"]
            if qty > holding:
                return jsonify({"error": "Not enough stock to sell"}), 400

        cursor.execute("""
            INSERT INTO transactions
            (user_id, stock_symbol, transaction_type, quantity, price)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, stock, t_type, qty, price))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Transaction added"}), 201

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Server error"}), 500

# ---------------- GET TRANSACTIONS ----------------
@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    user_id = verify_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM transactions
            WHERE user_id = %s
            ORDER BY transaction_date DESC
        """, (user_id,))
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Server error"}), 500

# ---------------- HOLDINGS ----------------
@app.route("/api/holdings", methods=["GET"])
def get_holdings():
    user_id = verify_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT stock_symbol,
                   SUM(
                       CASE
                           WHEN transaction_type = 'BUY' THEN quantity
                           WHEN transaction_type = 'SELL' THEN -quantity
                       END
                   ) AS net_quantity
            FROM transactions
            WHERE user_id = %s
            GROUP BY stock_symbol
            HAVING net_quantity > 0
        """, (user_id,))
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Server error"}), 500

# ---------------- SUMMARY ----------------
@app.route("/api/summary", methods=["GET"])
def get_summary():
    user_id = verify_token(request)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                SUM(CASE WHEN transaction_type = 'BUY'
                         THEN quantity * price ELSE 0 END) AS total_buy,
                SUM(CASE WHEN transaction_type = 'SELL'
                         THEN quantity * price ELSE 0 END) AS total_sell
            FROM transactions
            WHERE user_id = %s
        """, (user_id,))
        data = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify(data)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error"
