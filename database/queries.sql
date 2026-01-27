SELECT
    stock_symbol,
    SUM(
        CASE
            WHEN transaction_type = 'BUY' THEN quantity
            WHEN transaction_type = 'SELL' THEN -quantity
        END
    ) AS net_quantity
FROM transactions
GROUP BY stock_symbol;


SELECT
    SUM(CASE WHEN transaction_type='BUY' THEN quantity*price ELSE 0 END) AS total_buy,
    SUM(CASE WHEN transaction_type='SELL' THEN quantity*price ELSE 0 END) AS total_sell
FROM transactions;


SELECT
    u.username,
    t.stock_symbol,
    t.transaction_type,
    t.quantity,
    t.price,
    t.transaction_date
FROM transactions t
JOIN users u ON t.user_id = u.id;

INSERT INTO users (id, username) VALUES (1, 'demo');


SELECT * FROM users;

SHOW PROCESSLIST;

USE stock_system;
TRUNCATE TABLE transactions;

ALTER TABLE users
ADD COLUMN password VARCHAR(255) NOT NULL;
