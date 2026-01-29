from flask import Flask, request, jsonify
from flask_cors import CORS
from db import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)

# Simulated logged-in user (will improve later)
user_id = 1


# -------------------------------------------------
# REGISTER
# -------------------------------------------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    hashed_password = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check if user already exists
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Username already exists"}), 400

    # Insert user
    cursor.execute(
        "INSERT INTO users (username, password) VALUES (%s, %s)",
        (username, hashed_password)
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
    data = request.json
    username = data.get("username")
    password = data.get("password")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({"message": "Login successful", "user_id": user["id"]}), 200


# -------------------------------------------------
# ADD TRANSACTION
# -------------------------------------------------
@app.route("/api/transactions", methods=["POST"])
def add_transaction():
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


# -------------------------------------------------
# GET ALL TRANSACTIONS
# -------------------------------------------------
@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM transactions
        ORDER BY transaction_date DESC
    """)

    data = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(data)


# -------------------------------------------------
# HOLDINGS
# -------------------------------------------------
@app.route("/api/holdings", methods=["GET"])
def get_holdings():
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


# -------------------------------------------------
# SUMMARY
# -------------------------------------------------
@app.route("/api/summary", methods=["GET"])
def get_summary():
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


# -------------------------------------------------
# RUN SERVER
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
