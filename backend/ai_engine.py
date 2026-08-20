"""
SME Anchor AI - "AI Anchor"
A rule-based business-intelligence engine that analyzes the live SQLite
business state (inventory, demand, suppliers, sales, budget) and produces
grounded recommendations. It keeps light conversation memory per session
so follow-up questions like "which supplier is best?" or "prepare the
order" resolve against the product most recently discussed.
"""
import re
from datetime import datetime, timedelta

# In-memory per-session context (last product / recommendation discussed).
# Fine for a single-process demo; would move to a table/cache in production.
SESSION_CONTEXT = {}


def _get_ctx(session_id):
    return SESSION_CONTEXT.setdefault(session_id, {})


def stock_coverage_days(stock, daily_demand):
    if daily_demand <= 0:
        return 999
    return round(stock / daily_demand, 1)


def status_for_coverage(coverage):
    if coverage <= 2:
        return "Critical"
    if coverage <= 5:
        return "Warning"
    return "Healthy"


def get_priority_products(conn, limit=5):
    """Products most urgently needing restock, ranked by lowest coverage."""
    rows = conn.execute("SELECT * FROM products").fetchall()
    scored = []
    for p in rows:
        coverage = stock_coverage_days(p["stock"], p["daily_demand"])
        scored.append((coverage, p))
    scored.sort(key=lambda x: x[0])
    return [p for coverage, p in scored if coverage <= 5][:limit] or [scored[0][1]] if scored else []


def best_offer_for_product(conn, product_id, priority="balanced"):
    """
    Score supplier offers for a product. priority: 'price' | 'speed' | 'balanced'
    Lower score = better. Normalizes price/delivery against the offer set and
    factors in reliability.
    """
    offers = conn.execute(
        """SELECT supplier_offers.*, suppliers.name as supplier_name,
                  suppliers.reliability as reliability, suppliers.rating as rating
           FROM supplier_offers
           JOIN suppliers ON suppliers.id = supplier_offers.supplier_id
           WHERE product_id = ?""",
        (product_id,),
    ).fetchall()
    if not offers:
        return None, []

    prices = [o["price"] for o in offers]
    deliveries = [o["delivery_days"] for o in offers]
    pmin, pmax = min(prices), max(prices)
    dmin, dmax = min(deliveries), max(deliveries)

    def norm(v, lo, hi):
        return 0.0 if hi == lo else (v - lo) / (hi - lo)

    weights = {
        "price": (0.7, 0.15, 0.15),
        "speed": (0.15, 0.7, 0.15),
        "balanced": (0.4, 0.35, 0.25),
    }[priority]

    ranked = []
    for o in offers:
        price_n = norm(o["price"], pmin, pmax)
        delivery_n = norm(o["delivery_days"], dmin, dmax)
        reliability_n = 1 - (o["reliability"] / 100)
        score = weights[0] * price_n + weights[1] * delivery_n + weights[2] * reliability_n
        ranked.append((score, o))
    ranked.sort(key=lambda x: x[0])
    best = ranked[0][1]
    return best, [o for _, o in ranked]


def dashboard_summary(conn):
    business = conn.execute("SELECT * FROM business WHERE id=1").fetchone()
    today = datetime.utcnow().date()
    today_sales = conn.execute(
        "SELECT COALESCE(SUM(total),0) t, COALESCE(SUM(profit),0) p FROM sales WHERE date(created_at)=?",
        (today.isoformat(),),
    ).fetchone()
    products = conn.execute("SELECT * FROM products").fetchall()
    inventory_value = sum(p["price"] * p["stock"] for p in products)
    low_stock = [p for p in products if stock_coverage_days(p["stock"], p["daily_demand"]) <= 2]
    pending_orders = conn.execute(
        "SELECT COUNT(*) c FROM purchase_orders WHERE status NOT IN ('delivered','rejected')"
    ).fetchone()["c"]
    return {
        "available_cash": round(business["cash"], 2),
        "today_sales": round(today_sales["t"], 2),
        "today_profit": round(today_sales["p"], 2),
        "inventory_value": round(inventory_value, 2),
        "pending_orders": pending_orders,
        "low_stock_items": len(low_stock),
    }


def profit_trend_explanation(conn):
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    t = conn.execute(
        "SELECT COALESCE(SUM(profit),0) p FROM sales WHERE date(created_at)=?", (today.isoformat(),)
    ).fetchone()["p"]
    y = conn.execute(
        "SELECT COALESCE(SUM(profit),0) p FROM sales WHERE date(created_at)=?", (yesterday.isoformat(),)
    ).fetchone()["p"]
    diff = t - y
    pct = (diff / y * 100) if y else 0
    return t, y, diff, pct


def top_selling_products(conn, days=7, limit=5):
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT products.name, products.id, SUM(sale_items.qty) as units
           FROM sale_items
           JOIN sales ON sales.id = sale_items.sale_id
           JOIN products ON products.id = sale_items.product_id
           WHERE sales.created_at >= ?
           GROUP BY products.id
           ORDER BY units DESC LIMIT ?""",
        (since, limit),
    ).fetchall()
    return rows


def find_product_by_name(conn, text):
    text_l = text.lower()
    products = conn.execute("SELECT * FROM products").fetchall()
    # exact-ish match first
    for p in products:
        if p["name"].lower() in text_l:
            return p
    # loose token match
    best, best_score = None, 0
    for p in products:
        tokens = set(p["name"].lower().split())
        score = sum(1 for t in tokens if t in text_l)
        if score > best_score:
            best, best_score = p, score
    return best if best_score > 0 else None


def build_purchase_reason(product):
    coverage = stock_coverage_days(product["stock"], product["daily_demand"])
    return (f"Current stock ({product['stock']} units) covers about {coverage} days of demand "
            f"at {product['daily_demand']}/day. Restocking now avoids a stockout.")


def chat(conn, session_id, message):
    ctx = _get_ctx(session_id)
    msg = message.strip()
    msg_l = msg.lower()

    # --- "prepare the order" / confirm action ---
    if re.search(r"\bprepare\b.*\border\b|\bcreate\b.*\border\b", msg_l) or msg_l.strip() in (
        "prepare order", "prepare the order"
    ):
        product = ctx.get("last_product")
        offer = ctx.get("last_offer")
        if not product or not offer:
            return {
                "text": "I don't have a product in mind yet. Ask me something like "
                        "\"what should I purchase today?\" first, then I can prepare the order.",
                "type": "text",
            }
        qty = ctx.get("last_qty", 50)
        total = round(offer["price"] * qty, 2)
        po_preview = {
            "product_id": product["id"],
            "product_name": product["name"],
            "supplier_id": offer["supplier_id"],
            "supplier_name": offer["supplier_name"],
            "qty": qty,
            "unit_price": offer["price"],
            "total": total,
            "delivery_days": offer["delivery_days"],
            "reason": build_purchase_reason(product),
        }
        ctx["pending_po"] = po_preview
        return {
            "text": f"Here is the purchase order preview for {product['name']}.",
            "type": "purchase_order_preview",
            "data": po_preview,
        }

    # --- "which supplier is best for X" ---
    if "supplier" in msg_l and ("best" in msg_l or "compare" in msg_l or "recommend" in msg_l):
        product = find_product_by_name(conn, msg) or ctx.get("last_product")
        if not product:
            return {"text": "Which product's suppliers would you like me to compare?", "type": "text"}
        priority = "speed" if "fast" in msg_l or "quick" in msg_l else (
            "price" if "cheap" in msg_l or "cost" in msg_l else "balanced")
        best, ranked = best_offer_for_product(conn, product["id"], priority)
        if not best:
            return {"text": f"No suppliers currently list offers for {product['name']}.", "type": "text"}
        ctx["last_product"] = dict(product)
        ctx["last_offer"] = dict(best)
        offers_view = [
            {
                "supplier_name": o["supplier_name"], "price": o["price"],
                "delivery_days": o["delivery_days"], "reliability": o["reliability"],
                "is_best": o["supplier_id"] == best["supplier_id"],
            } for o in ranked
        ]
        return {
            "text": f"For {product['name']}, **{best['supplier_name']}** is the best option — "
                    f"₹{best['price']}/unit, {best['delivery_days']}-day delivery, "
                    f"{best['reliability']}% reliability.",
            "type": "supplier_comparison",
            "data": {"product_name": product["name"], "offers": offers_view},
        }

    # --- "which products are running low / low stock" ---
    if "low" in msg_l and "stock" in msg_l or "running low" in msg_l or "what should i purchase" in msg_l \
            or "what to purchase" in msg_l or "restock" in msg_l:
        priority_products = get_priority_products(conn, limit=3)
        if not priority_products:
            return {"text": "All products are currently well stocked. Nothing urgent to purchase today.",
                    "type": "text"}
        top = priority_products[0]
        best, ranked = best_offer_for_product(conn, top["id"])
        ctx["last_product"] = dict(top)
        coverage = stock_coverage_days(top["stock"], top["daily_demand"])
        qty = max(30, int(top["daily_demand"] * 7))
        ctx["last_qty"] = qty
        lines = [f"I found {len(priority_products)} product(s) requiring attention.",
                 f"**{top['name']} is the highest priority.**",
                 f"Current stock: {top['stock']} units",
                 f"Average daily demand: {top['daily_demand']}/day",
                 f"Estimated stock coverage: {coverage} days"]
        data = {
            "priority_products": [
                {"name": p["name"], "stock": p["stock"],
                 "coverage": stock_coverage_days(p["stock"], p["daily_demand"]),
                 "status": status_for_coverage(stock_coverage_days(p["stock"], p["daily_demand"]))}
                for p in priority_products
            ],
            "top_product": top["name"],
        }
        if best:
            ctx["last_offer"] = dict(best)
            data["recommended_supplier"] = best["supplier_name"]
            data["recommended_qty"] = qty
            data["estimated_cost"] = round(best["price"] * qty, 2)
            lines.append(f"\n{best['supplier_name']} can deliver within {best['delivery_days']} day(s) "
                         f"at ₹{best['price']}/unit.")
            lines.append(f"\n**Recommendation:** Purchase {qty} units from {best['supplier_name']}.")
            lines.append(f"Estimated cost: ₹{round(best['price'] * qty, 2)}.")
            lines.append("\nWould you like me to prepare the purchase order?")
        return {"text": "\n".join(lines), "type": "restock_recommendation", "data": data}

    # --- "how are sales today" ---
    if "sales" in msg_l and ("today" in msg_l or "how" in msg_l):
        summary = dashboard_summary(conn)
        return {
            "text": f"Today's sales are ₹{summary['today_sales']:,.2f} with a profit of "
                    f"₹{summary['today_profit']:,.2f} so far.",
            "type": "text",
        }

    # --- "why did my profit decrease" ---
    if "profit" in msg_l and ("why" in msg_l or "decrease" in msg_l or "drop" in msg_l or "down" in msg_l):
        t, y, diff, pct = profit_trend_explanation(conn)
        direction = "decreased" if diff < 0 else "increased"
        return {
            "text": f"Profit {direction} from ₹{y:,.2f} yesterday to ₹{t:,.2f} today "
                    f"({pct:+.1f}%). This mainly tracks lower unit sales and any recent "
                    f"purchase-order spend recorded as cost of goods.",
            "type": "text",
        }

    # --- "top selling products" ---
    if "top" in msg_l and ("selling" in msg_l or "product" in msg_l):
        rows = top_selling_products(conn)
        if not rows:
            return {"text": "No sales recorded yet in the last 7 days.", "type": "text"}
        lines = [f"{i+1}. {r['name']} — {r['units']} units sold (7 days)" for i, r in enumerate(rows)]
        return {"text": "Here are your top-selling products over the last 7 days:\n" + "\n".join(lines),
                "type": "text"}

    # --- generic product mention -> stock lookup, sets context ---
    product = find_product_by_name(conn, msg)
    if product:
        ctx["last_product"] = dict(product)
        coverage = stock_coverage_days(product["stock"], product["daily_demand"])
        return {
            "text": f"{product['name']} currently has {product['stock']} units in stock "
                    f"(about {coverage} days of coverage at current demand).",
            "type": "text",
        }

    return {
        "text": "I can help with restocking decisions, supplier comparisons, sales performance "
                "and purchase orders. Try asking \"What should I purchase today?\" or "
                "\"Which supplier is best for oil?\"",
        "type": "text",
    }
