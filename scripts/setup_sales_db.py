"""Script to create and populate the sales.db SQLite database with sample data."""

import os
import random
import sqlite3
from datetime import datetime, timedelta

from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

# Configuration
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "sales.db")

NUM_CUSTOMERS = 500
NUM_PRODUCTS = 50
NUM_ORDERS = 1500

REGIONS = ["North", "South", "East", "West"]
SEGMENTS = ["Consumer", "Corporate", "Home Office"]

PRODUCT_CATALOG = {
    "Technology": [
        "Laptop", "Desktop Monitor", "Wireless Mouse", "Mechanical Keyboard", "USB-C Hub",
        "External SSD", "Webcam", "Bluetooth Headset", "Tablet", "Smartphone",
        "Smartwatch", "Router", "Printer", "Graphics Card", "RAM Module",
        "Power Bank", "USB Flash Drive",
    ],
    "Furniture": [
        "Standing Desk", "Ergonomic Chair", "Bookshelf", "Filing Cabinet", "Conference Table",
        "Desk Lamp", "Monitor Stand", "Whiteboard", "Office Sofa", "Storage Unit",
        "Side Table", "Coat Rack", "Room Divider", "Footrest",
    ],
    "Office Supplies": [
        "Notebook Set", "Pen Pack", "Stapler", "Paper Ream", "Binder Clips",
        "Sticky Notes", "Highlighter Set", "Tape Dispenser", "Scissors", "Envelope Pack",
        "Label Maker", "Paper Shredder", "Calculator", "Desk Organizer",
        "Whiteboard Markers", "Correction Tape", "Glue Stick", "Rubber Bands", "Push Pins",
    ],
}


def create_tables(conn: sqlite3.Connection) -> None:
    """Create the database tables."""
    cursor = conn.cursor()
    cursor.executescript("""
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            region TEXT NOT NULL,
            segment TEXT NOT NULL
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            order_date TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE order_items (
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
    """)
    conn.commit()


def populate_customers(conn: sqlite3.Connection) -> None:
    """Insert sample customers."""
    cursor = conn.cursor()
    customers = []
    for i in range(1, NUM_CUSTOMERS + 1):
        customers.append((
            i,
            fake.name(),
            random.choice(REGIONS),
            random.choice(SEGMENTS),
        ))
    cursor.executemany("INSERT INTO customers (id, name, region, segment) VALUES (?, ?, ?, ?)", customers)
    conn.commit()
    print(f"  ✓ Inserted {len(customers)} customers")


def populate_products(conn: sqlite3.Connection) -> list[tuple]:
    """Insert sample products and return them for use in order_items."""
    cursor = conn.cursor()
    products = []
    product_id = 1

    for category, names in PRODUCT_CATALOG.items():
        selected = random.sample(names, min(len(names), NUM_PRODUCTS // 3 + 1))
        for name in selected:
            if category == "Technology":
                price = round(random.uniform(29.99, 1999.99), 2)
            elif category == "Furniture":
                price = round(random.uniform(49.99, 899.99), 2)
            else:
                price = round(random.uniform(2.99, 149.99), 2)
            products.append((product_id, name, category, price))
            product_id += 1

    cursor.executemany("INSERT INTO products (id, name, category, price) VALUES (?, ?, ?, ?)", products)
    conn.commit()

    # Add a few products that will NEVER be ordered (for evaluation queries)
    never_ordered = [
        (product_id, "Discontinued Fax Machine", "Technology", 299.99),
        (product_id + 1, "Antique Typewriter", "Office Supplies", 499.99),
        (product_id + 2, "VR Meeting Pod", "Furniture", 3499.99),
    ]
    cursor.executemany("INSERT INTO products (id, name, category, price) VALUES (?, ?, ?, ?)", never_ordered)
    conn.commit()

    print(f"  ✓ Inserted {len(products) + len(never_ordered)} products ({len(never_ordered)} never-ordered)")
    return products  # Return only orderable products


def populate_orders_and_items(conn: sqlite3.Connection, products: list[tuple]) -> None:
    """Insert sample orders and order_items."""
    cursor = conn.cursor()
    orders = []
    order_items = []

    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)
    date_range = (end_date - start_date).days

    for order_id in range(1, NUM_ORDERS + 1):
        customer_id = random.randint(1, NUM_CUSTOMERS)
        order_date = start_date + timedelta(days=random.randint(0, date_range))

        # Each order has 1-5 items
        num_items = random.randint(1, 5)
        selected_products = random.sample(products, min(num_items, len(products)))

        total_amount = 0.0
        for product in selected_products:
            prod_id, _, _, price = product
            quantity = random.randint(1, 10)
            item_total = price * quantity
            total_amount += item_total
            order_items.append((order_id, prod_id, quantity))

        total_amount = round(total_amount, 2)
        orders.append((order_id, customer_id, total_amount, order_date.strftime("%Y-%m-%d")))

    cursor.executemany(
        "INSERT INTO orders (id, customer_id, amount, order_date) VALUES (?, ?, ?, ?)",
        orders,
    )
    cursor.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity) VALUES (?, ?, ?)",
        order_items,
    )
    conn.commit()
    print(f"  ✓ Inserted {len(orders)} orders")
    print(f"  ✓ Inserted {len(order_items)} order items")


def main() -> None:
    """Create and populate the sales database."""
    os.makedirs(DB_DIR, exist_ok=True)

    # Remove existing database to start fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    print(f"Creating database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    try:
        print("Creating tables...")
        create_tables(conn)

        print("Populating data...")
        populate_customers(conn)
        products = populate_products(conn)
        populate_orders_and_items(conn, products)

        # Verify counts
        cursor = conn.cursor()
        for table in ["customers", "products", "orders", "order_items"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            count = cursor.fetchone()[0]
            print(f"  → {table}: {count} rows")

        print(f"\n✅ Database created successfully at: {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
