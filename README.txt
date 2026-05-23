═══════════════════════════════════════════════════════════════
  AGORA FM — Python Backend Demo
  Setup & Run Instructions
═══════════════════════════════════════════════════════════════

QUICK START
───────────
1. Put all files in one folder (agora-fm-demo/)
2. Open Terminal / Command Prompt in that folder
3. Install dependencies (one time only):
     pip install flask weasyprint
4. Run the server:
     python app.py
5. Open browser: http://localhost:5000

That's it. Leave the terminal open while using the demo.

⚠️  Do NOT open index.html by double-clicking.
    Always use http://localhost:5000


FOLDER STRUCTURE
────────────────
agora-fm-demo/
├── app.py                     ← Flask backend (RUN THIS)
├── requirements.txt           ← pip dependencies
├── agora_fm.css
├── db.js                      ← API client (talks to Flask)
├── nav-auth.js
├── basket.js
├── payment-demo.js
├── index.html
├── registration.html
├── service_providers.html
├── payment.html
├── dashboard.html
├── supplier_registration.html
├── supplier_dashboard.html
├── provider_profile.html
└── README.txt

agora.db is created automatically on first run.


DEMO CREDENTIALS
────────────────
CUSTOMER
  Email:    customer@demo.com
  Password: Demo123!
  → Lands on: dashboard.html

SUPPLIER (Apollo Fire Technicians)
  Email:    enquiries@apollofire.co.uk
  Password: Apollo123!
  → Lands on: supplier_dashboard.html

Other seed suppliers:
  info@aquasafe-testing.co.uk     / Aqua456!
  contracts@voltcompliance.co.uk  / Volt789!
  service@britheat.co.uk          / BritHeat1!
  hello@pureairhvac.co.uk         / PureAir2!


DEMO WALKTHROUGH
────────────────
1. Open http://localhost:5000
2. Sign in as customer@demo.com / Demo123!
3. Click "Find Providers" → browse the marketplace
4. Click "🛒 Commission" on any provider card
   → Basket panel slides in
5. Add more services, then "Proceed to Payment →"
6. Click "🤝 Click to Handshake"
   → Agreement timestamped, payment unlocks
7. Enter card details and "Complete Payment →"
   → Order saved to agora.db
8. Footer → ⚙ View DB to inspect live database


DATABASE
────────
  File:     agora.db (SQLite, created automatically)
  Tables:   customers, suppliers, baskets, orders
  View:     Footer → ⚙ View DB (any page)
  Reset:    Footer → ⚙ View DB → Reset DB
  Console:  python3 -c "import sqlite3; ..."

PDF PURCHASE ORDERS
───────────────────
  With weasyprint installed: real PDF downloaded on order
  Without weasyprint: HTML version shown in browser
  Install: pip install weasyprint


COMMISSION RATE
───────────────
  5% Agora FM commission — charged to service providers.
  Customers pay: Subtotal + VAT (20%) only.


═══════════════════════════════════════════════════════════════
  Agora FM — Master Project v6.0
═══════════════════════════════════════════════════════════════
