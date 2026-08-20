"""
SME Anchor - Flask backend
Serves the REST API used by the Owner, Customer and Supplier portals, and
serves the static frontend. Single central SQLite database (sme_anchor.db)
shared by all three portals, as required by the product spec.
"""
import os
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import database as db
import ai_engine

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

db.init_db()


def row_to_dict(row):
    return {k: row[k] for k in row.keys()} if row else None


def rows_to_list(rows):
    return [row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    full = os.path.join(FRONTEND_DIR, path)
    if os.path.exists(full):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")


# ---------------------------------------------------------------------------
# Dashboard / KPIs
# ---------------------------------------------------------------------------
@app.route("/api/dashboard")
def api_dashboard():
    conn = db.get_connection()
    summary = ai_engine.dashboard_summary(conn)
    conn.close()
    return jsonify(summary)


@app.route("/api/sales/chart")
def api_sales_chart():
    range_param = request.args.get("range", "7d")
    days = {"today": 1, "7d": 7, "30d": 30}.get(range_param, 7)
    conn = db.get_connection()
    since = (datetime.utcnow() - timedelta(days=days)).date()
    rows = conn.execute(
        """SELECT date(created_at) as day, COALESCE(SUM(total),0) as sales,
                  COALESCE(SUM(profit),0) as profit
           FROM sales WHERE date(created_at) >= ?
           GROUP BY date(created_at) ORDER BY day ASC""",
        (since.isoformat(),),
    ).fetchall()
    series = rows_to_list(rows)

    prev_since = (datetime.utcnow() - timedelta(days=days * 2)).date()
    prev_until = since
    prev_total = conn.execute(
        "SELECT COALESCE(SUM(total),0) t FROM sales WHERE date(created_at) >= ? AND date(created_at) < ?",
        (prev_since.isoformat(), prev_until.isoformat()),
    ).fetchone()["t"]
    current_total = sum(r["sales"] for r in series)
    change_pct = ((current_total - prev_total) / prev_total * 100) if prev_total else 0
    conn.close()
    return jsonify({"series": series, "change_pct": round(change_pct, 1), "range": range_param})


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
@app.route("/api/products")
def api_products():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "name")
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 12))

    conn = db.get_connection()
    where, params = [], []
    if q:
        where.append("name LIKE ?")
        params.append(f"%{q}%")
    if category:
        where.append("category = ?")
        params.append(category)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    order_sql = {
        "price_asc": "price ASC", "price_desc": "price DESC",
        "rating": "rating DESC", "name": "name ASC",
    }.get(sort, "name ASC")

    total = conn.execute(f"SELECT COUNT(*) c FROM products {where_sql}", params).fetchone()["c"]
    rows = conn.execute(
        f"SELECT * FROM products {where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    categories = [r["category"] for r in conn.execute("SELECT DISTINCT category FROM products").fetchall()]
    conn.close()
    return jsonify({
        "items": rows_to_list(rows), "total": total, "page": page,
        "page_size": page_size, "categories": categories,
    })


@app.route("/api/products/<int:product_id>")
def api_product_detail(product_id):
    conn = db.get_connection()
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    if not product:
        return jsonify({"error": "not found"}), 404
    return jsonify(row_to_dict(product))


@app.route("/api/products/<int:product_id>/offers")
def api_product_offers(product_id):
    conn = db.get_connection()
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product:
        conn.close()
        return jsonify({"error": "not found"}), 404
    best, ranked = ai_engine.best_offer_for_product(conn, product_id)
    conn.close()
    return jsonify({
        "product": row_to_dict(product),
        "offers": rows_to_list(ranked),
        "best_offer_id": best["id"] if best else None,
    })


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
@app.route("/api/inventory")
def api_inventory():
    conn = db.get_connection()
    products = conn.execute("SELECT * FROM products ORDER BY name ASC").fetchall()
    conn.close()
    items = []
    for p in products:
        coverage = ai_engine.stock_coverage_days(p["stock"], p["daily_demand"])
        d = row_to_dict(p)
        d["coverage_days"] = coverage
        d["status"] = ai_engine.status_for_coverage(coverage)
        items.append(d)
    return jsonify({"items": items})


# ---------------------------------------------------------------------------
# Customer checkout
# ---------------------------------------------------------------------------
@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    payload = request.get_json(force=True)
    customer_id = payload.get("customer_id", 1)
    cart = payload.get("cart", [])  # [{product_id, qty}]
    if not cart:
        return jsonify({"error": "cart is empty"}), 400

    conn = db.get_connection()
    subtotal, cost_total, items_out = 0, 0, []
    for item in cart:
        product = conn.execute("SELECT * FROM products WHERE id=?", (item["product_id"],)).fetchone()
        if not product:
            continue
        qty = min(item["qty"], product["stock"])
        if qty <= 0:
            continue
        unit_price = product["price"]
        subtotal += unit_price * qty
        cost_total += unit_price * 0.65 * qty
        items_out.append({"product_id": product["id"], "name": product["name"], "qty": qty, "unit_price": unit_price})
        conn.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, product["id"]))

    if not items_out:
        conn.close()
        return jsonify({"error": "no valid items / insufficient stock"}), 400

    tax = round(subtotal * 0.05, 2)
    total = round(subtotal + tax, 2)
    profit = round(total - cost_total - tax, 2)
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        """INSERT INTO sales (customer_id, subtotal, tax, total, cost_of_goods, profit, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (customer_id, round(subtotal, 2), tax, total, round(cost_total, 2), profit, now),
    )
    sale_id = cur.lastrowid
    for it in items_out:
        conn.execute(
            "INSERT INTO sale_items (sale_id, product_id, qty, unit_price) VALUES (?, ?, ?, ?)",
            (sale_id, it["product_id"], it["qty"], it["unit_price"]),
        )
    conn.execute("UPDATE business SET cash = cash + ? WHERE id=1", (total,))
    conn.commit()
    business = conn.execute("SELECT * FROM business WHERE id=1").fetchone()
    conn.close()

    return jsonify({
        "invoice": {
            "id": f"INV-{1000 + sale_id}",
            "sale_id": sale_id,
            "items": items_out,
            "subtotal": round(subtotal, 2),
            "tax": tax,
            "total": total,
            "created_at": now,
        },
        "available_cash": business["cash"],
        "message": "Sale recorded successfully.",
    })


@app.route("/api/customers")
def api_customers():
    conn = db.get_connection()
    rows = conn.execute("SELECT * FROM customers ORDER BY name ASC").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------
@app.route("/api/suppliers")
def api_suppliers():
    conn = db.get_connection()
    rows = conn.execute("SELECT * FROM suppliers ORDER BY name ASC").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route("/api/suppliers/<int:supplier_id>/dashboard")
def api_supplier_dashboard(supplier_id):
    conn = db.get_connection()
    supplier = conn.execute("SELECT * FROM suppliers WHERE id=?", (supplier_id,)).fetchone()
    if not supplier:
        conn.close()
        return jsonify({"error": "not found"}), 404

    counts = {}
    for status in ["pending_approval", "pending_supplier", "accepted", "shipped", "delivered", "rejected"]:
        counts[status] = conn.execute(
            "SELECT COUNT(*) c FROM purchase_orders WHERE supplier_id=? AND status=?",
            (supplier_id, status),
        ).fetchone()["c"]

    today = datetime.utcnow().date().isoformat()
    today_orders = conn.execute(
        "SELECT COUNT(*) c FROM purchase_orders WHERE supplier_id=? AND date(created_at)=?",
        (supplier_id, today),
    ).fetchone()["c"]

    revenue = conn.execute(
        "SELECT COALESCE(SUM(total),0) t FROM purchase_orders WHERE supplier_id=? AND status='delivered'",
        (supplier_id,),
    ).fetchone()["t"]

    products_supplied = conn.execute(
        """SELECT COUNT(DISTINCT product_id) c FROM supplier_offers WHERE supplier_id=?""",
        (supplier_id,),
    ).fetchone()["c"]

    conn.close()
    return jsonify({
        "supplier": row_to_dict(supplier),
        "today_orders": today_orders,
        "status_counts": counts,
        "revenue": round(revenue, 2),
        "products_supplied": products_supplied,
    })


# ---------------------------------------------------------------------------
# Purchase Orders
# ---------------------------------------------------------------------------
@app.route("/api/purchase-orders", methods=["GET"])
def api_list_pos():
    supplier_id = request.args.get("supplier_id")
    status = request.args.get("status")
    conn = db.get_connection()
    where, params = [], []
    if supplier_id:
        where.append("purchase_orders.supplier_id = ?")
        params.append(supplier_id)
    if status:
        where.append("purchase_orders.status = ?")
        params.append(status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    rows = conn.execute(
        f"""SELECT purchase_orders.*, products.name as product_name, suppliers.name as supplier_name
            FROM purchase_orders
            JOIN products ON products.id = purchase_orders.product_id
            JOIN suppliers ON suppliers.id = purchase_orders.supplier_id
            {where_sql}
            ORDER BY purchase_orders.created_at DESC""",
        params,
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route("/api/purchase-orders", methods=["POST"])
def api_create_po():
    payload = request.get_json(force=True)
    product_id = payload["product_id"]
    supplier_id = payload["supplier_id"]
    qty = int(payload["qty"])
    reason = payload.get("reason", "Manual purchase by owner.")
    auto_approve = payload.get("auto_approve", False)

    conn = db.get_connection()
    offer = conn.execute(
        "SELECT * FROM supplier_offers WHERE product_id=? AND supplier_id=?",
        (product_id, supplier_id),
    ).fetchone()
    if not offer:
        conn.close()
        return jsonify({"error": "no offer from this supplier for this product"}), 400

    total = round(offer["price"] * qty, 2)
    now = datetime.utcnow().isoformat()
    status = "accepted" if auto_approve else "pending_approval"
    cur = conn.execute(
        """INSERT INTO purchase_orders
           (product_id, supplier_id, qty, unit_price, total, delivery_days, status, reason, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (product_id, supplier_id, qty, offer["price"], total, offer["delivery_days"], status, reason, now, now),
    )
    conn.commit()
    po = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(po)), 201


def _update_po_status(po_id, new_status, allowed_from):
    conn = db.get_connection()
    po = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (po_id,)).fetchone()
    if not po:
        conn.close()
        return None, ("not found", 404)
    if po["status"] not in allowed_from:
        conn.close()
        return None, (f"cannot move from {po['status']} to {new_status}", 400)

    now = datetime.utcnow().isoformat()
    conn.execute("UPDATE purchase_orders SET status=?, updated_at=? WHERE id=?", (new_status, now, po_id))

    if new_status == "delivered":
        conn.execute("UPDATE products SET stock = stock + ? WHERE id=?", (po["qty"], po["product_id"]))
        conn.execute("UPDATE business SET cash = cash - ? WHERE id=1", (po["total"],))

    conn.commit()
    updated = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (po_id,)).fetchone()
    conn.close()
    return row_to_dict(updated), None


@app.route("/api/purchase-orders/<int:po_id>/approve", methods=["POST"])
def api_po_approve(po_id):
    """Owner approves the order; it is then sent to the supplier for their own accept/reject."""
    updated, err = _update_po_status(po_id, "pending_supplier", {"pending_approval"})
    if err:
        return jsonify({"error": err[0]}), err[1]
    return jsonify(updated)


@app.route("/api/purchase-orders/<int:po_id>/reject", methods=["POST"])
def api_po_reject(po_id):
    updated, err = _update_po_status(po_id, "rejected", {"pending_approval"})
    if err:
        return jsonify({"error": err[0]}), err[1]
    return jsonify(updated)


@app.route("/api/purchase-orders/<int:po_id>/supplier-accept", methods=["POST"])
def api_po_supplier_accept(po_id):
    updated, err = _update_po_status(po_id, "accepted", {"pending_supplier"})
    if err:
        return jsonify({"error": err[0]}), err[1]
    return jsonify(updated)


@app.route("/api/purchase-orders/<int:po_id>/supplier-reject", methods=["POST"])
def api_po_supplier_reject(po_id):
    updated, err = _update_po_status(po_id, "rejected", {"pending_supplier"})
    if err:
        return jsonify({"error": err[0]}), err[1]
    return jsonify(updated)


@app.route("/api/purchase-orders/<int:po_id>/ship", methods=["POST"])
def api_po_ship(po_id):
    updated, err = _update_po_status(po_id, "shipped", {"accepted"})
    if err:
        return jsonify({"error": err[0]}), err[1]
    return jsonify(updated)


@app.route("/api/purchase-orders/<int:po_id>/deliver", methods=["POST"])
def api_po_deliver(po_id):
    updated, err = _update_po_status(po_id, "delivered", {"shipped", "accepted"})
    if err:
        return jsonify({"error": err[0]}), err[1]
    return jsonify(updated)


# ---------------------------------------------------------------------------
# AI Anchor chat
# ---------------------------------------------------------------------------
@app.route("/api/ai/chat", methods=["POST"])
def api_ai_chat():
    payload = request.get_json(force=True)
    session_id = payload.get("session_id", "default")
    message = payload.get("message", "")
    if not message.strip():
        return jsonify({"error": "message required"}), 400

    conn = db.get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO ai_messages (session_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
        (session_id, message, now),
    )
    reply = ai_engine.chat(conn, session_id, message)
    conn.execute(
        "INSERT INTO ai_messages (session_id, role, content, created_at) VALUES (?, 'ai', ?, ?)",
        (session_id, reply["text"], now),
    )
    conn.commit()
    conn.close()
    return jsonify(reply)


@app.route("/api/ai/history")
def api_ai_history():
    session_id = request.args.get("session_id", "default")
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT * FROM ai_messages WHERE session_id=? ORDER BY id ASC", (session_id,)
    ).fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route("/api/ai/confirm-purchase", methods=["POST"])
def api_ai_confirm_purchase():
    """Owner approves a purchase order that AI Anchor prepared in-chat."""
    payload = request.get_json(force=True)
    session_id = payload.get("session_id", "default")
    ctx = ai_engine._get_ctx(session_id)
    po_preview = ctx.get("pending_po")
    if not po_preview:
        return jsonify({"error": "no pending AI purchase order for this session"}), 400

    conn = db.get_connection()
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        """INSERT INTO purchase_orders
           (product_id, supplier_id, qty, unit_price, total, delivery_days, status, reason, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending_supplier', ?, ?, ?)""",
        (po_preview["product_id"], po_preview["supplier_id"], po_preview["qty"], po_preview["unit_price"],
         po_preview["total"], po_preview["delivery_days"], po_preview["reason"], now, now),
    )
    conn.commit()
    po = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    ctx.pop("pending_po", None)
    return jsonify(row_to_dict(po))


# ---------------------------------------------------------------------------
# Reset (demo convenience)
# ---------------------------------------------------------------------------
@app.route("/api/admin/reset", methods=["POST"])
def api_reset():
    db.init_db(reset=True)
    ai_engine.SESSION_CONTEXT.clear()
    return jsonify({"message": "Database reset with fresh demo data."})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
