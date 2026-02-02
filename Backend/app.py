from flask import Flask, request, jsonify
from flask_cors import CORS
from db import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
from functools import wraps
import mysql.connector
import os

app = Flask(__name__)

# 🔐 SECRET KEY
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "supersecretkey")

# ✅ CORS CONFIG (ALLOW FRONTEND ORIGINS)
CORS(app, supports_credentials=False, origins=[
    "https://tms.infinityfree.me",
    "http://localhost:5500",
    "http://127.0.0.1:5500"
])


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        autocommit=True
    )



# -------------------------------------------------
# TOKEN REQUIRED DECORATOR
# -------------------------------------------------
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]

        if not token:
            return jsonify({"error": "Token is missing"}), 401

        try:
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            current_user_id = data["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(current_user_id, *args, **kwargs)

    return decorated


# -------------------------------------------------
# REGISTER
# -------------------------------------------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
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


# -------------------------------------------------
# LOGIN
# -------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
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

    token = jwt.encode({
        "user_id": user["id"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config["SECRET_KEY"], algorithm="HS256")

    return jsonify({
        "message": "Login successful",
        "token": token,
        "username": user["username"]
    }), 200


# -------------------------------------------------
# ADD TRANSACTION
# -------------------------------------------------
@app.route("/api/transactions", methods=["POST"])
@token_required
def add_transaction(current_user_id):
    data = request.json

    stock = data["stock_symbol"]
    t_type = data["transaction_type"]
    qty = int(data["quantity"])
    price = float(data["price"])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # SELL validation
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
        """, (stock, current_user_id))

        holding = cursor.fetchone()["holding"]

        if qty > holding:
            cursor.close()
            conn.close()
            return jsonify({"error": "Not enough stock to sell"}), 400

    cursor.execute("""
        INSERT INTO transactions
        (user_id, stock_symbol, transaction_type, quantity, price)
        VALUES (%s, %s, %s, %s, %s)
    """, (current_user_id, stock, t_type, qty, price))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Transaction added"}), 201


# -------------------------------------------------
# GET ALL TRANSACTIONS
# -------------------------------------------------
@app.route("/api/transactions", methods=["GET"])
@token_required
def get_transactions(current_user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM transactions
        WHERE user_id = %s
        ORDER BY transaction_date DESC
    """, (current_user_id,))

    data = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(data)


# -------------------------------------------------
# HOLDINGS
# -------------------------------------------------
@app.route("/api/holdings", methods=["GET"])
@token_required
def get_holdings(current_user_id):
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
    """, (current_user_id,))

    data = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(data)


# -------------------------------------------------
# SUMMARY
# -------------------------------------------------
@app.route("/api/summary", methods=["GET"])
@token_required
def get_summary(current_user_id):
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
    """, (current_user_id,))

    data = cursor.fetchone()
    cursor.close()
    conn.close()

    return jsonify(data)


# -------------------------------------------------
# RUN
# -------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
