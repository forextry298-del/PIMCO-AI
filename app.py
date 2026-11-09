import os, sqlite3, secrets, datetime, json
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "pimco-local-demo-change-this")
DB = os.path.join(app.root_path, "instance", "amazon.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            phone TEXT UNIQUE,
            username TEXT UNIQUE,
            country TEXT DEFAULT 'Uganda (UGX)',
            password_hash TEXT NOT NULL,
            referral_code TEXT UNIQUE NOT NULL
        )""")
        columns = {row["name"] for row in con.execute("PRAGMA table_info(users)")}
        if "phone" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN phone TEXT")
            if "email" in columns:
                con.execute("UPDATE users SET phone=email WHERE phone IS NULL")
        if "username" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "country" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN country TEXT DEFAULT 'Uganda (UGX)'")
        if "is_blocked" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0")
        if "referred_by" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        if "wallet_balance" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN wallet_balance REAL NOT NULL DEFAULT 0")
        if "balance" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN balance REAL NOT NULL DEFAULT 0")
        con.execute("""CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            machine_code TEXT NOT NULL,
            machine_name TEXT NOT NULL,
            price REAL NOT NULL,
            payment_source TEXT NOT NULL CHECK(payment_source IN ('wallet','balance')),
            purchased_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
        purchase_cols = {r['name'] for r in con.execute("PRAGMA table_info(purchases)")}
        for col, ddl in [("daily_income", "REAL NOT NULL DEFAULT 0"), ("duration_days", "INTEGER NOT NULL DEFAULT 0"), ("lock_days", "INTEGER NOT NULL DEFAULT 0")]:
            if col not in purchase_cols: con.execute(f"ALTER TABLE purchases ADD COLUMN {col} {ddl}")
        con.execute("""CREATE TABLE IF NOT EXISTS wallet_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_type TEXT NOT NULL,
            amount REAL NOT NULL,
            source TEXT NOT NULL,
            reference TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            amount REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending',
            approved_at TEXT, FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, amount REAL NOT NULL,
            phone TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT, FOREIGN KEY(user_id) REFERENCES users(id))""")
        con.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, kind TEXT NOT NULL,
            amount REAL NOT NULL, status TEXT NOT NULL DEFAULT 'pending', reference TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        con.execute("""CREATE TABLE IF NOT EXISTS machine_settings (
            code TEXT PRIMARY KEY, sold_out INTEGER NOT NULL DEFAULT 0, image TEXT, price REAL, daily REAL, days INTEGER, lock_days INTEGER NOT NULL DEFAULT 0)""")
        con.execute("""CREATE TABLE IF NOT EXISTS daily_earnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, purchase_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            earning_date TEXT NOT NULL, amount REAL NOT NULL, UNIQUE(purchase_id,earning_date))""")
        con.execute("""CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER, recipient_id INTEGER, is_admin INTEGER DEFAULT 0,
            body TEXT, image_name TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        con.execute("""CREATE TABLE IF NOT EXISTS vip_reward_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            vip_level INTEGER NOT NULL, reward REAL NOT NULL,
            credited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id,vip_level), FOREIGN KEY(user_id) REFERENCES users(id)
        )""")

def make_invite_code(con):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(100):
        code = "".join(secrets.choice(alphabet) for _ in range(5))
        if not con.execute("SELECT 1 FROM users WHERE referral_code=?", (code,)).fetchone():
            return code
    raise RuntimeError("Unable to generate a unique invitation code")

init_db()
with db() as con:
    seen=set()
    for row in con.execute("SELECT id, referral_code FROM users ORDER BY id").fetchall():
        code=(row["referral_code"] or "").strip().upper()
        if len(code)!=5 or code in seen:
            code=make_invite_code(con)
            con.execute("UPDATE users SET referral_code=? WHERE id=?", (code,row["id"]))
        seen.add(code)

def logged_in():
    return bool(session.get("user_id"))

@app.route("/")
def home():
    if not logged_in():
        return redirect(url_for("auth"))
    show_login_notice = bool(session.pop("show_login_notice", False))
    uid = session["user_id"]
    with db() as admin_con:
        admin_row=admin_con.execute("SELECT phone FROM users WHERE id=?", (uid,)).fetchone()
    admin_digits="".join(ch for ch in str(admin_row["phone"] or "") if ch.isdigit()) if admin_row else ""
    admin_access=admin_digits.endswith("758878297")

    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date().isoformat()
    with db() as con:
        con.execute("CREATE TABLE IF NOT EXISTS team_commissions (id INTEGER PRIMARY KEY AUTOINCREMENT, deposit_id INTEGER NOT NULL, depositor_id INTEGER NOT NULL, beneficiary_id INTEGER NOT NULL, level INTEGER NOT NULL, amount REAL NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(deposit_id,beneficiary_id,level))")
        ai_income=con.execute("SELECT COALESCE(SUM(amount),0) FROM daily_earnings WHERE user_id=?",(uid,)).fetchone()[0] or 0
        today_income=con.execute("SELECT COALESCE(SUM(amount),0) FROM daily_earnings WHERE user_id=? AND earning_date IN (?,?)",(uid,today,"LOCKED-"+today)).fetchone()[0] or 0
        deposit_total=con.execute("SELECT COALESCE(SUM(amount),0) FROM deposits WHERE user_id=? AND LOWER(status)='approved'",(uid,)).fetchone()[0] or 0
        withdrawal_total=con.execute("SELECT COALESCE(SUM(amount),0) FROM withdrawals WHERE user_id=? AND LOWER(status) IN ('approved','pending')",(uid,)).fetchone()[0] or 0
        invite_count=con.execute("SELECT COUNT(*) FROM users WHERE referred_by=?",(uid,)).fetchone()[0]
        lv1=[r[0] for r in con.execute("SELECT id FROM users WHERE referred_by=?",(uid,)).fetchall()]
        lv2=[]
        for parent in lv1:
            lv2.extend(r[0] for r in con.execute("SELECT id FROM users WHERE referred_by=?",(parent,)).fetchall())
        lv3=[]
        for parent in lv2:
            lv3.extend(r[0] for r in con.execute("SELECT id FROM users WHERE referred_by=?",(parent,)).fetchall())
        team_count=len(lv1)+len(lv2)+len(lv3)
        team_income=con.execute("SELECT COALESCE(SUM(amount),0) FROM team_commissions WHERE beneficiary_id=?",(uid,)).fetchone()[0] or 0
    metrics={"deposit_total":float(deposit_total),"withdrawal_total":float(withdrawal_total),"ai_income":float(ai_income),"today_income":float(today_income),"invite_count":int(invite_count),"team_count":int(team_count),"team_income":float(team_income)}
    return render_template("home.html",active="home",show_login_notice=show_login_notice,metrics=metrics,admin_access=admin_access)
@app.route("/auth", methods=["GET", "POST"])
def auth():
    mode = request.args.get("mode", "signin")
    invite_code = request.args.get("ref", "").strip().upper()
    if request.method == "POST":
        mode = request.form.get("mode", "signin")
        identity = request.form.get("identity", "").strip()
        password = request.form.get("password", "")
        if mode == "signup":
            confirm_password = request.form.get("confirm_password", "")
            username = request.form.get("username", "").strip()
            country = request.form.get("country", "Uganda (UGX)").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip().lower()
            invite_code = request.form.get("invite_code", "").strip().upper()
            if not phone or not password or not confirm_password or len(password) < 8 or password != confirm_password:
                flash("Enter your phone number, use at least 8 password characters, and make sure both passwords match.")
            else:
                try:
                    with db() as con:
                        inviter = con.execute("SELECT id FROM users WHERE UPPER(referral_code)=?", (invite_code,)).fetchone() if invite_code else None
                        cur = con.execute(
                            "INSERT INTO users(email,phone,username,country,password_hash,referral_code,referred_by) VALUES(?,?,?,?,?,?,?)",
                            (None, phone, None, "Uganda (UGX)", generate_password_hash(password), make_invite_code(con), inviter["id"] if inviter else None)
                        )
                        user_id = cur.lastrowid
                    session["user_id"] = user_id
                    session["phone"] = phone
                    session["username"] = ""
                    session["show_login_notice"] = True
                    return redirect(url_for("home"))
                except sqlite3.IntegrityError:
                    flash("This phone number is already registered.")
        else:
            with db() as con:
                user = con.execute(
                    "SELECT * FROM users WHERE phone=? OR email=? OR username=?",
                    (identity, identity.lower(), identity)
                ).fetchone()
            if user and check_password_hash(user["password_hash"], password):
                session["user_id"] = user["id"]
                session["phone"] = user["phone"] or ""
                session["username"] = user["username"] or ""
                session["show_login_notice"] = True
                return redirect(url_for("home"))
            flash("Username, email, phone or password is incorrect.")
    return render_template("auth.html", mode=mode, invite_code=invite_code)
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth"))

@app.route("/my")
def my():
    if not logged_in(): return redirect(url_for("auth"))
    with db() as con:
        user = con.execute("SELECT referral_code, COALESCE(wallet_balance,0) AS wallet_balance, COALESCE(balance,0) AS balance FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return render_template("my.html", active="my", referral=user["referral_code"] if user else "",
        wallet_balance=float(user["wallet_balance"] or 0) if user else 0,
        balance=float(user["balance"] or 0) if user else 0)

@app.route("/ai")
def ai():
    if not logged_in(): return redirect(url_for("auth"))
    series = request.args.get("series", "ALL").upper()
    if series not in ("ALL", "A", "B", "LV", "K", "D", "VIP"):
        series = "ALL"
    return render_template("ai.html", active="ai", series=series)



# Local PIMCO AI platform FAQ assistant. This is not connected to an external LLM.
def pimco_ai_answer(message):
    q=(message or '').strip().lower()
    if not q: return 'Please type a question about PIMCO AI.'
    if any(x in q for x in ('legit','legitimate','real company','scam','trustworthy','safe to invest')):
        return ('I can explain the features shown on this PIMCO AI website, but I cannot independently verify that the company is legitimate, licensed, financially safe, or that withdrawals will be paid. Before depositing, independently verify the legal company name, registration and any required financial authorization with the relevant regulator. Check independently documented withdrawals and do not invest money you cannot afford to lose.')
    if any(x in q for x in ('deposit','add money','recharge','fund wallet')):
        return 'Open Deposit, enter the amount and required Mobile Money details, then submit. A deposit should only be treated as credited after it is verified and approved. Check the minimum and payment instructions shown in your account before paying.'
    if any(x in q for x in ('withdraw','cash out','payout')):
        return 'Open Withdraw, enter the amount, receiving Mobile Money number and network, then submit. The request may remain pending while reviewed. Check the minimum and any fee displayed on the Withdrawal page before confirming.'
    if 'wallet' in q: return 'Wallet is the deposit-funds balance. It is separate from Balance, which represents platform earnings. Check your transaction history for confirmed entries.'
    if any(x in q for x in ('balance','earning','income','daily return')):
        return 'Balance is shown separately from Wallet and represents platform earnings in this project. Displayed machine or plan figures are not a guarantee of profit or payment. Review the actual terms and your transaction history.'
    if any(x in q for x in ('referral','invite','team','commission','level')):
        return 'Use Invite or My Team to view your referral link and team information. Commissions depend on configured levels and qualifying approved deposits. Check the team and ledger records to confirm any commission credited.'
    if any(x in q for x in ('machine','plan','vip','series','purchase')):
        return 'Open the AI tab to browse machine series and their displayed prices, daily figures and terms. These figures are platform information, not independently verified returns. Read the lock period and terms before purchasing.'
    if any(x in q for x in ('account','password','profile','settings','login','register')):
        return 'Use My → Settings for account options. Keep your password private. Never share your password or one-time verification codes.'
    if any(x in q for x in ('support','manager','help','contact')):
        return 'For account-specific help, use the Manager or support contact shown inside your account. Never share your password, PIN or one-time verification code.'
    if any(x in q for x in ('hello','hi','hey','good morning','good evening')):
        return 'Hello! I am the PIMCO AI platform assistant. Ask about deposits, withdrawals, Wallet, Balance, machines, referrals or account settings.'
    return 'I can help with deposits, withdrawals, Wallet versus Balance, machine plans, referrals, commissions and account settings. Try asking one of those questions. For account-specific records, check your transaction history or contact support.'

@app.route('/assistant', methods=['GET','POST'])
def assistant_chat():
    if not logged_in(): return redirect(url_for('auth'))
    if request.method == 'POST':
        data=request.get_json(silent=True) or {}
        message=str(data.get('message','')).strip()[:700]
        if not message: return jsonify({'reply':'Please type a question.'}),400
        return jsonify({'reply':pimco_ai_answer(message)})
    return render_template('assistant.html', active='ai')

MACHINE_CATALOG = [
    {"code":"A1","series":"A","image":"machine-a1.jpg","price":30000,"daily":3000,"days":16,"lock":"16 days"},
    {"code":"A2","series":"A","image":"machine-a2.jpg","price":97000,"daily":9700,"days":20,"lock":"20 days"},
    {"code":"A3","series":"A","image":"machine-a3.jpg","price":120000,"daily":16300,"days":18,"lock":"18 days"},
    {"code":"B1","series":"B","image":"machine-b1.jpg","price":48000,"daily":14400,"days":5,"lock":"5 days"},
    {"code":"B2","series":"B","image":"machine-b2.jpg","price":80000,"daily":24000,"days":5,"lock":"5 days"},
    {"code":"B3","series":"B","image":"machine-b3.jpg","price":100000,"daily":30000,"days":5,"lock":"5 days"},
    {"code":"B4","series":"B","image":"machine-b4.jpg","price":350000,"daily":105000,"days":5,"lock":"5 days"},
    {"code":"LV1","series":"LV","image":"machine-lv1.jpg","price":50000,"daily":9820,"days":150,"lock":"150 days"},
    {"code":"LV2-75","series":"LV","image":"machine-lv2.jpg","price":75000,"daily":17300,"days":180,"lock":"No lock"},
    {"code":"LV2-100","series":"LV","image":"machine-lv2.jpg","price":100000,"daily":23000,"days":120,"lock":"120 days"},
    {"code":"LV3","series":"LV","image":"machine-lv3.jpg","price":250000,"daily":40000,"days":90,"lock":"No lock"},
    {"code":"LV4","series":"LV","image":"machine-lv4.jpg","price":500000,"daily":95000,"days":10,"lock":"No lock"},
    {"code":"K1","series":"K","image":"machine-k1.jpg","price":50000,"daily":30000,"days":2,"lock":"2 days"},
    {"code":"K2","series":"K","image":"machine-k2.jpg","price":100000,"daily":70000,"days":2,"lock":"2 days"},
    {"code":"K3","series":"K","image":"machine-k3.jpg","price":140000,"daily":98000,"days":2,"lock":"2 days"},
    {"code":"K4","series":"K","image":"machine-k4.jpg","price":200000,"daily":150000,"days":2,"lock":"2 days"},
    {"code":"D1","series":"D","image":"machine-d1.jpg","price":1000000,"daily":470000,"days":4,"lock":"No lock"},
    {"code":"D2","series":"D","image":"machine-d2.jpg","price":2000000,"daily":950000,"days":4,"lock":"No lock"},
]
for _i, _price, _daily, _img in [
    (1,10000,4000,"vip1.jpg"),(2,20000,7000,"vip2.jpg"),
    (3,50000,10000,"vip3.jpg"),(4,100000,50000,"vip4.jpg"),
    (5,200000,100000,"vip5.jpg"),(6,320000,180000,"vip6.jpg"),
    (7,500000,250000,"vip7.jpg"),(8,860000,430000,"vip8.jpg"),
    (9,1000000,500000,"vip9.jpg"),(10,5000000,1000000,"vip10.jpg")]:
    MACHINE_CATALOG.append({"code":f"VIP{_i}","series":"VIP","image":_img,"price":_price,"daily":_daily,"days":10,"lock":"No lock"})

def machine_by_code(code):
    return next((m for m in MACHINE_CATALOG if m["code"].lower() == code.lower()), None)

@app.route("/machine/<code>")
def machine_detail(code):
    if not logged_in(): return redirect(url_for("auth"))
    machine = machine_by_code(code)
    if not machine: return redirect(url_for("ai"))
    with db() as con:
        user = con.execute("SELECT wallet_balance,balance FROM users WHERE id=?", (session["user_id"],)).fetchone()
    machine = dict(machine)
    machine["total"] = machine["daily"] * machine["days"]
    return render_template("machine_detail.html", machine=machine,
        wallet_balance=user["wallet_balance"], balance=user["balance"],
        vip=(machine["series"] == "VIP"))

@app.route("/machine/<code>/purchase", methods=["POST"])
def machine_purchase(code):
    if not logged_in(): return redirect(url_for("auth"))
    machine = machine_by_code(code)
    if not machine: return redirect(url_for("ai"))
    with db() as con:
        sold = con.execute("SELECT sold_out FROM machine_settings WHERE code=?", (machine["code"],)).fetchone()
    if sold and sold["sold_out"]:
        flash("SOLD OUT", "error"); return redirect(url_for("machine_detail", code=code))
    source = request.form.get("payment_source", "balance")
    if machine["series"] == "VIP":
        source = "balance"
    if source not in ("wallet", "balance"): source = "balance"
    col = "wallet_balance" if source == "wallet" else "balance"
    try:
        with db() as con:
            con.execute("BEGIN IMMEDIATE")
            user = con.execute(f"SELECT {col} AS funds FROM users WHERE id=?", (session["user_id"],)).fetchone()
            if not user or float(user["funds"] or 0) < machine["price"]:
                flash("Insufficient funds. Please add funds to the selected account.", "error")
                return redirect(url_for("machine_detail", code=code))
            con.execute(f"UPDATE users SET {col} = {col} - ? WHERE id=? AND {col} >= ?",
                        (machine["price"], session["user_id"], machine["price"]))
            if con.total_changes < 1:
                flash("Insufficient funds. No amount was deducted.", "error")
                return redirect(url_for("machine_detail", code=code))
            con.execute("INSERT INTO purchases(user_id,machine_code,machine_name,price,payment_source,daily_income,duration_days,lock_days) VALUES(?,?,?,?,?,?,?,?)",
                        (session["user_id"], machine["code"], machine["code"], machine["price"], source, machine["daily"], machine["days"], 0 if machine["lock"] == "No lock" else machine["days"]))
            con.execute("INSERT INTO wallet_ledger(user_id,entry_type,amount,source,reference) VALUES(?,?,?,?,?)",
                        (session["user_id"], "debit", machine["price"], f"machine_purchase_{source}", machine["code"]))
        flash("Purchase successful.", "success")
    except sqlite3.Error:
        flash("Purchase could not be completed. No purchase was recorded.", "error")
    return redirect(url_for("machine_detail", code=code))

VIP_TASKS = [
    (1, 2, 30000), (2, 5, 80000), (3, 30, 100000), (4, 50, 200000),
    (5, 100, 400000), (6, 180, 800000), (7, 450, 1600000),
    (8, 650, 4000000), (9, 850, 10000000), (10, 1500, 50000000),
]

def process_vip_rewards(con, user_id):
    """Credit each eligible VIP reward once; call after deposit approval as well as on page load."""
    credited = []
    for level, required, reward in VIP_TASKS:
        count = con.execute(
            "SELECT COUNT(DISTINCT u.id) FROM users u WHERE u.referred_by=? AND EXISTS (SELECT 1 FROM deposits d WHERE d.user_id=u.id AND LOWER(d.status)='approved')",
            (user_id,)
        ).fetchone()[0]
        if count >= required:
            cur = con.execute(
                "INSERT OR IGNORE INTO vip_reward_claims(user_id,vip_level,reward) VALUES(?,?,?)",
                (user_id, level, reward)
            )
            if cur.rowcount:
                con.execute("UPDATE users SET balance=COALESCE(balance,0)+? WHERE id=?", (reward, user_id))
                con.execute("INSERT INTO wallet_ledger(user_id,entry_type,amount,source,reference) VALUES(?,?,?,?,?)",
                            (user_id, "credit", reward, "vip_task_reward", f"VIP{level}"))
                credited.append(level)
    return credited

@app.route("/vip-task")
def vip_task():
    if not logged_in(): return redirect(url_for("auth"))
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        credited = process_vip_rewards(con, session["user_id"])
        rows = []
        for level, required, reward in VIP_TASKS:
            count = con.execute(
                "SELECT COUNT(DISTINCT u.id) FROM users u WHERE u.referred_by=? AND EXISTS (SELECT 1 FROM deposits d WHERE d.user_id=u.id AND LOWER(d.status)='approved')",
                (session["user_id"],)
            ).fetchone()[0]
            claimed = con.execute("SELECT 1 FROM vip_reward_claims WHERE user_id=? AND vip_level=?",
                                  (session["user_id"], level)).fetchone() is not None
            rows.append({"level": level, "required": required, "reward": reward, "progress": min(count, required), "completed": claimed})
    if credited:
        flash("VIP reward credited to your balance: " + ", ".join(f"VIP{x}" for x in credited), "success")
    return render_template("vip_task.html", active="my", tasks=rows)

@app.route("/i/<code>")
def invite_register(code):
    return redirect(url_for("auth", mode="signup", ref=code))

@app.route("/team")
def team():
    if not logged_in(): return redirect(url_for("auth"))
    with db() as con:
        user = con.execute("SELECT referral_code FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return render_template("team.html", active="team", referral=user["referral_code"] if user else "")



@app.route("/income")
def income():
    if not logged_in():
        return redirect(url_for("auth"))
    catalog = {m["code"]: m for m in MACHINE_CATALOG}
    with db() as con:
        purchased = con.execute("""
            SELECT machine_code, machine_name, price, purchased_at
            FROM purchases
            WHERE user_id=?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()
    machines = []
    for item in purchased:
        machine = catalog.get(item["machine_code"], {})
        machines.append({
            "code": item["machine_code"],
            "name": item["machine_name"] or item["machine_code"],
            "price": item["price"],
            "purchased_at": item["purchased_at"],
            "daily": machine.get("daily", 0),
            "days": machine.get("days", 0),
            "image": machine.get("image", ""),
        })
    return render_template("income.html", active="income", machines=machines)


ADMIN_PHONE = "0758878297"
DEPOSIT_PHONE = '0731199883'

def is_admin():
    uid = session.get("user_id")
    if not uid:
        return False
    try:
        with db() as con:
            row = con.execute("SELECT phone FROM users WHERE id=?", (uid,)).fetchone()
        digits = "".join(ch for ch in str(row["phone"] or "") if ch.isdigit()) if row else ""
        return digits.endswith("758878297")
    except Exception:
        return False

    if not uid:
        return False
    try:
        with db() as con:
            row = con.execute("SELECT phone FROM users WHERE id=?", (uid,)).fetchone()
        digits = "".join(ch for ch in str(row["phone"] or "") if ch.isdigit()) if row else ""
        return digits.endswith("758878297")
    except Exception:
        return False

    if not uid:
        return False
    try:
        with db() as con:
            row = con.execute("SELECT phone FROM users WHERE id=?", (uid,)).fetchone()
        digits = "".join(ch for ch in str(row["phone"] or "") if ch.isdigit()) if row else ""
        return digits.endswith("758878297")
    except Exception:
        return False


def record_tx(con, uid, kind, amount, status, reference=""):
    con.execute("INSERT INTO transactions(user_id,kind,amount,status,reference) VALUES(?,?,?,?,?)", (uid,kind,amount,status,reference))

def process_daily_earnings():
    # Idempotent: one credit per purchase per Uganda calendar day; call on each request.
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date().isoformat()
    with db() as con:
        rows = con.execute("SELECT p.*,u.id AS owner FROM purchases p JOIN users u ON u.id=p.user_id").fetchall()
        for r in rows:
            setting = con.execute("SELECT sold_out FROM machine_settings WHERE code=?", (r['machine_code'],)).fetchone()
            # duration starts on purchase date; daily earnings continue through duration_days.
            try: bought = datetime.datetime.fromisoformat(r['purchased_at']).date()
            except Exception: bought = datetime.date.today()
            elapsed = (datetime.date.fromisoformat(today)-bought).days
            duration = int(r['duration_days'] or 0)
            daily = float(r['daily_income'] or 0)
            if daily <= 0 or duration <= 0 or elapsed < 1 or elapsed > duration: continue
            lock_days = int(r['lock_days'] or 0)
            if lock_days:
                if elapsed != lock_days: continue
                credit = daily * min(lock_days, duration)
                earning_key = f"LOCKED-{today}"
                source = 'locked_machine_income'
            else:
                credit = daily
                earning_key = today
                source = 'daily_machine_income'
            cur = con.execute("INSERT OR IGNORE INTO daily_earnings(purchase_id,user_id,earning_date,amount) VALUES(?,?,?,?)", (r['id'],r['user_id'],earning_key,credit))
            if cur.rowcount:
                con.execute("UPDATE users SET balance=COALESCE(balance,0)+? WHERE id=?", (credit,r['user_id']))
                con.execute("INSERT INTO wallet_ledger(user_id,entry_type,amount,source,reference) VALUES(?,?,?,?,?)", (r['user_id'],'credit',credit,source,r['machine_code']))
                record_tx(con,r['user_id'],'Machine income',credit,'approved',r['machine_code'])

@app.before_request
def _earnings_tick():
    if request.endpoint not in ('static', 'auth', 'logout'):
        process_daily_earnings()

@app.route('/deposit', methods=['GET','POST'])
def deposit():
    if not logged_in(): return redirect(url_for('auth'))
    if request.method == 'POST':
        method=request.form.get('method','').lower()
        if method == 'usdt':
            flash('Not available for your account.','error'); return redirect(url_for('deposit'))
        try: amount=float(request.form.get('amount','0'))
        except ValueError: amount=0
        if amount <= 0: flash('Enter a valid deposit amount.','error'); return redirect(url_for('deposit'))
        with db() as con:
            cur=con.execute("INSERT INTO deposits(user_id,amount,status) VALUES(?,?,'pending')",(session['user_id'],amount))
            record_tx(con,session['user_id'],'Deposit',amount,'pending',f'DEP-{cur.lastrowid}')
        session['deposit_pending_id']=cur.lastrowid
        return redirect(url_for('deposit_instructions'))
    with db() as con:
        user=con.execute("SELECT COALESCE(wallet_balance,0) AS wallet_balance FROM users WHERE id=?",(session['user_id'],)).fetchone()
    return render_template('deposit.html',active='my',balance=float(user['wallet_balance'] or 0) if user else 0)

@app.route('/deposit/instructions')
def deposit_instructions():
    if not logged_in(): return redirect(url_for('auth'))
    return render_template('deposit_instructions.html', active='my', recipient=DEPOSIT_PHONE, recipient_name='Collins')

@app.route('/withdraw', methods=['GET','POST'])
def withdraw():
    if not logged_in(): return redirect(url_for('auth'))
    if request.method == 'POST':
        try: amount = float(request.form.get('amount', '0'))
        except (TypeError, ValueError): amount = 0
        phone = request.form.get('phone', '').strip()
        network = request.form.get('network', '').strip()
        if amount < 3000 or not phone or network not in ('MTN', 'Airtel'):
            flash('Enter a valid amount, mobile money number and network.', 'error')
            return redirect(url_for('withdraw'))
        fee = round(amount * 0.10, 2)
        payout_amount = round(amount - fee, 2)
        with db() as con:
            # Backward-compatible columns for existing databases.
            columns = {r['name'] for r in con.execute('PRAGMA table_info(withdrawals)').fetchall()}
            if 'network' not in columns: con.execute("ALTER TABLE withdrawals ADD COLUMN network TEXT NOT NULL DEFAULT ''")
            if 'fee' not in columns: con.execute("ALTER TABLE withdrawals ADD COLUMN fee REAL NOT NULL DEFAULT 0")
            if 'payout_amount' not in columns: con.execute("ALTER TABLE withdrawals ADD COLUMN payout_amount REAL NOT NULL DEFAULT 0")
            con.execute('BEGIN IMMEDIATE')
            user = con.execute('SELECT wallet_balance FROM users WHERE id=?', (session['user_id'],)).fetchone()
            available = float(user['wallet_balance'] or 0) if user else 0
            if available < amount:
                flash('Insufficient balance. Your available balance is UGX {:,.0f}.'.format(available), 'error')
                return redirect(url_for('withdraw'))
            debit = con.execute(
                'UPDATE users SET wallet_balance=COALESCE(wallet_balance,0)-? WHERE id=? AND COALESCE(wallet_balance,0)>=?',
                (amount, session['user_id'], amount))
            if debit.rowcount != 1:
                flash('Insufficient balance. Please try again.', 'error')
                return redirect(url_for('withdraw'))
            cur = con.execute(
                "INSERT INTO withdrawals(user_id,amount,phone,status,network,fee,payout_amount) VALUES(?,?,?,'pending',?,?,?)",
                (session['user_id'], amount, phone, network, fee, payout_amount))
            con.execute("INSERT INTO wallet_ledger(user_id,entry_type,amount,source,reference) VALUES(?,?,?,?,?)",
                (session['user_id'], 'debit', amount, 'withdrawal_pending', str(cur.lastrowid)))
            record_tx(con, session['user_id'], 'Withdrawal', amount, 'pending', f'WDR-{cur.lastrowid}')
            flash('Withdrawal pending. Net payout: UGX {:,.0f} after 10% fee.'.format(payout_amount), 'success')
            return redirect(url_for('bill'))
    with db() as con:
        user = con.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    return render_template('withdraw.html', active='my',
        balance=float(user['wallet_balance'] or 0) if user else 0,
        registered_phone=user['phone'] if user and 'phone' in user.keys() else '')

@app.route('/bill')
def bill():
    if not logged_in(): return redirect(url_for('auth'))
    with db() as con: rows=con.execute('SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC',(session['user_id'],)).fetchall()
    return render_template('bill.html',active='my',rows=rows)

@app.route('/manager', methods=['GET','POST'])
def manager():
    if not logged_in(): return redirect(url_for('auth'))
    if request.method=='POST':
        body=request.form.get('body','').strip()
        if body:
            with db() as con: con.execute('INSERT INTO chats(sender_id,recipient_id,is_admin,body) VALUES(?,?,0,?)',(session['user_id'],None,body))
        return redirect(url_for('manager'))
    with db() as con: messages=con.execute('SELECT * FROM chats WHERE sender_id=? OR recipient_id=? ORDER BY id',(session['user_id'],session['user_id'])).fetchall()
    return render_template('manager.html',active='my',messages=messages)


# Existing referral rates retained: 2% for each of the three levels.
REFERRAL_LEVEL_PERCENTAGES = {1: 2.0, 2: 2.0, 3: 2.0}
def credit_team_commissions(con, deposit_id, depositor_id, deposit_amount):
    con.execute("CREATE TABLE IF NOT EXISTS team_commissions (id INTEGER PRIMARY KEY AUTOINCREMENT, deposit_id INTEGER NOT NULL, depositor_id INTEGER NOT NULL, beneficiary_id INTEGER NOT NULL, level INTEGER NOT NULL, amount REAL NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(deposit_id,beneficiary_id,level))")
    row=con.execute("SELECT referred_by FROM users WHERE id=?",(depositor_id,)).fetchone()
    parent_id=row["referred_by"] if row else None
    for level in (1,2,3):
        if not parent_id: break
        pct=float(REFERRAL_LEVEL_PERCENTAGES.get(level,0))
        commission=round(float(deposit_amount)*pct/100.0,2)
        if commission>0:
            cur=con.execute("INSERT OR IGNORE INTO team_commissions(deposit_id,depositor_id,beneficiary_id,level,amount) VALUES(?,?,?,?,?)",(deposit_id,depositor_id,parent_id,level,commission))
            if cur.rowcount:
                con.execute("UPDATE users SET balance=COALESCE(balance,0)+? WHERE id=?",(commission,parent_id))
                con.execute("INSERT INTO wallet_ledger(user_id,entry_type,amount,source,reference) VALUES(?,?,?,?,?)",(parent_id,"credit",commission,"team_deposit_commission",f"DEP-{deposit_id}-LV{level}"))
        parent=con.execute("SELECT referred_by FROM users WHERE id=?",(parent_id,)).fetchone()
        parent_id=parent["referred_by"] if parent else None

@app.route('/admin', methods=['GET','POST'])
def admin():
    if not logged_in(): return redirect(url_for('auth'))
    if not is_admin(): return ('Forbidden',403)
    if request.method=='POST':
        action=request.form.get('action'); rid=request.form.get('id','')
        with db() as con:
            if action in ('approve_deposit','reject_deposit'):
                row=con.execute('SELECT * FROM deposits WHERE id=? AND status="pending"',(rid,)).fetchone()
                if row:
                    status='approved' if action=='approve_deposit' else 'rejected'
                    con.execute('UPDATE deposits SET status=?,approved_at=CURRENT_TIMESTAMP WHERE id=?',(status,rid))
                    if status=='approved':
                        con.execute('UPDATE users SET wallet_balance=COALESCE(wallet_balance,0)+? WHERE id=?',(row['amount'],row['user_id']))
                        con.execute('INSERT INTO wallet_ledger(user_id,entry_type,amount,source,reference) VALUES(?,?,?,?,?)',(row['user_id'],'credit',row['amount'],'deposit_approved',str(rid)))
                        credit_team_commissions(con,int(rid),row['user_id'],row['amount'])
                    con.execute('UPDATE transactions SET status=? WHERE user_id=? AND kind="Deposit" AND reference=?',(status,row['user_id'],f'DEP-{rid}'))
                    process_vip_rewards(con,row['user_id'])
            elif action in ('approve_withdrawal','reject_withdrawal'):
                row=con.execute('SELECT * FROM withdrawals WHERE id=? AND status="pending"',(rid,)).fetchone()
                if row:
                    status='approved' if action=='approve_withdrawal' else 'rejected'
                    con.execute('UPDATE withdrawals SET status=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?',(status,rid))
                    if status=='rejected': con.execute('UPDATE users SET wallet_balance=COALESCE(wallet_balance,0)+? WHERE id=?',(row['amount'],row['user_id']))
                    con.execute('UPDATE transactions SET status=? WHERE user_id=? AND kind="Withdrawal" AND reference=?',(status,row['user_id'],f'WDR-{rid}'))
            elif action=='block_user':
                con.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(secrets.token_urlsafe(32)),rid))
            elif action=='reset_password':
                newpass=request.form.get('new_password','')
                if len(newpass)>=8: con.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(newpass),rid))
            elif action=='machine_save':
                code=request.form.get('code','').strip(); sold=1 if request.form.get('sold_out') else 0
                con.execute('INSERT INTO machine_settings(code,sold_out,image,price,daily,days,lock_days) VALUES(?,?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET sold_out=excluded.sold_out,image=excluded.image,price=excluded.price,daily=excluded.daily,days=excluded.days,lock_days=excluded.lock_days',(code,sold,request.form.get('image',''),float(request.form.get('price') or 0),float(request.form.get('daily') or 0),int(request.form.get('days') or 0),int(request.form.get('lock_days') or 0)))
        return redirect(url_for('admin'))
    with db() as con:
        deposits=con.execute('SELECT d.*,u.phone FROM deposits d JOIN users u ON u.id=d.user_id ORDER BY d.id DESC').fetchall()
        withdrawals=con.execute('SELECT w.*,u.phone AS user_phone FROM withdrawals w JOIN users u ON u.id=w.user_id ORDER BY w.id DESC').fetchall()
        users=con.execute('SELECT id,phone,username,balance FROM users ORDER BY id DESC').fetchall()
    return render_template('admin.html',active='my',deposits=deposits,withdrawals=withdrawals,users=users,machines=MACHINE_CATALOG)


@app.route("/pages/login/index")
def pimco_legacy_invite():
    code = request.args.get("code", "").strip()
    return redirect(url_for("auth", mode="signup", ref=code))



@app.route("/settings", methods=["GET", "POST"])
def settings():
    if not logged_in():
        return redirect(url_for("auth"))
    message = None
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        with db() as con:
            user = con.execute(
                "SELECT password_hash FROM users WHERE id=?",
                (session["user_id"],)
            ).fetchone()
            if not user or not check_password_hash(user["password_hash"], current_password):
                message = ("error", "Your current password is incorrect.")
            elif len(new_password) < 8:
                message = ("error", "New password must contain at least 8 characters.")
            elif new_password != confirm_password:
                message = ("error", "The new passwords do not match.")
            elif check_password_hash(user["password_hash"], new_password):
                message = ("error", "Choose a password different from your current password.")
            else:
                con.execute(
                    "UPDATE users SET password_hash=? WHERE id=?",
                    (generate_password_hash(new_password), session["user_id"])
                )
                message = ("success", "Password changed successfully.")
    return render_template("settings.html", active="my", message=message)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)


@app.route("/admin/members/<int:member_id>", methods=["GET", "POST"])
def admin_member(member_id):
    if not logged_in() or not is_admin():
        return redirect(url_for("auth"))
    with db() as con:
        if request.method == "POST":
            action=request.form.get("action","")
            if action in ("block","unblock"):
                if action=="unblock" or member_id != session.get("user_id"):
                    con.execute("UPDATE users SET is_blocked=? WHERE id=?", (1 if action=="block" else 0,member_id))
            elif action in ("add_balance","subtract_balance","set_balance"):
                try:
                    amount=float(request.form.get("amount",""))
                    if amount < 0: raise ValueError()
                    row=con.execute("SELECT balance FROM users WHERE id=?",(member_id,)).fetchone()
                    if row:
                        old=float(row["balance"] or 0)
                        new=amount if action=="set_balance" else old+amount if action=="add_balance" else old-amount
                        if new < 0: raise ValueError()
                        delta=new-old
                        con.execute("UPDATE users SET balance=? WHERE id=?",(new,member_id))
                        if delta:
                            con.execute("INSERT INTO wallet_ledger(user_id,entry_type,amount,source,reference) VALUES(?,?,?,?,?)",
                                (member_id,"admin_adjustment",delta,"admin_panel","Admin balance adjustment"))
                            con.execute("INSERT INTO transactions(user_id,kind,amount,status,reference) VALUES(?,?,?,?,?)",
                                (member_id,"admin_adjustment",delta,"approved","Admin balance adjustment"))
                except (ValueError,TypeError):
                    flash("Invalid amount or insufficient balance.", "error")
            elif action=="reset_password":
                password=request.form.get("new_password","")
                if len(password)>=8:
                    con.execute("UPDATE users SET password_hash=? WHERE id=?",
                        (generate_password_hash(password),member_id))
                else:
                    flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("admin_member",member_id=member_id))
        member=con.execute("SELECT id,phone,username,email,balance,wallet_balance,referral_code,referred_by,is_blocked FROM users WHERE id=?",(member_id,)).fetchone()
        if not member: return "Member not found",404
        team1=con.execute("SELECT id,phone,username,balance FROM users WHERE referred_by=? ORDER BY id DESC",(member_id,)).fetchall()
        team2=[]
        for p in team1:
            team2.extend(con.execute("SELECT id,phone,username,balance FROM users WHERE referred_by=? ORDER BY id DESC",(p["id"],)).fetchall())
        team3=[]
        for p in team2:
            team3.extend(con.execute("SELECT id,phone,username,balance FROM users WHERE referred_by=? ORDER BY id DESC",(p["id"],)).fetchall())
    return render_template("admin_member.html",member=member,team1=team1,team2=team2,team3=team3)
