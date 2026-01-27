from flask import Flask, request, jsonify
from flask_cors import CORS
from db import get_db_connection
from werkzeug.security import generate_password_hash

app = Flask(__name__)
CORS(app)

# Simulated logged-in user
user_id = 1

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

    # INSERT transaction (FIXED)
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

def ensure_user_exists():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (id, username) VALUES (%s, %s)",
            (user_id, "demo")
        )
        conn.commit()
    conn.close()

ensure_user_exists()



# -------------------------------------------------
# RUN SERVER
# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
