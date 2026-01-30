from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import traceback

try:
    from db import get_db_connection
except Exception as e:
    print("❌ DB import failed:", e)
    get_db_connection = None

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True
)

CORS(app, supports_credentials=True, origins=[
    "https://tms.infinityfree.me",
    "https://dbms-project-3xgk.onrender.com",
    "http://localhost:5500",
    "http://127.0.0.1:5500"
])

@app.route("/")
def home():
    return "Backend is running!"

def safe_db():
    if not get_db_connection:
        raise Exception("DB module failed to load")
    return get_db_connection()

# ---------------- REGISTER ----------------
@app.route("/api/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data received"}), 400

        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400

        conn = safe_db()
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

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Server error", "details": str(e)}), 500

# ---------------- LOGIN ----------------
@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data received"}), 400

        username = data.get("username")
        password = data.get("password")

        conn = safe_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or not check_password_hash(user["password"], password):
            return jsonify({"error": "Invalid credentials"}), 401

        session["user_id"] = user["id"]

        return jsonify({"message": "Login successful"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Server error", "details": str(e)}), 500

# ---------------- LOGOUT ----------------
@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200

def login_required():
    return "user_id" in session

# ---------------- ADD TRANSACTION ----------------
@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    if not login_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json()
        user_id = session["user_id"]

        stock = data.get("stock_symbol")
        t_type = data.get("transaction_type")
        qty = int(data.get("quantity"))
        price = float(data.get("price"))

        conn = safe_db()
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
                cursor.close()
                conn.close()
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
        return jsonify({"error": "Server error", "details": str(e)}), 500

# ---------------- GET TRANSACTIONS ----------------
@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    if not login_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        user_id = session["user_id"]

        conn = safe_db()
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
        return jsonify({"error": "Server error", "details": str(e)}), 500

# ---------------- HOLDINGS ----------------
@app.route("/api/holdings", methods=["GET"])
def get_holdings():
    if not login_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        user_id = session["user_id"]

        conn = safe_db()
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
        return jsonify({"error": "Server error", "details": str(e)}), 500

# ---------------- SUMMARY ----------------
@app.route("/api/summary", methods=["GET"])
def get_summary():
    if not login_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        user_id = session["user_id"]

        conn = safe_db()
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
        return jsonify({"error": "Server error", "details": str(e)}), 500

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    print("🚀 Starting server on port", port)
    app.run(host="0.0.0.0", port=port)
