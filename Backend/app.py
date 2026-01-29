from flask import Flask, request, jsonify, session
from flask_cors import CORS
import mysql.connector
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

CORS(app, supports_credentials=True)

# ---------------- DB CONNECTION ----------------
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# ---------------- AUTH ----------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Missing fields"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        return jsonify({"error": "Username already exists"}), 409

    hashed_pw = generate_password_hash(password)
    cursor.execute(
        "INSERT INTO users (username, password) VALUES (%s, %s)",
        (username, hashed_pw)
    )
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "Registered successfully"}), 201


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

    session["user_id"] = user["id"]

    return jsonify({"message": "Login successful"}), 200


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200


# ---------------- TRANSACTIONS ----------------
@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()

    stock = data.get("stock_symbol")
    t_type = data.get("transaction_type")
    qty = int(data.get("quantity"))
    price = float(data.get("price"))
    user_id = session["user_id"]

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


@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]

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


# ---------------- HOLDINGS ----------------
@app.route("/api/holdings", methods=["GET"])
def get_holdings():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]

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


# ---------------- SUMMARY ----------------
@app.route("/api/summary", methods=["GET"])
def get_summary():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]

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


# ---------------- ROOT ----------------
@app.route("/", methods=["GET"])
def home():
    return "Backend is running 🚀", 200


# ---------------- RUN SERVER ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
