# SME
Your Business, Anchored by Intelligence." An intelligent operational anchor for small and medium enterprises.

SME Anchor is a complete virtual SME management platform with three connected portals — Owner, Customer, and Supplier — all reading and writing to a single shared business database. A rule-based AI ("SME Anchor AI") analyzes live inventory, demand and supplier data to recommend and prepare purchase orders, which the owner must explicitly approve.

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

PROJECT IS LIVE AT -------> FRONTEND -> sme-fawn.vercel.app
                            BACKEND ->https://sme-tk4o.onrender.com


//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
Customer purchases → Sale recorded → Inventory decreases → Owner dashboard updates
   → AI analyzes the business → Owner approves purchase → Supplier accepts,
   ships, delivers → Inventory increases
1. Tech Stack
Layer	Technology
Backend	Python 3, Flask, Flask-CORS, SQLite (sme_anchor.db)
Frontend	HTML5, vanilla CSS, vanilla JavaScript (no build step)
AI Engine	Rule-based business-intelligence module (ai_engine.py) — no external API key required
Database	Single central SQLite file shared by all three portals
No Node.js, npm, or bundler is required to run the app — the frontend is static HTML/CSS/JS served directly by Flask.

2. Project Structure
sme_anchor/
├── backend/
│   ├── app.py              # Flask app — all REST API routes + static file serving
│   ├── database.py         # SQLite schema + demo-data seeding (70+ products, 5 suppliers...)
│   ├── ai_engine.py        # AI Anchor: recommendations, supplier scoring, chat logic
│   ├── requirements.txt    # Python dependencies
│   └── sme_anchor.db       # SQLite database (auto-created on first run)
├── frontend/
│   ├── index.html          # Login / role-selection screen
│   ├── owner.html          # Owner portal (dashboard, inventory, suppliers, AI dock, etc.)
│   ├── customer.html       # Customer portal (SME Anchor Mart storefront)
│   ├── supplier.html       # Supplier portal (order management)
│   ├── css/style.css       # Light blue + white SaaS design system
│   └── js/
│       ├── api.js          # Shared fetch helpers, formatting, toasts
│       ├── owner.js        # Owner portal logic
│       ├── customer.js     # Customer portal logic
│       └── supplier.js     # Supplier portal logic
└── README.md
3. Setup & Run Procedure
Prerequisites
Python 3.9 or newer
pip
Step-by-step
Unzip the project and open a terminal in the sme_anchor folder.

Create a virtual environment (recommended)

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
Install backend dependencies

cd backend
pip install -r requirements.txt
Run the server

python app.py
On first run, sme_anchor.db is automatically created and seeded with:

89 realistic products across 8 categories
5 suppliers (A–E) with varied pricing, delivery time and reliability
~300 supplier offers
30 days of historical sales
3 in-flight purchase orders (for an instant supplier-portal demo)
Open the app Go to http://localhost:5000 in your browser. That's it — the Flask server serves both the API (/api/...) and the frontend from the same process, so there's nothing else to start.

Reset demo data at any time From the Owner portal, go to Settings → Reset Demo Data, or call:

curl -X POST http://localhost:5000/api/admin/reset
4. The Main Demo Story (matches the product brief)
Log in as Customer on the login screen.
Browse categories, add a few products to the cart, and Checkout — a digital invoice is generated and the sale is recorded.
Log out and log in as Owner. The dashboard now reflects the updated Today's Sales, Today's Profit and Inventory Value.
Open AI Anchor (docked at the bottom of the Owner portal) and ask:
"What should I purchase today?"

The AI analyzes inventory, demand, and the 5 suppliers, and recommends a product, quantity and supplier with an estimated cost.
Click Prepare Order in the AI reply, review the purchase-order preview, then click Approve Purchase.
Log out and log in as Supplier, selecting the recommended supplier (e.g. Supplier C) from the dropdown.
In Orders, the supplier sees the new purchase order: Accept Order → Mark as Shipped → Mark as Delivered.
Log back in as Owner. Inventory has automatically increased and the dashboard/finance figures reflect the delivery cost.
5. Key API Endpoints (backend/app.py)
Method	Endpoint	Purpose
GET	/api/dashboard	Owner KPI summary
GET	/api/sales/chart?range=today|7d|30d	Sales trend for the chart
GET	/api/products	Paginated/searchable product catalog
GET	/api/products/<id>/offers	Supplier comparison for one product
GET	/api/inventory	Stock, coverage days and status per item
POST	/api/checkout	Customer checkout → sale + inventory update
GET	/api/suppliers / /api/suppliers/<id>/dashboard	Supplier list / supplier KPIs
POST	/api/purchase-orders	Owner creates a manual purchase order
POST	/api/purchase-orders/<id>/approve	Owner approves → sent to supplier
POST	/api/purchase-orders/<id>/supplier-accept	Supplier accepts the order
POST	/api/purchase-orders/<id>/ship	Supplier marks shipped
POST	/api/purchase-orders/<id>/deliver	Supplier marks delivered → inventory ↑
POST	/api/ai/chat	AI Anchor conversational endpoint
POST	/api/ai/confirm-purchase	Owner approves a PO the AI prepared in-chat
POST	/api/admin/reset	Reset all demo data
Purchase-order lifecycle: pending_approval → pending_supplier → accepted → shipped → delivered (owner can reject at pending_approval; supplier can supplier-reject at pending_supplier). Inventory only increases at delivered, exactly as specified in the product brief.

6. AI Anchor — How It Works
ai_engine.py implements a deterministic, explainable business-intelligence layer (no external LLM calls, so the demo works fully offline):

Stock coverage = current stock ÷ average daily demand → drives Healthy / Warning / Critical status.
Supplier scoring normalizes price, delivery time and reliability into a single weighted score to pick the best offer (balanced, price, or speed priority, inferred from the question).
Conversation memory is kept per session (session_id) so follow-ups like "which supplier is best?" or "prepare the order" resolve against the product most recently discussed — matching the "AI conversation memory" requirement in the brief.
The AI never finalizes a purchase — it only prepares a purchase-order preview; the Owner must click Approve Purchase.
7. Design System
Light blue + white professional SaaS palette (see frontend/css/style.css): white backgrounds, soft blue cards, blue primary buttons (#2f7fe0), dark navy text (#10233f), green/orange/red used only for status meaning, subtle shadows and rounded corners throughout. Sidebar collapses and tables scroll horizontally on smaller screens.

8. Notes & Limitations (demo scope)
Single-process Flask dev server — fine for a hackathon/college demo, not for production (see the Flask console warning).
The AI is intentionally rule-based, not an LLM call, so the whole demo runs with zero API keys and no internet dependency.
Customer login is simplified to a single demo customer for checkout; the customers table and endpoint exist for the Owner portal's Customers view.
