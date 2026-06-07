"""
AGORA FM — Flask Backend (app.py)
Run:  python app.py
Open: http://localhost:5000

Database: Uses PostgreSQL on Railway (DATABASE_URL env var) or SQLite locally.
"""
import os, json, hashlib, secrets, datetime, io
from flask import Flask, request, jsonify, session, send_from_directory, send_file, g

WEASYPRINT_OK   = False   # Removed — do not re-enable
COMMISSION_RATE = 0.05
VAT_RATE        = 0.20

# ── Database mode detection ──────────────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'agora.db')   # SQLite only (local dev)

app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
app.secret_key = 'agora-fm-demo-secret-key-2026'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ── DB helpers ──────────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        if USE_POSTGRES:
            g.db = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            g.db = sqlite3.connect(DB_PATH)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        try: db.close()
        except: pass

def _pg_sql(sql):
    """Convert SQLite ? placeholders to PostgreSQL %s."""
    return sql.replace('?', '%s') if USE_POSTGRES else sql

def query(sql, params=(), one=False):
    db  = get_db()
    cur = db.cursor()
    cur.execute(_pg_sql(sql), params)
    db.commit()
    rows = [dict(r) for r in cur.fetchall()]
    return (rows[0] if rows else None) if one else rows

def execute(sql, params=()):
    db  = get_db()
    cur = db.cursor()
    cur.execute(_pg_sql(sql), params)
    db.commit()
    return getattr(cur, 'lastrowid', None)

def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()
def uid():      return secrets.token_hex(5)
def now():      return datetime.datetime.utcnow().isoformat()

# ── Static files ────────────────────────────────────────────────────────────
@app.route('/')
def index(): return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:f>')
def static_files(f): return send_from_directory(BASE_DIR, f)

# ── AUTH ────────────────────────────────────────────────────────────────────
@app.route('/api/auth/login', methods=['POST'])
def login():
    d  = request.json or {}
    em = (d.get('email') or '').strip().lower()
    pw = hash_pw(d.get('password') or '')
    if not em: return jsonify(ok=False, error='Email required.'), 400

    u = query('SELECT * FROM customers WHERE LOWER(email)=? AND password_hash=?', (em, pw), one=True)
    if u:
        session.update(user_id=u['id'], user_type='customer', email=u['email'],
                       name=u['first_name']+' '+u['last_name'], org=u['org_name'])
        return jsonify(ok=True, session=_sess())

    u = query('SELECT * FROM suppliers WHERE LOWER(email)=? AND password_hash=?', (em, pw), one=True)
    if u:
        session.update(user_id=u['id'], user_type='supplier', email=u['email'],
                       name=u['contact_first']+' '+u['contact_last'], org=u['company_name'])
        return jsonify(ok=True, session=_sess())

    return jsonify(ok=False, error='Invalid email or password.'), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear(); return jsonify(ok=True)

@app.route('/api/auth/session')
def get_session():
    if 'user_id' in session:
        return jsonify(loggedIn=True, **_sess())
    return jsonify(loggedIn=False)

def _sess():
    return dict(userId=session.get('user_id'), type=session.get('user_type'),
                email=session.get('email'), name=session.get('name'), org=session.get('org'))

# ── CUSTOMERS ───────────────────────────────────────────────────────────────
@app.route('/api/customers/register', methods=['POST'])
def register_customer():
    d  = request.json or {}
    em = (d.get('email') or '').strip().lower()
    if not em: return jsonify(ok=False, error='Email required.'), 400
    if query('SELECT id FROM customers WHERE LOWER(email)=?', (em,), one=True):
        return jsonify(ok=False, error='Email already registered.'), 409

    cid = 'cust_' + uid()
    execute('''INSERT INTO customers
        (id,org_name,org_type,reg_address,phone,first_name,last_name,job_title,email,password_hash,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (
        cid, d.get('orgName','').strip(), d.get('orgType',''),
        d.get('regAddress','').strip(), d.get('phone','').strip(),
        d.get('firstName','').strip(), d.get('lastName','').strip(),
        d.get('jobTitle','').strip(), em, hash_pw(d.get('password','')), now()
    ))
    session.update(user_id=cid, user_type='customer', email=em,
                   name=d.get('firstName','').strip()+' '+d.get('lastName','').strip(),
                   org=d.get('orgName','').strip())
    return jsonify(ok=True, id=cid)

# ── SUPPLIERS ───────────────────────────────────────────────────────────────
@app.route('/api/suppliers/register', methods=['POST'])
def register_supplier():
    d  = request.json or {}
    em = (d.get('email') or '').strip().lower()
    if not em: return jsonify(ok=False, error='Email required.'), 400
    if query('SELECT id FROM suppliers WHERE LOWER(email)=?', (em,), one=True):
        return jsonify(ok=False, error='Email already registered.'), 409

    sid = 'sup_' + uid()
    execute('''INSERT INTO suppliers
        (id,company_name,company_reg,reg_address,main_tel,website,contact_first,contact_last,
         contact_role,email,password_hash,coverage,categories,accreditations,pl_insurance,
         el_insurance,bank_name,sort_code,account_num,company_desc,verified,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
        sid, d.get('companyName','').strip(), d.get('companyReg','').strip(),
        d.get('regAddress','').strip(), d.get('mainTel','').strip(), d.get('website','').strip(),
        d.get('contactFirst','').strip(), d.get('contactLast','').strip(), d.get('contactRole','').strip(),
        em, hash_pw(d.get('password','')), d.get('coverage',''),
        json.dumps(d.get('categories',[])), json.dumps(d.get('accreditations',[])),
        d.get('plInsurance',''), d.get('elInsurance',''), d.get('bankName','').strip(),
        d.get('sortCode','').strip(), d.get('accountNum','').strip(), d.get('companyDesc','').strip(),
        0, now()
    ))
    session.update(user_id=sid, user_type='supplier', email=em,
                   name=d.get('contactFirst','').strip()+' '+d.get('contactLast','').strip(),
                   org=d.get('companyName','').strip())
    return jsonify(ok=True, id=sid)

@app.route('/api/suppliers')
def get_suppliers():
    rows = query('SELECT * FROM suppliers WHERE verified=1 ORDER BY company_name')
    for r in rows:
        r['categories']     = json.loads(r.get('categories') or '[]')
        r['accreditations'] = json.loads(r.get('accreditations') or '[]')
        for k in ('password_hash','bank_name','sort_code','account_num'): r.pop(k, None)
    return jsonify(rows)

@app.route('/api/suppliers/<sid>/services')
def get_supplier_services(sid):
    rows = query('SELECT * FROM services WHERE supplier_id=? AND active=1 ORDER BY id', (sid,))
    out = []
    for r in rows:
        out.append({
            'id':            r['id'],
            'supplier_id':   r['supplier_id'],
            'name':          r['name'],
            'description':   r['description'],
            'unit_label':    r['unit_label'],
            'unit_price':    r['unit_price_pennies'] / 100,
            'unit_price_pennies': r['unit_price_pennies'],
        })
    return jsonify(out)


@app.route('/api/suppliers/<sid>')
def get_supplier(sid):
    r = query('SELECT * FROM suppliers WHERE id=?', (sid,), one=True)
    if not r: return jsonify(error='Not found'), 404
    r['categories']     = json.loads(r.get('categories') or '[]')
    r['accreditations'] = json.loads(r.get('accreditations') or '[]')
    for k in ('password_hash','bank_name','sort_code','account_num'): r.pop(k, None)
    return jsonify(r)

# ── BASKET ──────────────────────────────────────────────────────────────────
def _get_basket():
    uid_ = session.get('user_id')
    if not uid_: return {'items': []}
    row = query('SELECT items FROM baskets WHERE user_id=?', (uid_,), one=True)
    return {'items': json.loads(row['items']) if row else []}

def _save_basket(items):
    uid_ = session.get('user_id')
    if not uid_: return
    if query('SELECT user_id FROM baskets WHERE user_id=?', (uid_,), one=True):
        execute('UPDATE baskets SET items=?,updated_at=? WHERE user_id=?', (json.dumps(items), now(), uid_))
    else:
        execute('INSERT INTO baskets(user_id,items,updated_at) VALUES(?,?,?)', (uid_, json.dumps(items), now()))

def _totals(items):
    sub  = sum(float(i.get('price',0)) * int(i.get('qty',1)) for i in items)
    vat  = round(sub * VAT_RATE, 2)
    comm = round(sub * COMMISSION_RATE, 2)
    return {'subtotal': round(sub,2), 'vat': vat, 'commission': comm, 'total': round(sub+vat,2)}

@app.route('/api/basket')
def basket_get():
    b = _get_basket(); t = _totals(b['items'])
    return jsonify(**b, **t, count=len(b['items']))

@app.route('/api/basket/add', methods=['POST'])
def basket_add():
    if 'user_id' not in session: return jsonify(ok=False, error='Sign in first.'), 401
    item = request.json or {}
    b = _get_basket()
    if not any(i['id'] == item['id'] for i in b['items']):
        item.setdefault('qty', 1); item['addedAt'] = now()
        b['items'].append(item); _save_basket(b['items'])
        return jsonify(ok=True, added=True, count=len(b['items']))
    return jsonify(ok=True, added=False, count=len(b['items']))

@app.route('/api/basket/item/<item_id>', methods=['DELETE'])
def basket_remove(item_id):
    b = _get_basket()
    b['items'] = [i for i in b['items'] if i['id'] != item_id]
    _save_basket(b['items']); return jsonify(ok=True, count=len(b['items']))

@app.route('/api/basket/qty', methods=['PUT'])
def basket_qty():
    d = request.json or {}; b = _get_basket()
    for i in b['items']:
        if i['id'] == d.get('id'): i['qty'] = max(1, int(d.get('qty',1))); break
    _save_basket(b['items']); return jsonify(ok=True)

@app.route('/api/basket/clear', methods=['POST'])
def basket_clear():
    _save_basket([]); return jsonify(ok=True)

# ── ORDERS ──────────────────────────────────────────────────────────────────
@app.route('/api/orders', methods=['POST'])
def create_order():
    if 'user_id' not in session: return jsonify(ok=False, error='Not authenticated.'), 401
    d = request.json or {}; b = _get_basket(); t = _totals(b['items'])
    if not b['items']: return jsonify(ok=False, error='Basket is empty.'), 400

    oid = 'ORD-' + datetime.datetime.utcnow().strftime('%Y%m%d') + '-' + uid().upper()
    execute('''INSERT INTO orders
        (id,customer_id,customer_email,customer_org,items,subtotal,vat,commission,total,
         payment_method,handshake_at,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
        oid, session['user_id'], session['email'], session.get('org',''),
        json.dumps(b['items']), t['subtotal'], t['vat'], t['commission'], t['total'],
        d.get('method','card'), d.get('handshakeAt', now()), 'confirmed', now()
    ))
    _save_basket([])
    order = query('SELECT * FROM orders WHERE id=?', (oid,), one=True)
    order['items'] = json.loads(order['items'])
    return jsonify(ok=True, order=order)

@app.route('/api/orders')
def get_orders():
    if 'user_id' not in session: return jsonify([])
    rows = query('SELECT * FROM orders WHERE customer_id=? ORDER BY created_at DESC', (session['user_id'],))
    for r in rows: r['items'] = json.loads(r.get('items') or '[]')
    return jsonify(rows)

@app.route('/api/orders/<oid>', methods=['GET'])
def get_order(oid):
    """Single order detail — available to the customer who placed it or the supplier it was placed with."""
    if 'user_id' not in session:
        return jsonify(error='Not authenticated.'), 401
    order = query('SELECT * FROM orders WHERE id=?', (oid,), one=True)
    if not order:
        return jsonify(error='Order not found.'), 404
    order['items'] = json.loads(order.get('items') or '[]')
    # Allow access if customer owns it or if any item's supplierName matches session org
    uid_ = session['user_id']
    utype = session.get('user_type')
    if utype == 'customer' and order['customer_id'] != uid_:
        return jsonify(error='Forbidden.'), 403
    if utype == 'supplier':
        sup_org = session.get('org','').lower()
        # Check if any basket item was from this supplier
        names = [i.get('supplierName','').lower() for i in order['items']]
        if sup_org not in names and session.get('name','').lower() not in names:
            # Also check supplier id
            if not any(i.get('supplierId','') == uid_ for i in order['items']):
                return jsonify(error='Forbidden.'), 403
    return jsonify(order)


@app.route('/api/supplier/orders', methods=['GET'])
def get_supplier_orders():
    """All orders that contain items from the logged-in supplier."""
    if 'user_id' not in session or session.get('user_type') != 'supplier':
        return jsonify([])
    sup_id   = session.get('user_id', '')
    sup_org  = (session.get('org') or '').lower()
    sup_name = (session.get('name') or '').lower()
    # Also get company_name directly from suppliers table for reliable matching
    sup_row  = query('SELECT company_name FROM suppliers WHERE id=?', (sup_id,), one=True)
    sup_company = (sup_row['company_name'] if sup_row else '').lower()
    all_orders = query('SELECT * FROM orders ORDER BY created_at DESC')
    result = []
    for o in all_orders:
        items = json.loads(o.get('items') or '[]')
        # Match by supplierId (most reliable), then company_name, then org name
        matched = [i for i in items if
                   i.get('supplierId','') == sup_id or
                   i.get('supplierName','').lower() == sup_company or
                   i.get('supplierName','').lower() == sup_org or
                   i.get('supplierName','').lower() == sup_name]
        if matched:
            o['items']         = items
            o['matched_items'] = matched
            result.append(o)
    return jsonify(result)


@app.route('/api/orders/<oid>/complete', methods=['POST'])
def complete_order(oid):
    """Supplier marks an order as completed."""
    if 'user_id' not in session or session.get('user_type') != 'supplier':
        return jsonify(ok=False, error='Supplier login required.'), 403
    order = query('SELECT * FROM orders WHERE id=?', (oid,), one=True)
    if not order:
        return jsonify(ok=False, error='Order not found.'), 404
    execute("UPDATE orders SET status='completed' WHERE id=?", (oid,))
    return jsonify(ok=True, status='completed')


@app.route('/api/orders/<oid>/pdf')
def order_pdf(oid):
    order = query('SELECT * FROM orders WHERE id=?', (oid,), one=True)
    if not order: return jsonify(error='Not found'), 404
    order['items'] = json.loads(order.get('items') or '[]')
    html = _po_html(order)
    if WEASYPRINT_OK:
        pdf = weasyprint.HTML(string=html).write_pdf()
        return send_file(io.BytesIO(pdf), mimetype='application/pdf',
                         as_attachment=True, download_name=f'AgoraFM-{oid}.pdf')
    return html, 200, {'Content-Type': 'text/html'}

def _po_html(o):
    rows = ''
    for i in o['items']:
        line = float(i.get('price',0)) * int(i.get('qty',1))
        vat  = line * VAT_RATE
        rows += f"<tr><td>{i.get('name','')}</td><td>{i.get('supplierName','')}</td><td style='text-align:center'>{i.get('qty',1)}</td><td style='text-align:right'>£{float(i.get('price',0)):.2f}</td><td style='text-align:right'>£{line:.2f}</td><td style='text-align:right'>£{vat:.2f}</td><td style='text-align:right;font-weight:bold;color:#F18F01'>£{line+vat:.2f}</td></tr>"
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>body{{font-family:Arial,sans-serif;margin:40px;color:#333}}
h1{{color:#0A1A2F;letter-spacing:4px}}.accent{{color:#F18F01}}
table{{width:100%;border-collapse:collapse;margin:20px 0}}
th{{background:#0A1A2F;color:#fff;padding:10px;font-size:11px;text-transform:uppercase;letter-spacing:1px;text-align:left}}
td{{padding:10px;border-bottom:1px solid #eee;font-size:13px}}
.total{{font-weight:bold;background:#f9f9f9;border-top:2px solid #0A1A2F}}
.foot{{margin-top:30px;font-size:11px;color:#aaa;text-align:center;border-top:1px solid #eee;padding-top:12px}}</style>
</head><body>
<table style="border:none;margin-bottom:20px"><tr>
<td style="border:none;padding:0"><h1>AGORA<span class="accent">FM</span></h1><div style="font-size:11px;color:#888;letter-spacing:2px">PURCHASE ORDER</div></td>
<td style="border:none;padding:0;text-align:right"><div style="font-size:18px;font-weight:bold">{o['id']}</div><div style="font-size:11px;color:#888">{o['created_at'][:10]}</div><div style="color:#F18F01;font-weight:bold">{o['status'].upper()}</div></td>
</tr></table>
<table style="border:none;margin-bottom:20px"><tr>
<td style="border:none;padding:0;width:50%;vertical-align:top"><div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px">Customer</div><div style="font-weight:bold">{o['customer_org']}</div><div>{o['customer_email']}</div></td>
<td style="border:none;padding:0;width:50%;vertical-align:top"><div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px">Payment Method</div><div>{o['payment_method'].replace('_',' ').title()}</div><div style="font-size:11px;color:#888;margin-top:6px">Handshake: {o['handshake_at'][:19].replace('T',' ')}</div></td>
</tr></table>
<table><thead><tr><th>Service</th><th>Supplier</th><th>Qty</th><th>Unit Price</th><th>Line Total</th><th>VAT 20%</th><th>Total inc VAT</th></tr></thead>
<tbody>{rows}</tbody>
<tfoot><tr class="total"><td colspan="4">TOTALS</td><td style="text-align:right">£{o['subtotal']:.2f}</td><td style="text-align:right">£{o['vat']:.2f}</td><td style="text-align:right;color:#F18F01">£{o['total']:.2f}</td></tr></tfoot></table>
<div style="font-size:11px;color:#888;margin-top:8px">5% Agora FM commission (£{o['commission']:.2f}) is charged to the service provider — not the customer.</div>
<div class="foot">Generated by Agora FM · Platform v3.0 · ISO 27001 Certified · GDPR Compliant</div>
</body></html>"""

# ── ADMIN ───────────────────────────────────────────────────────────────────
@app.route('/api/admin/dump')
def admin_dump():
    custs = query('SELECT id,org_name,email,first_name,last_name,created_at FROM customers')
    sups  = query('SELECT id,company_name,email,contact_first,contact_last,verified,created_at FROM suppliers')
    ords  = query('SELECT id,customer_email,customer_org,total,payment_method,status,created_at FROM orders ORDER BY created_at DESC')
    b     = _get_basket()
    rev   = sum(r['total'] for r in ords)
    return jsonify(customers=custs, suppliers=sups, orders=ords, basket=b, session=_sess() if 'user_id' in session else {},
                   stats=dict(customers=len(custs), suppliers=len(sups), orders=len(ords),
                               revenue=round(rev,2), commission=round(rev*COMMISSION_RATE,2)))

@app.route('/api/admin/reset', methods=['POST'])
def admin_reset():
    db = get_db()
    cur = db.cursor()
    for t in ('customers','suppliers','orders','baskets'):
        cur.execute(f'DELETE FROM {t}')
    db.commit()
    session.clear(); _seed(db)
    return jsonify(ok=True, message='Reset and re-seeded.')

# ── DB INIT ─────────────────────────────────────────────────────────────────
SCHEMA = '''
CREATE TABLE IF NOT EXISTS customers(
    id TEXT PRIMARY KEY, org_name TEXT, org_type TEXT, reg_address TEXT,
    phone TEXT, first_name TEXT, last_name TEXT, job_title TEXT,
    email TEXT UNIQUE, password_hash TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS suppliers(
    id TEXT PRIMARY KEY, company_name TEXT, company_reg TEXT, reg_address TEXT,
    main_tel TEXT, website TEXT, contact_first TEXT, contact_last TEXT,
    contact_role TEXT, email TEXT UNIQUE, password_hash TEXT, coverage TEXT,
    categories TEXT, accreditations TEXT, pl_insurance TEXT, el_insurance TEXT,
    bank_name TEXT, sort_code TEXT, account_num TEXT, company_desc TEXT,
    verified INTEGER DEFAULT 0, created_at TEXT);
CREATE TABLE IF NOT EXISTS services(
    id TEXT PRIMARY KEY,
    supplier_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    unit_label TEXT NOT NULL,
    unit_price_pennies INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS baskets(
    user_id TEXT PRIMARY KEY, items TEXT DEFAULT '[]', updated_at TEXT);
CREATE TABLE IF NOT EXISTS orders(
    id TEXT PRIMARY KEY, customer_id TEXT, customer_email TEXT, customer_org TEXT,
    items TEXT, subtotal NUMERIC, vat NUMERIC, commission NUMERIC, total NUMERIC,
    payment_method TEXT, handshake_at TEXT, status TEXT DEFAULT 'confirmed', created_at TEXT);
'''

def _seed(db=None):
    close = False
    if db is None:
        if USE_POSTGRES:
            db = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            import sqlite3 as _sq3
            db = _sq3.connect(DB_PATH)
        close = True

    def _x(sql, params=()):
        cur = db.cursor()
        cur.execute(_pg_sql(sql), params)
        db.commit()

    def h(p): return hashlib.sha256(p.encode()).hexdigest()
    t = datetime.datetime.utcnow().isoformat()

    try:
        _x('''INSERT OR IGNORE INTO customers(id,org_name,org_type,reg_address,phone,first_name,last_name,job_title,email,password_hash,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
            ('cust_demo','Whitmore Estate Services Ltd','Commercial Property Owner',
             '1 Canada Square, London E14 5AB','020 7123 0001',
             'James','Hartley','FM Director','customer@demo.com',h('Demo123!'),t))
    except: pass

    seed = [
        ('sup_001','Apollo Fire Technicians Ltd','04821033','12 Barbican Centre, London EC2Y 8NB','020 7123 4567','www.apollofire.co.uk','James','Hartley','Operations Director','enquiries@apollofire.co.uk',h('Apollo123!'),'National (England & Wales)','["Fire"]','["BAFE","CHAS Premium","ISO 9001","SafeContractor"]','£5 million','£10 million','Apollo Fire Technicians Ltd','20-41-18','80123456','BAFE-certified fire protection specialists with 20+ years of commercial experience.',1),
        ('sup_002','AquaSafe Testing Ltd','07234891','4 Waterside Court, Leeds LS1 4GL','0333 123 9876','www.aquasafe-testing.co.uk','Sarah','Chen','Technical Director','info@aquasafe-testing.co.uk',h('Aqua456!'),'National (England)','["Water"]','["UKAS Accredited","Legionella Control","ISO 9001","CHAS"]','£5 million','£10 million','AquaSafe Testing Ltd','30-98-12','12345678','UKAS-accredited Legionella and water hygiene specialists.',1),
        ('sup_003','Volt Electrical Compliance Ltd','09871234','Unit 7 Aston Cross Business Village Birmingham B6 5RQ','0121 456 7890','www.voltcompliance.co.uk','Marcus','Williams','Managing Director','contracts@voltcompliance.co.uk',h('Volt789!'),'National (England & Wales)','["Electricity"]','["NICEIC","ECA Member","CHAS","ISO 9001"]','£5 million','£10 million','Volt Electrical Compliance Ltd','40-12-34','87654321','NICEIC-approved electrical testing and compliance specialists.',1),
        ('sup_004','BritHeat Gas Services Ltd','06543210','88 Wellington Street Leeds LS1 2EQ','0113 345 6789','www.britheat.co.uk','David','Okafor','Commercial Manager','service@britheat.co.uk',h('BritHeat1!'),'Regional (multi-county)','["Gas"]','["Gas Safe","OFTEC","CHAS","ISO 9001"]','£2 million','£5 million','BritHeat Gas Services Ltd','60-23-45','11223344','Gas Safe registered commercial boiler and gas compliance specialists.',1),
        ('sup_005','PureAir HVAC Solutions Ltd','11223344','22 Kings Road Reading RG1 3AR','020 3456 7890','www.pureairhvac.co.uk','Priya','Sharma','Technical Sales Director','hello@pureairhvac.co.uk',h('PureAir2!'),'National (England)','["HVAC"]','["REFCOM","F-Gas Certified","CHAS","SafeContractor"]','£5 million','£10 million','PureAir HVAC Solutions Ltd','20-33-99','55667788','F-Gas certified HVAC and air conditioning specialists.',1),
    ]
    # 5 additional suppliers for remaining compliance categories
    extra = [
        ('sup_006','ClearLift Services Ltd','08234567','Unit 4 Lenton Business Centre Nottingham NG7 2BY','0115 987 3456','www.clearlift.co.uk','Paul','Dixon','Managing Director','service@clearlift.co.uk',h('ClearLift1!'),'National (England & Wales)','["Lifts & Lifting Equipment"]','["LEIA Member","LOLER Certified","ISO 9001","CHAS"]','£5 million','£10 million','ClearLift Services Ltd','60-44-21','22334455','LEIA-member lift maintenance and LOLER inspection specialists with national coverage.',1),
        ('sup_007','SafeAir Asbestos Consultancy Ltd','05678901','15 Temple Row Birmingham B2 5LG','0121 233 4567','www.safeair-asbestos.co.uk','Helen','Marsh','Technical Director','surveys@safeair-asbestos.co.uk',h('SafeAir1!'),'National (England & Wales)','["Asbestos"]','["UKAS Accredited","BOHS P402","ISO 17025","CHAS"]','£5 million','£10 million','SafeAir Asbestos Consultancy Ltd','40-55-33','33445566','UKAS-accredited asbestos management survey and consultancy specialists.',1),
        ('sup_008','CoolEdge Climate Ltd','06789012','7 Rutherford Way Cheltenham GL51 9TU','01242 512 890','www.cooledgeclimate.co.uk','Adam','Foster','Operations Manager','info@cooledgeclimate.co.uk',h('CoolEdge1!'),'National (England)','["Air Conditioning"]','["REFCOM","F-Gas Certified","SafeContractor","CHAS"]','£5 million','£5 million','CoolEdge Climate Ltd','30-77-44','44556677','F-Gas certified air conditioning maintenance specialists covering split, multi-split and VRF systems.',1),
        ('sup_009','PressureSafe Engineering Ltd','07890123','33 Sovereign Way Tonbridge TN9 1RH','01732 360 450','www.pressuresafe.co.uk','Kevin','Obi','Chief Engineer','inspect@pressuresafe.co.uk',h('PressureSafe1!'),'National (England & Wales)','["Pressure Vessels"]','["PSSR Certified","ISO 9001","CHAS","SafeContractor"]','£5 million','£10 million','PressureSafe Engineering Ltd','50-66-77','55667788','PSSR-competent pressure vessel inspection and chiller maintenance specialists.',1),
        ('sup_010','RiskFirst Consultancy Ltd','09012345','20 St James Street London SW1A 1ES','020 7930 1234','www.riskfirst.co.uk','Natasha','Okonkwo','Head of Consulting','hello@riskfirst.co.uk',h('RiskFirst1!'),'National','["Risk Assessments"]','["NEBOSH","IOSH Member","ISO 45001","SafeContractor"]','£5 million','£10 million','RiskFirst Consultancy Ltd','20-99-11','66778899','NEBOSH and IOSH-qualified risk assessment consultancy for commercial and mixed-use estates.',1),
    ]
    # Insert original 5 suppliers FIRST (services reference them)
    for s in seed:
        try:
            _x('''INSERT OR IGNORE INTO suppliers(id,company_name,company_reg,reg_address,main_tel,website,
                contact_first,contact_last,contact_role,email,password_hash,coverage,categories,
                accreditations,pl_insurance,el_insurance,bank_name,sort_code,account_num,company_desc,verified,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', s+(t,))
        except Exception as e:
            print(f'  Seed warning (sup): {e}')

    # Then insert 5 extra suppliers
    for s in extra:
        try:
            _x('''INSERT OR IGNORE INTO suppliers(id,company_name,company_reg,reg_address,main_tel,website,
                contact_first,contact_last,contact_role,email,password_hash,coverage,categories,
                accreditations,pl_insurance,el_insurance,bank_name,sort_code,account_num,company_desc,verified,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', s+(t,))
        except Exception as e:
            print(f'  Seed warning (extra): {e}')

    # Services — 2 per supplier (10 suppliers = 20 services)
    services = [
        # Apollo Fire
        ('svc_001_1','sup_001','Fire Alarm PPM Visit','Bi-annual planned preventive maintenance visit covering all fire alarm panels, detectors, sounders and call points. BS 5839-1 compliant. Certificate issued same day.','per visit',28500),
        ('svc_001_2','sup_001','Fire Extinguisher Service','Annual inspection, recharge and certification of all extinguisher types. BAFE-certified. Cost per extinguisher. Pass/fail certificate and asset log provided.','per extinguisher',800),
        # AquaSafe
        ('svc_002_1','sup_002','Legionella Water Sampling','UKAS-accredited L8 water sampling at sentinel hot and cold outlets. Includes laboratory analysis and written report. Results within 5 working days.','per sample',9500),
        ('svc_002_2','sup_002','Monthly Sentinel Outlet Checks','Monthly temperature monitoring at sentinel outlets with flow checks and logbook updates. Includes annual L8 risk assessment review.','per month',19500),
        # Volt Electrical
        ('svc_003_1','sup_003','EICR Inspection','Electrical Installation Condition Report to BS 7671 (18th Edition). Full inspection of distribution boards, wiring, earthing and bonding. NICEIC approved. Report within 5 days.','per distribution board',45000),
        ('svc_003_2','sup_003','Emergency Lighting Test','Annual full-duration discharge test plus monthly flick-test monitoring. Compliant with BS 5266-1. Certificate issued after every visit. Fault rectification included.','per visit',19500),
        # BritHeat
        ('svc_004_1','sup_004','Commercial Boiler Service','Annual boiler service by Gas Safe registered engineer. Covers all gas-fired types. Includes flue analysis, controls check and gas tightness test. Certificate issued.','per boiler',19500),
        ('svc_004_2','sup_004','Gas Safety Inspection','Full gas safety inspection and CP12 certificate for commercial premises. Covers all gas appliances, pipework pressure test and ventilation checks.','per inspection',15000),
        # PureAir HVAC
        ('svc_005_1','sup_005','AHU Filter Change','Quarterly air handling unit filter change and visual inspection. Covers all filter grades. Includes post-change report and next-change schedule. Cost per filter bank.','per filter bank',8500),
        ('svc_005_2','sup_005','Quarterly HVAC PPM Visit','Quarterly planned preventive maintenance visit covering AHUs, fan coils and ventilation plant. Full engineer report with condition ratings and priority action log.','per visit',69500),
        # ClearLift
        ('svc_006_1','sup_006','Passenger Lift Maintenance','Monthly planned maintenance contract for traction and hydraulic passenger lifts. Covers 12 visits per year. Includes 24/7 entrapment response and engineer callout.','per lift per year',714200),
        ('svc_006_2','sup_006','LOLER Inspection','Thorough examination of all lifting equipment under LOLER 1998 regulations. Includes passenger lifts, goods lifts, scissor lifts and MEWPS. Certificate issued.','per inspection',51800),
        # SafeAir Asbestos
        ('svc_007_1','sup_007','Asbestos Management Survey','UKAS-accredited management survey for in-use buildings. Identifies and records ACMs, assesses condition and provides risk rating. Digital register provided.','per survey',73000),
        ('svc_007_2','sup_007','Asbestos R&D Survey','Refurbishment and demolition survey required before any intrusive works. Destructive inspection to identify all ACMs in the proposed works area. Report within 48 hours.','per survey',120000),
        # CoolEdge Climate
        ('svc_008_1','sup_008','Split System AC Service','Bi-annual service and maintenance of split and multi-split air conditioning systems. F-Gas certified. Includes filter clean, refrigerant check, coil inspection and performance report.','per unit per year',28000),
        ('svc_008_2','sup_008','VRF System PPM Visit','Quarterly VRF/VRV system planned maintenance visit. Full system health check, outdoor unit inspection, refrigerant circuit analysis and controller review. All major brands covered.','per visit',69500),
        # PressureSafe
        ('svc_009_1','sup_009','Pressure Vessel Inspection','6-monthly written scheme of examination for pressure vessels, calorifiers and expansion vessels under PSSR 2000. Includes hydraulic test where required. Certificate issued.','per vessel',19500),
        ('svc_009_2','sup_009','Chiller Maintenance Visit','Quarterly chiller maintenance covering refrigerant circuit analysis, oil sample, condenser cleaning, controls calibration and full operational test. Cost per chiller.','per visit',50000),
        # RiskFirst
        ('svc_010_1','sup_010','Fire Risk Assessment','PAS 79 compliant fire risk assessment for commercial premises. Written report with photographic evidence, RAG-rated findings and prioritised action plan. 10 working day turnaround.','per building',200000),
        ('svc_010_2','sup_010','DSE Workstation Assessment','Individual Display Screen Equipment assessment compliant with DSE Regulations 1992. Covers workstation setup, posture, lighting and equipment. Written recommendations per employee.','per workstation',3500),
    ]
    for s in services:
        try:
            _x('''INSERT OR IGNORE INTO services(id,supplier_id,name,description,unit_label,unit_price_pennies,active)
                VALUES(?,?,?,?,?,?,1)''', s)
        except Exception as e:
            print(f'  Seed warning (svc): {e}')

    # Force-update demo credentials so they always work
    try:
        _x("UPDATE customers SET password_hash=? WHERE id='cust_demo'",
           (hashlib.sha256('Demo123!'.encode()).hexdigest(),))
        _x("UPDATE suppliers SET password_hash=? WHERE id='sup_001'",
           (hashlib.sha256('Apollo123!'.encode()).hexdigest(),))
        _x("UPDATE suppliers SET password_hash=? WHERE id='sup_002'",
           (hashlib.sha256('Aqua456!'.encode()).hexdigest(),))
        _x("UPDATE suppliers SET password_hash=? WHERE id='sup_003'",
           (hashlib.sha256('Volt789!'.encode()).hexdigest(),))
        _x("UPDATE suppliers SET password_hash=? WHERE id='sup_004'",
           (hashlib.sha256('BritHeat1!'.encode()).hexdigest(),))
        _x("UPDATE suppliers SET password_hash=? WHERE id='sup_005'",
           (hashlib.sha256('PureAir2!'.encode()).hexdigest(),))
    except Exception as e:
        print(f'  Warning: could not update demo credentials: {e}')
    if close:
        try: db.close()
        except: pass


def init_db():
    if USE_POSTGRES:
        db = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = db.cursor()
        for stmt in SCHEMA.strip().split(';'):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        db.commit(); db.close()
    else:
        import sqlite3 as _sq3
        db = _sq3.connect(DB_PATH)
        db.executescript(SCHEMA)
        db.commit(); db.close()

# ── Startup (runs under gunicorn AND python app.py) ──────────────────────────
print('=' * 52)
print('  AGORA FM — Python Backend')
print('  Mode: ' + ('PostgreSQL (Railway)' if USE_POSTGRES else 'SQLite (local)'))
print('=' * 52)
init_db()
_seed()
print('  DB ready.')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, port=port, host='0.0.0.0')
