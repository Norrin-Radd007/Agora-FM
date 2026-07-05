"""
AGORA FM — Flask Backend (app.py)
Run:  python app.py
Open: http://localhost:5000

Database: Uses PostgreSQL on Railway (DATABASE_URL env var) or SQLite locally.
"""
import os, json, hashlib, secrets, datetime, io
from flask import Flask, request, jsonify, session, send_from_directory, send_file, g
from werkzeug.utils import secure_filename

WEASYPRINT_OK   = False   # Removed — do not re-enable
COMMISSION_RATE = 0.05
VAT_RATE        = 0.20

# ── Resend email ─────────────────────────────────────────────────────────────
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
EMAIL_FROM     = 'Agora FM <noreply@agorafm.co.uk>'
EMAIL_ENABLED  = bool(RESEND_API_KEY)

def send_email(to, subject, html_body):
    if not EMAIL_ENABLED:
        print('[Email] Skipped (no RESEND_API_KEY): ' + subject)
        return False
    try:
        import urllib.request
        payload = json.dumps({'from': EMAIL_FROM, 'to': [to] if isinstance(to, str) else to,
                              'subject': subject, 'html': html_body}).encode('utf-8')
        req = urllib.request.Request('https://api.resend.com/emails', data=payload,
            headers={'Authorization': 'Bearer ' + RESEND_API_KEY, 'Content-Type': 'application/json'},
            method='POST')
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read())
            print('[Email] Sent: ' + subject + ' (id:' + str(result.get('id','')) + ')')
            return True
    except Exception as e:
        print('[Email] Failed: ' + str(e))
        return False

def _ew(body):
    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"><style>'
        'body{margin:0;background:#0A1A2F;font-family:Arial,sans-serif;}'
        '.w{max-width:600px;margin:0 auto;background:#0F2239;}'
        '.h{background:#0A1A2F;padding:24px 32px;border-bottom:3px solid #F18F01;}'
        '.logo{font-size:1.5rem;font-weight:900;color:#E3E5E8;letter-spacing:2px;}'
        '.logo span{color:#F18F01;}'
        '.b{padding:32px;color:#E3E5E8;font-size:0.9rem;line-height:1.7;}'
        '.s{background:#112240;border:1px solid rgba(62,107,137,0.3);border-radius:4px;padding:20px;margin:20px 0;}'
        '.lbl{font-size:0.65rem;letter-spacing:2px;text-transform:uppercase;color:rgba(227,229,232,0.4);margin-bottom:4px;}'
        '.val{font-size:0.95rem;color:#E3E5E8;font-weight:600;}'
        '.amt{font-size:1.3rem;color:#F18F01;font-weight:900;}'
        'hr{border:none;border-top:1px solid rgba(62,107,137,0.2);margin:12px 0;}'
        'a{color:#F18F01;}'
        '.ft{padding:16px 32px;border-top:1px solid rgba(62,107,137,0.2);font-size:0.7rem;color:rgba(227,229,232,0.3);text-align:center;}'
        '</style></head><body><div class="w">'
        '<div class="h"><span class="logo">AGORA<span>FM</span></span></div>'
        '<div class="b">' + body + '</div>'
        '<div class="ft">Agora FM Ltd &middot; <a href="https://agora-fm-production.up.railway.app">agora-fm-production.up.railway.app</a></div>'
        '</div></body></html>'
    )

def _row3(name, supplier, price):
    s = 'padding:6px 0;border-bottom:1px solid rgba(62,107,137,0.1);'
    return ('<tr>'
        '<td style="' + s + 'color:#E3E5E8;">' + name + '</td>'
        '<td style="' + s + 'color:rgba(227,229,232,0.5);">' + supplier + '</td>'
        '<td style="' + s + 'text-align:right;color:#F18F01;">&#163;' + price + '</td>'
        '</tr>')

def _row2(name, price):
    s = 'padding:6px 0;border-bottom:1px solid rgba(62,107,137,0.1);'
    return ('<tr>'
        '<td style="' + s + 'color:#E3E5E8;">' + name + '</td>'
        '<td style="' + s + 'text-align:right;color:#F18F01;">&#163;' + price + '</td>'
        '</tr>')

def email_order_confirmation(order, to_email, to_name):
    items = order.get('items', [])
    rows = ''.join(_row3(i.get('name',''), i.get('supplierName',''), '{:.2f}'.format(float(i.get('price',0)))) for i in items)
    th = 'font-size:0.65rem;letter-spacing:2px;text-transform:uppercase;color:rgba(227,229,232,0.4);padding-bottom:8px;'
    body = (
        '<p>Dear ' + to_name + ',</p>'
        '<p>Your order has been confirmed on Agora FM. Your selected service providers have been notified.</p>'
        '<div class="s">'
        '<div class="lbl">Order Reference</div><div class="val">' + order.get('id','') + '</div><hr>'
        '<div class="lbl">Payment Method</div><div class="val">' + order.get('payment_method','').replace('_',' ').title() + '</div>'
        '</div>'
        '<div class="s"><table style="width:100%;border-collapse:collapse;">'
        '<thead><tr>'
        '<th style="text-align:left;' + th + '">Service</th>'
        '<th style="text-align:left;' + th + '">Provider</th>'
        '<th style="text-align:right;' + th + '">Price</th>'
        '</tr></thead><tbody>' + rows + '</tbody></table><hr>'
        '<div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span style="color:rgba(227,229,232,0.5);">Subtotal</span><span>&#163;' + '{:.2f}'.format(float(order.get('subtotal',0))) + '</span></div>'
        '<div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span style="color:rgba(227,229,232,0.5);">VAT (20%)</span><span>&#163;' + '{:.2f}'.format(float(order.get('vat',0))) + '</span></div>'
        '<div style="display:flex;justify-content:space-between;margin-top:8px;"><span style="font-weight:700;">Total inc. VAT</span><span class="amt">&#163;' + '{:.2f}'.format(float(order.get('total',0))) + '</span></div>'
        '</div>'
        '<p style="font-size:0.8rem;color:rgba(227,229,232,0.5);">View your order history in your <a href="https://agora-fm-production.up.railway.app/dashboard.html">Agora FM dashboard</a>.</p>'
        '<p style="font-size:0.8rem;color:rgba(227,229,232,0.5);">The 5% Agora FM commission is charged to your service provider, not you.</p>'
    )
    send_email(to_email, 'Order Confirmed -- ' + order.get('id','') + ' -- Agora FM', _ew(body))

def email_new_order_supplier(order, to_email, to_name):
    items = order.get('items', [])
    rows = ''.join(_row2(i.get('name',''), '{:.2f}'.format(float(i.get('price',0)))) for i in items)
    th = 'font-size:0.65rem;letter-spacing:2px;text-transform:uppercase;color:rgba(227,229,232,0.4);padding-bottom:8px;'
    body = (
        '<p>Dear ' + to_name + ',</p>'
        '<p>You have received a new order via Agora FM. Please contact the customer to arrange service delivery.</p>'
        '<div class="s">'
        '<div class="lbl">Order Reference</div><div class="val">' + order.get('id','') + '</div><hr>'
        '<div class="lbl">Customer Organisation</div><div class="val">' + order.get('customer_org','') + '</div><hr>'
        '<div class="lbl">Customer Email</div><div class="val">' + order.get('customer_email','') + '</div>'
        '</div>'
        '<div class="s"><table style="width:100%;border-collapse:collapse;">'
        '<thead><tr>'
        '<th style="text-align:left;' + th + '">Service Ordered</th>'
        '<th style="text-align:right;' + th + '">Value</th>'
        '</tr></thead><tbody>' + rows + '</tbody></table><hr>'
        '<div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span style="color:rgba(227,229,232,0.5);">Order Total</span><span class="amt">&#163;' + '{:.2f}'.format(float(order.get('total',0))) + '</span></div>'
        '<div style="display:flex;justify-content:space-between;"><span style="color:rgba(227,229,232,0.5);">Your net (after 5% commission)</span><span style="color:#5cb85c;">&#163;' + '{:.2f}'.format(float(order.get('total',0))*0.95) + '</span></div>'
        '</div>'
        '<p style="font-size:0.8rem;color:rgba(227,229,232,0.5);">Log in to your <a href="https://agora-fm-production.up.railway.app/supplier_dashboard.html">supplier dashboard</a> to manage this order.</p>'
    )
    send_email(to_email, 'New Order Received -- ' + order.get('id','') + ' -- Agora FM', _ew(body))

def email_new_review(to_email, to_name, reviewer_name, reviewer_org, rating, title, supplier_id):
    stars = '&#9733;' * rating + '&#9734;' * (5 - rating)
    body = (
        '<p>Dear ' + to_name + ',</p>'
        '<p>A new review has been posted on your Agora FM profile.</p>'
        '<div class="s">'
        '<div class="lbl">Reviewer</div><div class="val">' + reviewer_name + ', ' + reviewer_org + '</div><hr>'
        '<div class="lbl">Rating</div><div class="val" style="color:#F18F01;font-size:1.1rem;">' + stars + ' &nbsp;' + str(rating) + '/5</div><hr>'
        '<div class="lbl">Review Title</div><div class="val">' + title + '</div>'
        '</div>'
        '<p style="font-size:0.8rem;color:rgba(227,229,232,0.5);">You can respond to this review from your <a href="https://agora-fm-production.up.railway.app/provider_profile.html?provider=' + supplier_id + '">provider profile</a>.</p>'
    )
    send_email(to_email, 'New Review Posted -- ' + str(rating) + '/5 Stars -- Agora FM', _ew(body))

def email_new_enquiry(to_email, to_name, cust_name, cust_org, cust_email, cust_phone, service, notes):
    body = (
        '<p>Dear ' + to_name + ',</p>'
        '<p>You have received a new service enquiry via Agora FM.</p>'
        '<div class="s">'
        '<div class="lbl">Customer Name</div><div class="val">' + cust_name + '</div><hr>'
        '<div class="lbl">Organisation</div><div class="val">' + cust_org + '</div><hr>'
        '<div class="lbl">Email</div><div class="val">' + cust_email + '</div><hr>'
        '<div class="lbl">Phone</div><div class="val">' + (cust_phone or 'Not provided') + '</div><hr>'
        '<div class="lbl">Service Required</div><div class="val">' + service + '</div>'
        + ('<hr><div class="lbl">Notes</div><div class="val" style="font-weight:400;color:rgba(227,229,232,0.7);">' + notes + '</div>' if notes else '') +
        '</div>'
        '<p style="font-size:0.8rem;color:rgba(227,229,232,0.5);">Reply directly to the customer at <a href="mailto:' + cust_email + '">' + cust_email + '</a>.</p>'
    )
    send_email(to_email, 'New Enquiry -- ' + service + ' -- Agora FM', _ew(body))

# ── Database mode detection ──────────────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')
# Railway provides postgres:// but psycopg2 requires postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    print(f'  PG URL prefix: {DATABASE_URL[:30]}...')
else:
    import sqlite3
    print('  WARNING: No DATABASE_URL found — using SQLite')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'agora.db')   # SQLite only (local dev)

app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
app.secret_key = 'agora-fm-demo-secret-key-2026'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024  # hard ceiling above the 10MB per-document limit below

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
    try:
        cur = db.cursor()
        cur.execute(_pg_sql(sql), params)
        rows = [dict(r) for r in cur.fetchall()]
        return (rows[0] if rows else None) if one else rows
    except Exception as e:
        print(f'[query error] {e}')
        try: db.rollback()
        except: pass
        return None if one else []

def execute(sql, params=()):
    db  = get_db()
    try:
        cur = db.cursor()
        cur.execute(_pg_sql(sql), params)
        db.commit()
        return getattr(cur, 'lastrowid', None)
    except Exception as e:
        print(f'[execute error] {e}')
        try: db.rollback()
        except: pass
        return None

def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()
def uid():      return secrets.token_hex(5)
def now():      return datetime.datetime.utcnow().isoformat()

def _bin(data):
    """Wrap raw bytes for insertion into a BYTEA/BLOB column on either backend."""
    if USE_POSTGRES:
        return psycopg2.Binary(data)
    return data

# Document uploads: keep this well under Railway/Flask's request size ceiling.
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10MB per file
ALLOWED_DOCUMENT_MIME = {'application/pdf', 'image/jpeg', 'image/png', 'image/heic'}

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
         contact_role,email,password_hash,coverage,coverage_regions,categories,accreditations,pl_insurance,
         el_insurance,bank_name,sort_code,account_num,company_desc,verified,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
        sid, d.get('companyName','').strip(), d.get('companyReg','').strip(),
        d.get('regAddress','').strip(), d.get('mainTel','').strip(), d.get('website','').strip(),
        d.get('contactFirst','').strip(), d.get('contactLast','').strip(), d.get('contactRole','').strip(),
        em, hash_pw(d.get('password','')), d.get('coverage',''),
        json.dumps(d.get('coverageRegions',[])),
        json.dumps(d.get('categories',[])), json.dumps(d.get('accreditations',[])),
        d.get('plInsurance',''), d.get('elInsurance',''), d.get('bankName','').strip(),
        d.get('sortCode','').strip(), d.get('accountNum','').strip(), d.get('companyDesc','').strip(),
        0, now()
    ))
    session.update(user_id=sid, user_type='supplier', email=em,
                   name=d.get('contactFirst','').strip()+' '+d.get('contactLast','').strip(),
                   org=d.get('companyName','').strip())
    return jsonify(ok=True, id=sid)

# ── SUPPLIER DOCUMENTS (PL insurance certs, accreditation certs) ────────────
@app.errorhandler(413)
def _too_large(e):
    return jsonify(ok=False, error='File is too large — please upload a file under 10MB.'), 413

@app.route('/api/suppliers/documents', methods=['POST'])
def upload_supplier_document():
    if 'user_id' not in session or session.get('user_type') != 'supplier':
        return jsonify(ok=False, error='Must be logged in as a supplier to upload documents.'), 401

    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify(ok=False, error='No file was received.'), 400

    doc_type = (request.form.get('doc_type') or '').strip()
    if doc_type not in ('pl_insurance', 'accreditation'):
        return jsonify(ok=False, error='Invalid document type.'), 400

    data = f.read()
    if len(data) == 0:
        return jsonify(ok=False, error='That file appears to be empty.'), 400
    if len(data) > MAX_DOCUMENT_BYTES:
        return jsonify(ok=False, error='File is too large — please upload a file under 10MB.'), 400
    mime = f.mimetype or 'application/octet-stream'
    if mime not in ALLOWED_DOCUMENT_MIME:
        return jsonify(ok=False, error='Please upload a PDF, JPG or PNG file.'), 400

    doc_id   = 'doc_' + uid()
    filename = secure_filename(f.filename) or 'document'
    label    = (request.form.get('label') or '').strip()

    execute('''INSERT INTO supplier_documents
        (id,supplier_id,doc_type,label,filename,mime_type,file_size,file_data,uploaded_at)
        VALUES(?,?,?,?,?,?,?,?,?)''', (
        doc_id, session['user_id'], doc_type, label, filename, mime, len(data), _bin(data), now()
    ))
    return jsonify(ok=True, id=doc_id, filename=filename, doc_type=doc_type)

@app.route('/api/suppliers/<sid>/documents')
def list_supplier_documents(sid):
    rows = query('''SELECT id,doc_type,label,filename,mime_type,file_size,uploaded_at
        FROM supplier_documents WHERE supplier_id=? ORDER BY uploaded_at''', (sid,))
    return jsonify(rows)

@app.route('/api/suppliers/documents/<doc_id>')
def download_supplier_document(doc_id):
    row = query('SELECT * FROM supplier_documents WHERE id=?', (doc_id,), one=True)
    if not row:
        return jsonify(error='Not found'), 404
    data = bytes(row['file_data'])
    return send_file(io.BytesIO(data), mimetype=row['mime_type'],
                      as_attachment=False, download_name=row['filename'])

@app.route('/api/suppliers/documents/<doc_id>', methods=['DELETE'])
def delete_supplier_document(doc_id):
    if 'user_id' not in session or session.get('user_type') != 'supplier':
        return jsonify(ok=False, error='Must be logged in as a supplier.'), 401
    row = query('SELECT supplier_id FROM supplier_documents WHERE id=?', (doc_id,), one=True)
    if not row or row['supplier_id'] != session['user_id']:
        return jsonify(ok=False, error='Not found.'), 404
    execute('DELETE FROM supplier_documents WHERE id=?', (doc_id,))
    return jsonify(ok=True)

@app.route('/api/suppliers')
def get_suppliers():
    rows = query('SELECT * FROM suppliers WHERE verified=1 ORDER BY company_name')
    for r in rows:
        r['categories']        = json.loads(r.get('categories') or '[]')
        r['accreditations']    = json.loads(r.get('accreditations') or '[]')
        r['coverage_regions']  = json.loads(r.get('coverage_regions') or '[]')
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
    r['categories']       = json.loads(r.get('categories') or '[]')
    r['accreditations']   = json.loads(r.get('accreditations') or '[]')
    r['coverage_regions'] = json.loads(r.get('coverage_regions') or '[]')
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
    try:
        cust_name = session.get('name', 'Customer')
        email_order_confirmation(order, session['email'], cust_name)
        sup_ids = list(set(i.get('supplierId','') for i in order['items'] if i.get('supplierId')))
        for sid in sup_ids:
            sup = query('SELECT email, contact_first, contact_last, company_name FROM suppliers WHERE id=?', (sid,), one=True)
            if sup:
                sup_name = sup.get('company_name') or (sup.get('contact_first','') + ' ' + sup.get('contact_last','')).strip()
                email_new_order_supplier(order, sup['email'], sup_name)
    except Exception as e:
        print('[Email] Order notification error: ' + str(e))
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
    docs  = query('''SELECT id,supplier_id,doc_type,label,filename,mime_type,file_size,uploaded_at
                      FROM supplier_documents ORDER BY uploaded_at DESC''')
    b     = _get_basket()
    rev   = sum(r['total'] for r in ords)
    return jsonify(customers=custs, suppliers=sups, orders=ords, documents=docs, basket=b,
                   session=_sess() if 'user_id' in session else {},
                   stats=dict(customers=len(custs), suppliers=len(sups), orders=len(ords),
                               revenue=round(rev,2), commission=round(rev*COMMISSION_RATE,2)))

@app.route('/api/admin/reset', methods=['POST'])
def admin_reset():
    db = get_db()
    cur = db.cursor()
    for t in ('customers','suppliers','orders','baskets','reviews','supplier_documents'):
        cur.execute(f'DELETE FROM {t}')
    db.commit()
    session.clear(); _seed(db)
    return jsonify(ok=True, message='Reset and re-seeded.')

# ── Reviews API ──────────────────────────────────────────────────────────────
@app.route('/api/suppliers/<sid>/reviews', methods=['GET'])
def get_reviews(sid):
    reviews = query('SELECT * FROM reviews WHERE supplier_id=? ORDER BY created_at DESC', (sid,))
    avg = round(sum(r['rating'] for r in reviews) / len(reviews), 1) if reviews else 0
    return jsonify(ok=True, reviews=reviews, count=len(reviews), average=avg)

@app.route('/api/suppliers/<sid>/reviews', methods=['POST'])
def post_review(sid):
    if 'user_id' not in session or session.get('user_type') != 'customer':
        return jsonify(ok=False, error='Must be logged in as a customer to leave a review.')
    d = request.json or {}
    rating = int(d.get('rating', 0))
    if not (1 <= rating <= 5):
        return jsonify(ok=False, error='Rating must be between 1 and 5.')
    if not d.get('title','').strip():
        return jsonify(ok=False, error='Please provide a review title.')
    if not d.get('body','').strip():
        return jsonify(ok=False, error='Please provide review comments.')
    rid = 'rev_' + secrets.token_hex(6)
    execute(
        'INSERT INTO reviews(id,supplier_id,customer_id,customer_name,customer_org,rating,title,body,service_used,verified_purchase,created_at) VALUES(?,?,?,?,?,?,?,?,?,0,?)',
        (rid, sid, session['user_id'], session.get('name','Anonymous'),
         session.get('org_name',''), rating,
         d['title'].strip(), d['body'].strip(),
         d.get('service_used',''), now()))
    try:
        sup = query('SELECT email, company_name FROM suppliers WHERE id=?', (sid,), one=True)
        if sup:
            email_new_review(sup['email'], sup['company_name'],
                session.get('name','Anonymous'), session.get('org_name',''),
                rating, d['title'].strip(), sid)
    except Exception as e:
        print('[Email] Review notification error: ' + str(e))
    return jsonify(ok=True, id=rid)

@app.route('/api/reviews/<rid>/respond', methods=['POST'])
def respond_review(rid):
    if 'user_id' not in session or session.get('user_type') != 'supplier':
        return jsonify(ok=False, error='Must be logged in as a supplier to respond.')
    d = request.json or {}
    response_text = d.get('response','').strip()
    if not response_text:
        return jsonify(ok=False, error='Response cannot be empty.')
    rev = query('SELECT * FROM reviews WHERE id=?', (rid,), one=True)
    if not rev:
        return jsonify(ok=False, error='Review not found.')
    if rev['supplier_id'] != session['user_id']:
        return jsonify(ok=False, error='You can only respond to your own reviews.')
    execute('UPDATE reviews SET supplier_response=?, supplier_response_at=? WHERE id=?',
            (response_text, now(), rid))
    return jsonify(ok=True)

# ── Enquiry ───────────────────────────────────────────────────────────────────
@app.route('/api/enquiry', methods=['POST'])
def submit_enquiry():
    d = request.json or {}
    supplier_id = d.get('supplier_id', '')
    service     = d.get('service', 'General Enquiry')
    cust_name   = d.get('name', '').strip()
    cust_org    = d.get('org', '').strip()
    cust_email  = d.get('email', '').strip()
    cust_phone  = d.get('phone', '').strip()
    notes       = d.get('notes', '').strip()
    if not supplier_id or not cust_email:
        return jsonify(ok=False, error='Missing required fields.')
    sup = query('SELECT email, company_name FROM suppliers WHERE id=?', (supplier_id,), one=True)
    if not sup:
        return jsonify(ok=False, error='Supplier not found.')
    try:
        email_new_enquiry(sup['email'], sup['company_name'], cust_name, cust_org, cust_email, cust_phone, service, notes)
    except Exception as e:
        print('[Email] Enquiry error: ' + str(e))
    return jsonify(ok=True, message='Enquiry sent successfully.')

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
    coverage_regions TEXT DEFAULT '[]',
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
CREATE TABLE IF NOT EXISTS reviews(
    id TEXT PRIMARY KEY,
    supplier_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    customer_org TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    service_used TEXT,
    verified_purchase INTEGER DEFAULT 0,
    supplier_response TEXT,
    supplier_response_at TEXT,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS supplier_documents(
    id TEXT PRIMARY KEY,
    supplier_id TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    label TEXT,
    filename TEXT,
    mime_type TEXT,
    file_size INTEGER,
    file_data BYTEA,
    uploaded_at TEXT NOT NULL);
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
        _x('''INSERT INTO customers(id,org_name,org_type,reg_address,phone,first_name,last_name,job_title,email,password_hash,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (id) DO NOTHING''',
            ('cust_demo','Whitmore Estate Services Ltd','Commercial Property Owner',
             '1 Canada Square, London E14 5AB','020 7123 0001',
             'James','Hartley','FM Director','dtait29@hotmail.com',h('Demo123!'),t))
    except: pass

    seed = [
        ('sup_001','Apollo Fire Technicians Ltd','04821033','12 Barbican Centre, London EC2Y 8NB','020 7123 4567','www.apollofire.co.uk','James','Hartley','Operations Director','enquiries@apollofire.co.uk',h('Apollo123!'),'National (England & Wales)','["London","South East","East of England","South West","West Midlands","East Midlands","Wales","Scotland","Northern Ireland"]','["Fire"]','["BAFE","CHAS Premium","ISO 9001","SafeContractor"]','£5 million','£10 million','Apollo Fire Technicians Ltd','20-41-18','80123456','BAFE-certified fire protection specialists with 20+ years of commercial experience.',1),
        ('sup_002','AquaSafe Testing Ltd','07234891','4 Waterside Court, Leeds LS1 4GL','0333 123 9876','www.aquasafe-testing.co.uk','Sarah','Chen','Technical Director','info@aquasafe-testing.co.uk',h('Aqua456!'),'National (England)','["Yorkshire & Humber","North East","North West","East Midlands","West Midlands","East of England","London","South East","Scotland"]','["Water"]','["UKAS Accredited","Legionella Control","ISO 9001","CHAS"]','£5 million','£10 million','AquaSafe Testing Ltd','30-98-12','12345678','UKAS-accredited Legionella and water hygiene specialists.',1),
        ('sup_003','Volt Electrical Compliance Ltd','09871234','Unit 7 Aston Cross Business Village Birmingham B6 5RQ','0121 456 7890','www.voltcompliance.co.uk','Marcus','Williams','Managing Director','contracts@voltcompliance.co.uk',h('Volt789!'),'National (England & Wales)','["West Midlands","East Midlands","Wales","South West","North West","London","East of England","Scotland"]','["Electricity"]','["NICEIC","ECA Member","CHAS","ISO 9001"]','£5 million','£10 million','Volt Electrical Compliance Ltd','40-12-34','87654321','NICEIC-approved electrical testing and compliance specialists.',1),
        ('sup_004','BritHeat Gas Services Ltd','06543210','88 Wellington Street Leeds LS1 2EQ','0113 345 6789','www.britheat.co.uk','David','Okafor','Commercial Manager','service@britheat.co.uk',h('BritHeat1!'),'Regional (multi-county)','["Yorkshire & Humber","North East","East Midlands","Scotland"]','["Gas"]','["Gas Safe","OFTEC","CHAS","ISO 9001"]','£2 million','£5 million','BritHeat Gas Services Ltd','60-23-45','11223344','Gas Safe registered commercial boiler and gas compliance specialists.',1),
        ('sup_005','PureAir HVAC Solutions Ltd','11223344','22 Kings Road Reading RG1 3AR','020 3456 7890','www.pureairhvac.co.uk','Priya','Sharma','Technical Sales Director','hello@pureairhvac.co.uk',h('PureAir2!'),'National (England)','["South East","London","South West","East of England","West Midlands","Yorkshire & Humber","North West","Scotland"]','["HVAC"]','["REFCOM","F-Gas Certified","CHAS","SafeContractor"]','£5 million','£10 million','PureAir HVAC Solutions Ltd','20-33-99','55667788','F-Gas certified HVAC and air conditioning specialists.',1),
    ]
    # 5 additional suppliers for remaining compliance categories
    extra = [
        ('sup_006','ClearLift Services Ltd','08234567','Unit 4 Lenton Business Centre Nottingham NG7 2BY','0115 987 3456','www.clearlift.co.uk','Paul','Dixon','Managing Director','service@clearlift.co.uk',h('ClearLift1!'),'National (England & Wales)','["East Midlands","West Midlands","Yorkshire & Humber","East of England","Wales","London","South East","Scotland"]','["Lifts & Lifting Equipment"]','["LEIA Member","LOLER Certified","ISO 9001","CHAS"]','£5 million','£10 million','ClearLift Services Ltd','60-44-21','22334455','LEIA-member lift maintenance and LOLER inspection specialists with national coverage.',1),
        ('sup_007','SafeAir Asbestos Consultancy Ltd','05678901','15 Temple Row Birmingham B2 5LG','0121 233 4567','www.safeair-asbestos.co.uk','Helen','Marsh','Technical Director','surveys@safeair-asbestos.co.uk',h('SafeAir1!'),'National (England & Wales)','["West Midlands","Wales","East Midlands","North West","South West","South East","London","Scotland"]','["Asbestos"]','["UKAS Accredited","BOHS P402","ISO 17025","CHAS"]','£5 million','£10 million','SafeAir Asbestos Consultancy Ltd','40-55-33','33445566','UKAS-accredited asbestos management survey and consultancy specialists.',1),
        ('sup_008','CoolEdge Climate Ltd','06789012','7 Rutherford Way Cheltenham GL51 9TU','01242 512 890','www.cooledgeclimate.co.uk','Adam','Foster','Operations Manager','info@cooledgeclimate.co.uk',h('CoolEdge1!'),'National (England)','["South West","South East","West Midlands","London","East Midlands","East of England","Scotland"]','["Air Conditioning"]','["REFCOM","F-Gas Certified","SafeContractor","CHAS"]','£5 million','£5 million','CoolEdge Climate Ltd','30-77-44','44556677','F-Gas certified air conditioning maintenance specialists covering split, multi-split and VRF systems.',1),
        ('sup_009','PressureSafe Engineering Ltd','07890123','33 Sovereign Way Tonbridge TN9 1RH','01732 360 450','www.pressuresafe.co.uk','Kevin','Obi','Chief Engineer','inspect@pressuresafe.co.uk',h('PressureSafe1!'),'National (England & Wales)','["South East","London","South West","East of England","West Midlands","North West","Scotland"]','["Pressure Vessels"]','["PSSR Certified","ISO 9001","CHAS","SafeContractor"]','£5 million','£10 million','PressureSafe Engineering Ltd','50-66-77','55667788','PSSR-competent pressure vessel inspection and chiller maintenance specialists.',1),
        ('sup_010','RiskFirst Consultancy Ltd','09012345','20 St James Street London SW1A 1ES','020 7930 1234','www.riskfirst.co.uk','Natasha','Okonkwo','Head of Consulting','hello@riskfirst.co.uk',h('RiskFirst1!'),'National','["London","South East","South West","East of England","West Midlands","East Midlands","North West","Yorkshire & Humber","North East","Wales","Scotland"]','["Risk Assessments"]','["NEBOSH","IOSH Member","ISO 45001","SafeContractor"]','£5 million','£10 million','RiskFirst Consultancy Ltd','20-99-11','66778899','NEBOSH and IOSH-qualified risk assessment consultancy for commercial and mixed-use estates.',1),
    ]
    # Insert original 5 suppliers FIRST (services reference them)
    for s in seed:
        try:
            _x('''INSERT INTO suppliers(id,company_name,company_reg,reg_address,main_tel,website,
                contact_first,contact_last,contact_role,email,password_hash,coverage,coverage_regions,categories,
                accreditations,pl_insurance,el_insurance,bank_name,sort_code,account_num,company_desc,verified,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (id) DO NOTHING''', s+(t,))
        except Exception as e:
            print(f'  Seed warning (sup): {e}')

    # Then insert 5 extra suppliers
    for s in extra:
        try:
            _x('''INSERT INTO suppliers(id,company_name,company_reg,reg_address,main_tel,website,
                contact_first,contact_last,contact_role,email,password_hash,coverage,coverage_regions,categories,
                accreditations,pl_insurance,el_insurance,bank_name,sort_code,account_num,company_desc,verified,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (id) DO NOTHING''', s+(t,))
        except Exception as e:
            print(f'  Seed warning (extra): {e}')

    # Sync coverage_regions for the 10 known seed suppliers on every boot.
    # ON CONFLICT DO NOTHING above means the INSERT is skipped entirely for suppliers
    # that already exist, so their coverage_regions would otherwise never update when
    # this seed data changes (e.g. broadening a supplier's coverage in a later session).
    # This is safe because sup_001–sup_010 are demo/seed suppliers, not real customer data —
    # do NOT use this unconditional-overwrite pattern for any future real supplier-editable field.
    region_backfill = {s[0]: s[12] for s in (seed + extra)}
    for sid, regions_json in region_backfill.items():
        try:
            _x('UPDATE suppliers SET coverage_regions=? WHERE id=?', (regions_json, sid))
        except Exception as e:
            print(f'  Backfill warning (coverage_regions {sid}): {e}')

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
            _x('''INSERT INTO services(id,supplier_id,name,description,unit_label,unit_price_pennies,active)
                VALUES(?,?,?,?,?,?,1) ON CONFLICT (id) DO NOTHING''', s)
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

    # ── Seed reviews ────────────────────────────────────────────────────────
    REVIEWS = [
        ('rev_001','sup_001','cust_demo','James Hartley','Whitmore Estate Services Ltd',5,'Exceptional fire alarm service','Apollo Fire have been maintaining our fire alarm systems for two years. Response times are outstanding and their engineers always arrive on time and fully prepared. Digital logbook is a real bonus.','Fire Alarm PPM Visit',1),
        ('rev_002','sup_001','cust_r02','Sarah Chen','Meridian Property Group',5,'Best fire contractor we have used','Switched to Apollo after a poor experience elsewhere. The difference is night and day. Fully BAFE certified, always compliant, and the team communicate brilliantly.','Fire Extinguisher Service',1),
        ('rev_003','sup_001','cust_r03','David Okafor','Langham Estates Ltd',5,'Highly recommended','Professional, thorough and competitively priced. Our compliance audits have been spotless since appointing Apollo.','Fire Alarm PPM Visit',1),
        ('rev_004','sup_001','cust_r04','Emma Thornton','Nexus FM Solutions',4,'Very good, minor scheduling issue','Excellent technical quality. Only reason for 4 stars is one rescheduled visit at short notice. Otherwise flawless.','Fire Door Checks',1),
        ('rev_005','sup_002','cust_demo','James Hartley','Whitmore Estate Services Ltd',5,'Thorough legionella management','AquaSafe completely overhauled our water hygiene programme. Their sampling reports are detailed and easy to understand. Highly compliant.','Legionella Water Sampling',1),
        ('rev_006','sup_002','cust_r02','Sarah Chen','Meridian Property Group',5,'Excellent water hygiene service','Prompt, professional and their risk assessments are comprehensive. We have had zero issues since appointment.','Monthly Sentinel Outlet Checks',1),
        ('rev_007','sup_002','cust_r03','David Okafor','Langham Estates Ltd',4,'Good service, reports could be faster','Technically very competent. Water sampling results sometimes take a few extra days to arrive but quality is high.','Legionella Water Sampling',1),
        ('rev_008','sup_002','cust_r05','Priya Sharma','BlueSky Facilities',5,'Saved us from a compliance failure','AquaSafe identified a Legionella risk that our previous contractor had missed entirely. Exceptional attention to detail.','Legionella Water Sampling',1),
        ('rev_009','sup_003','cust_demo','James Hartley','Whitmore Estate Services Ltd',5,'Excellent EICR service','Volt completed our full site EICR efficiently and the report was clear and actionable. All remedials quoted fairly.','EICR Inspection',1),
        ('rev_010','sup_003','cust_r02','Sarah Chen','Meridian Property Group',4,'Competent and reliable','Good engineers, solid compliance knowledge. Occasionally hard to reach by phone but work quality is consistently high.','Emergency Lighting Test',1),
        ('rev_011','sup_003','cust_r04','Emma Thornton','Nexus FM Solutions',5,'Transformed our electrical compliance','Volt identified several urgent remedials our previous contractor had overlooked. Very thorough.','EICR Inspection',1),
        ('rev_012','sup_003','cust_r06','Marcus Webb','Crown Commercial Estates',4,'Good value EICR','Competitive pricing, professional engineers and a well-structured report. Would use again.','EICR Inspection',1),
        ('rev_013','sup_004','cust_demo','James Hartley','Whitmore Estate Services Ltd',5,'Superb boiler servicing','BritHeat have kept our commercial boilers running perfectly. Their engineers are knowledgeable and efficient.','Commercial Boiler Service',1),
        ('rev_014','sup_004','cust_r03','David Okafor','Langham Estates Ltd',4,'Reliable gas safety','Professional gas safety inspections. Certificates issued promptly and all work fully documented.','Gas Safety Inspection',1),
        ('rev_015','sup_004','cust_r05','Priya Sharma','BlueSky Facilities',5,'Prevented a costly breakdown','BritHeat spotted a developing fault during routine service that would have caused a complete boiler failure mid-winter. Excellent work.','Commercial Boiler Service',1),
        ('rev_016','sup_004','cust_r06','Marcus Webb','Crown Commercial Estates',4,'Good service overall','Competent team, responsive to urgent callouts. Minor paperwork delays occasionally but nothing serious.','Gas Safety Inspection',1),
        ('rev_017','sup_005','cust_demo','James Hartley','Whitmore Estate Services Ltd',5,'Outstanding HVAC maintenance','PureAir have dramatically improved air quality across our portfolio. PPM visits are thorough and their filter change reports are excellent.','Quarterly HVAC PPM Visit',1),
        ('rev_018','sup_005','cust_r02','Sarah Chen','Meridian Property Group',5,'Highly professional team','Engineers are punctual, tidy and technically excellent. Our AHU performance has improved significantly.','AHU Filter Change',1),
        ('rev_019','sup_005','cust_r04','Emma Thornton','Nexus FM Solutions',4,'Good HVAC partner','Solid maintenance programme, good communication. Slightly slow on issuing service reports but work quality is high.','Quarterly HVAC PPM Visit',1),
        ('rev_020','sup_005','cust_r06','Marcus Webb','Crown Commercial Estates',5,'Best HVAC contractor we have used','Switched to PureAir after persistent problems with our previous contractor. Immediately noticed the improvement.','AHU Filter Change',1),
        ('rev_021','sup_006','cust_demo','James Hartley','Whitmore Estate Services Ltd',5,'Excellent lift maintenance','ClearLift keep our passenger lifts running reliably. LOLER inspections are thorough and certificates issued same day.','Passenger Lift Maintenance',1),
        ('rev_022','sup_006','cust_r03','David Okafor','Langham Estates Ltd',4,'Reliable and compliant','Good technical team, always LOLER compliant. Response to breakdowns is quick which is critical for our buildings.','LOLER Inspection',1),
        ('rev_023','sup_006','cust_r05','Priya Sharma','BlueSky Facilities',5,'Zero lift failures in 18 months','Since appointing ClearLift we have had zero lift failures. Their preventative maintenance programme is clearly effective.','Passenger Lift Maintenance',1),
        ('rev_024','sup_006','cust_r06','Marcus Webb','Crown Commercial Estates',4,'Good value maintenance','Competitive contract pricing and a professional team. Minor admin delays occasionally but operationally excellent.','LOLER Inspection',1),
        ('rev_025','sup_007','cust_demo','James Hartley','Whitmore Estate Services Ltd',5,'Comprehensive asbestos surveys','SafeAir produced the most detailed asbestos management survey we have ever received. Register is clear and fully actionable.','Asbestos Management Survey',1),
        ('rev_026','sup_007','cust_r02','Sarah Chen','Meridian Property Group',5,'Exceptional survey quality','The level of detail in SafeAir reports is remarkable. Found asbestos-containing materials two previous surveyors had missed.','Asbestos R&D Survey',1),
        ('rev_027','sup_007','cust_r04','Emma Thornton','Nexus FM Solutions',5,'Highly professional surveyors','Thorough, compliant and excellent communicators. Our asbestos management is now fully under control.','Asbestos Management Survey',1),
        ('rev_028','sup_007','cust_r06','Marcus Webb','Crown Commercial Estates',4,'Very good asbestos management','High quality surveys and a well-maintained register. Slightly premium pricing but the quality justifies it.','Asbestos Management Survey',1),
        ('rev_029','sup_008','cust_demo','James Hartley','Whitmore Estate Services Ltd',4,'Good AC maintenance','CoolEdge keep our air conditioning units well maintained. Engineers are knowledgeable and PPM visits thorough.','Split System AC Service',1),
        ('rev_030','sup_008','cust_r03','David Okafor','Langham Estates Ltd',5,'Excellent VRF specialists','CoolEdge have real expertise in VRF systems. Their diagnostic work on a fault that stumped our previous contractor was impressive.','VRF System PPM Visit',1),
        ('rev_031','sup_008','cust_r05','Priya Sharma','BlueSky Facilities',4,'Reliable AC servicing','Consistent service quality, good compliance documentation. Response to breakdowns could be slightly faster.','Split System AC Service',1),
        ('rev_032','sup_008','cust_r06','Marcus Webb','Crown Commercial Estates',5,'Transformed our AC reliability','Following a full system service our AC breakdown rate dropped by over 80 percent. Excellent preventative work.','VRF System PPM Visit',1),
        ('rev_033','sup_009','cust_demo','James Hartley','Whitmore Estate Services Ltd',5,'Thorough pressure vessel inspections','PressureSafe carry out our statutory pressure vessel inspections efficiently. Reports are detailed and issued promptly.','Pressure Vessel Inspection',1),
        ('rev_034','sup_009','cust_r02','Sarah Chen','Meridian Property Group',4,'Competent inspection service','Professional inspectors, good compliance knowledge. We have been fully compliant since appointing PressureSafe.','Chiller Maintenance Visit',1),
        ('rev_035','sup_009','cust_r04','Emma Thornton','Nexus FM Solutions',5,'Excellent chiller maintenance','PressureSafe significantly extended the life of our ageing chiller plant through proactive maintenance. Great value.','Chiller Maintenance Visit',1),
        ('rev_036','sup_009','cust_r06','Marcus Webb','Crown Commercial Estates',4,'Good inspection service','Reliable, competent and thorough. Minor delays in issuing certificates occasionally but nothing that has caused compliance issues.','Pressure Vessel Inspection',1),
        ('rev_037','sup_010','cust_demo','James Hartley','Whitmore Estate Services Ltd',5,'Outstanding fire risk assessments','RiskFirst produced the most comprehensive fire risk assessment we have seen. Actionable recommendations and excellent follow-up.','Fire Risk Assessment',1),
        ('rev_038','sup_010','cust_r03','David Okafor','Langham Estates Ltd',5,'Excellent risk consultancy','Thorough, professional and highly knowledgeable. Their FRA identified several issues our previous assessor had overlooked.','Fire Risk Assessment',1),
        ('rev_039','sup_010','cust_r05','Priya Sharma','BlueSky Facilities',4,'Good DSE assessments','Professional workstation assessments, well-presented reports. Slightly slow turnaround on final reports.','DSE Workstation Assessment',1),
        ('rev_040','sup_010','cust_r06','Marcus Webb','Crown Commercial Estates',5,'Transformed our compliance posture','RiskFirst conducted a full compliance audit across our estate. The quality of their work has been transformative.','Fire Risk Assessment',1),
    ]
    t = now()
    for r in REVIEWS:
        try:
            _x("""INSERT INTO reviews(id,supplier_id,customer_id,customer_name,customer_org,rating,title,body,service_used,verified_purchase,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (id) DO NOTHING""",
                r + (t,))
        except Exception as e:
            print(f'  Seed warning (review): {e}')

    if close:
        try: db.close()
        except: pass


def _migrate(db):
    """Add columns that may be missing on databases created before this version."""
    if USE_POSTGRES:
        cur = db.cursor()
        try:
            cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS coverage_regions TEXT DEFAULT '[]'")
            db.commit()
        except Exception as e:
            print(f'  Migration warning (coverage_regions): {e}')
            try: db.rollback()
            except: pass
    else:
        cur = db.cursor()
        cur.execute("PRAGMA table_info(suppliers)")
        cols = [r[1] for r in cur.fetchall()]
        if 'coverage_regions' not in cols:
            try:
                cur.execute("ALTER TABLE suppliers ADD COLUMN coverage_regions TEXT DEFAULT '[]'")
                db.commit()
            except Exception as e:
                print(f'  Migration warning (coverage_regions): {e}')

def init_db():
    if USE_POSTGRES:
        db = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = db.cursor()
        for stmt in SCHEMA.strip().split(';'):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        db.commit()
        _migrate(db)
        db.close()
    else:
        import sqlite3 as _sq3
        db = _sq3.connect(DB_PATH)
        db.executescript(SCHEMA)
        db.commit()
        _migrate(db)
        db.close()

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
