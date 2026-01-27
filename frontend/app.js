const form = document.getElementById("transactionForm");
const list = document.getElementById("list");
const symbol = document.getElementById("symbol");
const type = document.getElementById("type");
const quantity = document.getElementById("quantity");
const price = document.getElementById("price");
const totalBuy = document.getElementById("totalBuy");
const totalSell = document.getElementById("totalSell");
const holdingsList = document.getElementById("holdingsList");
const errorMsg = document.getElementById("error");

// ------------------ Add Transaction ------------------
form.addEventListener("submit", async e => {
    e.preventDefault();

    errorMsg.textContent = ""; // clear previous error

    const data = {
        stock_symbol: symbol.value,
        transaction_type: type.value,
        quantity: quantity.value,
        price: price.value
    };

    try {
        const res = await fetch("http://127.0.0.1:5000/api/transactions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });

        const result = await res.json();

        if (!res.ok) {
            errorMsg.textContent = result.error || "Failed to add transaction";
            return;
        }

        form.reset();
        loadTransactions();
        loadSummary();
        loadHoldings();
    } catch (err) {
        errorMsg.textContent = "Server error. Try again.";
        console.error(err);
    }
});

// ------------------ Load All Transactions ------------------
async function loadTransactions() {
    const res = await fetch("http://127.0.0.1:5000/api/transactions");
    const data = await res.json();

    list.innerHTML = "";
    data.forEach(t => {
        const li = document.createElement("li");
        li.textContent = `${t.stock_symbol} | ${t.transaction_type} | ${t.quantity} @ ${t.price}`;
        list.appendChild(li);
    });
}

// ------------------ Load Dashboard Summary ------------------
async function loadSummary() {
    const res = await fetch("http://127.0.0.1:5000/api/summary");
    const data = await res.json();

    totalBuy.textContent = data.total_buy ;
    totalSell.textContent = data.total_sell;
}

// ------------------ Load Holdings ------------------
async function loadHoldings() {
    const res = await fetch("http://127.0.0.1:5000/api/holdings");
    const data = await res.json();

    holdingsList.innerHTML = "";
    data.forEach(h => {
        const li = document.createElement("li");
        li.textContent = `${h.stock_symbol} : ${h.net_quantity}`;
        holdingsList.appendChild(li);
    });
}

// ------------------ Initial Load ------------------
loadTransactions();
loadSummary();
loadHoldings();
