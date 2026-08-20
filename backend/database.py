"""
SME Anchor - Database layer
Single central SQLite database shared by Owner, Customer and Supplier portals.
"""
import sqlite3
import random
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "sme_anchor.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS business (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    cash REAL NOT NULL,
    budget REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL,
    min_stock INTEGER NOT NULL,
    daily_demand REAL NOT NULL,
    description TEXT,
    rating REAL,
    image_seed TEXT
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    reliability REAL NOT NULL,
    rating REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS supplier_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    price REAL NOT NULL,
    delivery_days INTEGER NOT NULL,
    available_qty INTEGER NOT NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    subtotal REAL NOT NULL,
    tax REAL NOT NULL,
    total REAL NOT NULL,
    cost_of_goods REAL NOT NULL,
    profit REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total REAL NOT NULL,
    delivery_days INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_approval',
    reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT,
    amount REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    context_json TEXT,
    created_at TEXT NOT NULL
);
"""

CATEGORIES = {
    "Staples": ["Rice", "Wheat Flour", "Basmati Rice", "Sooji", "Poha", "Besan",
                "Toor Dal", "Moong Dal", "Chana Dal", "Urad Dal", "Masoor Dal",
                "Sugar", "Salt", "Jaggery", "Sunflower Oil", "Groundnut Oil",
                "Mustard Oil", "Ghee", "Vermicelli", "Sabudana"],
    "Beverages": ["Tea Powder", "Green Tea", "Coffee Powder", "Instant Coffee",
                  "Soft Drink Cola", "Orange Soda", "Mango Juice", "Apple Juice",
                  "Mineral Water", "Energy Drink", "Buttermilk", "Lemon Drink"],
    "Dairy": ["Milk", "Toned Milk", "Curd", "Paneer", "Butter", "Cheese Slices",
              "Cream", "Yogurt Cup", "Milk Powder", "Condensed Milk"],
    "Snacks": ["Potato Chips", "Banana Chips", "Namkeon Mix", "Salted Peanuts",
               "Popcorn", "Chocolate Bar", "Biscuits Marie", "Cream Biscuits",
               "Rusk", "Cookies", "Cup Noodles", "Papad"],
    "Household": ["Detergent Powder", "Detergent Bar", "Dishwash Liquid",
                  "Dishwash Bar", "Floor Cleaner", "Toilet Cleaner", "Room Freshener",
                  "Mosquito Repellent", "Matchbox", "Candles", "Garbage Bags"],
    "Personal Care": ["Toothpaste", "Toothbrush", "Bathing Soap", "Shampoo",
                       "Hair Oil", "Body Lotion", "Face Wash", "Razor",
                       "Sanitary Pads", "Hand Sanitizer", "Talcum Powder"],
    "Bakery": ["Bread", "Brown Bread", "Buns", "Cake Rusk", "Pastry Pack"],
    "Spices": ["Turmeric Powder", "Red Chilli Powder", "Coriander Powder",
               "Garam Masala", "Cumin Seeds", "Mustard Seeds", "Black Pepper",
               "Biryani Masala"],
}


def build_products():
    products = []
    sku_counter = 1000
    for category, items in CATEGORIES.items():
        for item in items:
            sku_counter += 1
            stock = random.randint(4, 120)
            min_stock = random.randint(10, 30)
            daily_demand = round(random.uniform(1.5, 12), 1)
            price = round(random.uniform(15, 320), 2)
            products.append({
                "sku": f"SKU{sku_counter}",
                "name": item,
                "category": category,
                "price": price,
                "stock": stock,
                "min_stock": min_stock,
                "daily_demand": daily_demand,
                "description": f"{item} - quality {category.lower()} product for everyday household needs.",
                "rating": round(random.uniform(3.6, 4.9), 1),
                "image_seed": item.lower().replace(" ", "-"),
            })
    return products


SUPPLIER_PROFILES = [
    {"name": "Supplier A", "reliability": 94, "rating": 4.5, "price_mult": 1.00, "delivery_days": 2},
    {"name": "Supplier B", "reliability": 91, "rating": 4.2, "price_mult": 0.96, "delivery_days": 5},
    {"name": "Supplier C", "reliability": 98, "rating": 4.8, "price_mult": 1.05, "delivery_days": 1},
    {"name": "Supplier D", "reliability": 86, "rating": 3.9, "price_mult": 0.92, "delivery_days": 7},
    {"name": "Supplier E", "reliability": 96, "rating": 4.6, "price_mult": 0.98, "delivery_days": 3},
]

CUSTOMER_NAMES = ["Aarav Kumar", "Meera Nair", "Rohit Sharma", "Divya Iyer",
                   "Karthik Raj", "Sneha Pillai", "Arjun Menon", "Priya Das"]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(reset=False):
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    fresh = not os.path.exists(DB_PATH)
    conn = get_connection()
    conn.executescript(SCHEMA)

    if fresh:
        random.seed(42)
        seed(conn)

    conn.commit()
    conn.close()


def seed(conn):
    now = datetime.utcnow()
    conn.execute("INSERT INTO business (id, cash, budget) VALUES (1, 82450, 150000)")

    # Suppliers
    supplier_ids = {}
    for sp in SUPPLIER_PROFILES:
        cur = conn.execute(
            "INSERT INTO suppliers (name, reliability, rating) VALUES (?, ?, ?)",
            (sp["name"], sp["reliability"], sp["rating"]),
        )
        supplier_ids[sp["name"]] = cur.lastrowid

    # Products
    product_rows = build_products()
    product_ids = []
    for p in product_rows:
        cur = conn.execute(
            """INSERT INTO products
               (sku, name, category, price, stock, min_stock, daily_demand, description, rating, image_seed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["sku"], p["name"], p["category"], p["price"], p["stock"], p["min_stock"],
             p["daily_demand"], p["description"], p["rating"], p["image_seed"]),
        )
        product_ids.append(cur.lastrowid)

    # Supplier offers: each supplier offers ~70% of products at varied price/delivery
    for pid in product_ids:
        base_price_row = conn.execute("SELECT price FROM products WHERE id=?", (pid,)).fetchone()
        base_cost = base_price_row["price"] * 0.65  # wholesale cost baseline
        for sp in SUPPLIER_PROFILES:
            if random.random() < 0.75:
                jitter = random.uniform(0.94, 1.06)
                offer_price = round(base_cost * sp["price_mult"] * jitter, 2)
                delivery = sp["delivery_days"] + random.choice([-1, 0, 0, 1])
                delivery = max(1, delivery)
                available_qty = random.randint(20, 300)
                conn.execute(
                    """INSERT INTO supplier_offers
                       (supplier_id, product_id, price, delivery_days, available_qty)
                       VALUES (?, ?, ?, ?, ?)""",
                    (supplier_ids[sp["name"]], pid, offer_price, delivery, available_qty),
                )

    # Customers
    customer_ids = []
    for name in CUSTOMER_NAMES:
        cur = conn.execute(
            "INSERT INTO customers (name, email) VALUES (?, ?)",
            (name, name.lower().replace(" ", ".") + "@example.com"),
        )
        customer_ids.append(cur.lastrowid)

    # Historical sales for last 30 days
    for day_offset in range(30, 0, -1):
        day = now - timedelta(days=day_offset)
        num_sales = random.randint(2, 9)
        for _ in range(num_sales):
            cust = random.choice(customer_ids)
            items = random.sample(product_ids, k=random.randint(1, 5))
            subtotal = 0
            cost_total = 0
            sale_time = day.replace(
                hour=random.randint(9, 20), minute=random.randint(0, 59)
            )
            cur = conn.execute(
                """INSERT INTO sales (customer_id, subtotal, tax, total, cost_of_goods, profit, created_at)
                   VALUES (?, 0, 0, 0, 0, 0, ?)""",
                (cust, sale_time.isoformat()),
            )
            sale_id = cur.lastrowid
            for pid in items:
                prod = conn.execute("SELECT price FROM products WHERE id=?", (pid,)).fetchone()
                qty = random.randint(1, 4)
                unit_price = prod["price"]
                subtotal += unit_price * qty
                cost_total += unit_price * 0.65 * qty
                conn.execute(
                    "INSERT INTO sale_items (sale_id, product_id, qty, unit_price) VALUES (?, ?, ?, ?)",
                    (sale_id, pid, qty, unit_price),
                )
            tax = round(subtotal * 0.05, 2)
            total = round(subtotal + tax, 2)
            profit = round(total - cost_total - tax, 2)
            conn.execute(
                "UPDATE sales SET subtotal=?, tax=?, total=?, cost_of_goods=?, profit=? WHERE id=?",
                (round(subtotal, 2), tax, total, round(cost_total, 2), profit, sale_id),
            )

    # A couple of demo expenses
    for desc, amt, days_ago in [("Shop Rent", 12000, 25), ("Electricity Bill", 3200, 10),
                                 ("Staff Wages", 18000, 5)]:
        conn.execute(
            "INSERT INTO expenses (description, amount, created_at) VALUES (?, ?, ?)",
            (desc, amt, (now - timedelta(days=days_ago)).isoformat()),
        )

    # A couple of demo purchase orders already in-flight for the supplier portal demo
    sample_products = random.sample(product_ids, 3)
    statuses = ["pending_supplier", "accepted", "shipped"]
    for pid, status in zip(sample_products, statuses):
        offer = conn.execute(
            "SELECT * FROM supplier_offers WHERE product_id=? ORDER BY price ASC LIMIT 1", (pid,)
        ).fetchone()
        if not offer:
            continue
        qty = random.randint(20, 60)
        total = round(offer["price"] * qty, 2)
        created = (now - timedelta(days=random.randint(1, 4))).isoformat()
        conn.execute(
            """INSERT INTO purchase_orders
               (product_id, supplier_id, qty, unit_price, total, delivery_days, status, reason, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, offer["supplier_id"], qty, offer["price"], total, offer["delivery_days"],
             status, "Restocking based on demand forecast", created, created),
        )


if __name__ == "__main__":
    init_db(reset=True)
    print(f"Database initialized at {DB_PATH}")
