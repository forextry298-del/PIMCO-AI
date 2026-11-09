#!/usr/bin/env python3
import os, re, shutil, sys, secrets, datetime, py_compile
ROOT=os.path.abspath(os.getcwd())
APP=os.path.join(ROOT,"app.py")
TPL=os.path.join(ROOT,"templates")
ADMIN=os.path.join(TPL,"admin.html")
if not os.path.isfile(APP) or not os.path.isdir(TPL):
    sys.exit("Run this installer from the PIMCO_AI folder containing app.py and templates/.")
src=open(APP,encoding="utf-8").read()
admin=open(ADMIN,encoding="utf-8").read() if os.path.isfile(ADMIN) else ""
old_src,old_admin=src,admin

# Add the blocked flag within init_db(), not at module level.
anchor='''        if "country" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN country TEXT DEFAULT 'Uganda (UGX)'")'''
if "if \"is_blocked\" not in columns:" not in src:
    if anchor not in src:
        sys.exit("Could not find init_db users migration anchor. No files changed.")
    src=src.replace(anchor,anchor+'''
        if "is_blocked" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER NOT NULL DEFAULT 0")''',1)

# Add unique five-character invite-code helper and repair existing codes after init_db().
helper = '''

def make_invite_code(con):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(100):
        code = "".join(secrets.choice(alphabet) for _ in range(5))
        if not con.execute("SELECT 1 FROM users WHERE referral_code=?", (code,)).fetchone():
            return code
    raise RuntimeError("Unable to generate a unique invitation code")
'''
if "def make_invite_code(con):" not in src:
    marker="\ninit_db()\n"
    if marker not in src:
        sys.exit("Could not find init_db() call. No files changed.")
    src=src.replace(marker,helper+'''
init_db()
with db() as con:
    seen=set()
    for row in con.execute("SELECT id, referral_code FROM users ORDER BY id").fetchall():
        code=(row["referral_code"] or "").strip().upper()
        if len(code)!=5 or code in seen:
            code=make_invite_code(con)
            con.execute("UPDATE users SET referral_code=? WHERE id=?", (code,row["id"]))
        seen.add(code)
''',1)
src=src.replace("secrets.token_hex(4).upper()", "make_invite_code(con)")
src=src.replace("secrets.token_hex(4)", "make_invite_code(con)")

# DB-backed admin phone check; supports 075... and +256... formats.
pat=r"def is_admin\(\):\n(?:[ \t]+.*\n)+?"
m=re.search(pat,src)
if not m:
    sys.exit("Could not safely locate is_admin(). No files changed.")
replacement='''def is_admin():
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

'''
src=src[:m.start()]+replacement+src[m.end():]

route = r'''

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
'''
if "def admin_member(member_id):" not in src:
    src += route

member_html = '''{% extends "base.html" %}
{% block content %}
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
.member-admin{max-width:720px;margin:12px auto;padding:10px;color:#eee}
.member-admin .panel{background:#191b25;border:1px solid #383b49;border-radius:11px;padding:12px;margin:10px 0}
.member-admin h2,.member-admin h3{color:#e8bd62;margin:3px 0 10px}
.member-admin p{margin:5px 0;overflow-wrap:anywhere}
.member-admin input,.member-admin button{box-sizing:border-box;width:100%;padding:10px;margin:4px 0;border-radius:8px;border:1px solid #444;background:#292c38;color:#fff;font-size:14px}
.member-admin button{background:#c99b42;color:#171717;border:0;font-weight:bold}
.member-admin .danger{background:#8e3030;color:white}
.member-admin .grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.member-admin .person{padding:7px 0;border-bottom:1px solid #333}
@media(max-width:430px){.member-admin{padding:7px}.member-admin .grid{grid-template-columns:1fr}}
</style>
<div class="member-admin">
<p><a href="{{ url_for('admin') }}">← Back to Admin</a></p>
<div class="panel"><h2>Member #{{ member.id }}</h2>
<p><b>Username:</b> {{ member.username or '—' }}</p><p><b>Phone:</b> {{ member.phone or '—' }}</p>
<p><b>Email:</b> {{ member.email or '—' }}</p><p><b>Invitation code:</b> {{ member.referral_code }}</p>
<p><b>Available balance:</b> UGX {{ '%.2f'|format(member.balance or 0) }}</p>
<p><b>Wallet balance:</b> UGX {{ '%.2f'|format(member.wallet_balance or 0) }}</p>
<p><b>Status:</b> {{ 'BLOCKED' if member.is_blocked else 'ACTIVE' }}</p></div>
<div class="panel"><h3>Edit available balance</h3>
<form method="post" class="grid"><input type="hidden" name="action" value="add_balance"><input name="amount" type="number" min="0" step="0.01" placeholder="Amount" required><button>Add</button></form>
<form method="post" class="grid"><input type="hidden" name="action" value="subtract_balance"><input name="amount" type="number" min="0" step="0.01" placeholder="Amount" required><button>Subtract</button></form>
<form method="post" class="grid"><input type="hidden" name="action" value="set_balance"><input name="amount" type="number" min="0" step="0.01" placeholder="New balance" required><button>Set balance</button></form></div>
<div class="panel"><h3>Account controls</h3>
{% if member.is_blocked %}<form method="post"><input type="hidden" name="action" value="unblock"><button>Unblock user</button></form>
{% else %}<form method="post"><input type="hidden" name="action" value="block"><button class="danger">Block user</button></form>{% endif %}
<form method="post"><input type="hidden" name="action" value="reset_password"><input type="password" name="new_password" minlength="8" placeholder="New password (8+ characters)" required><button>Reset password</button></form></div>
{% for title, people in [('Level 1',team1),('Level 2',team2),('Level 3',team3)] %}
<div class="panel"><h3>{{ title }} — {{ people|length }} users</h3>
{% for p in people %}<div class="person">#{{ p.id }} · {{ p.username or p.phone or 'Member' }} · UGX {{ '%.2f'|format(p.balance or 0) }}</div>
{% else %}<p>No members</p>{% endfor %}</div>{% endfor %}
</div>
{% endblock %}
'''
# Add Manage links if we can identify the current admin user loop; route remains accessible by URL otherwise.
if admin and "admin_member" not in admin and "u.balance" in admin:
    admin=admin.replace("{{ u.balance }}","{{ u.balance }} <a href=\"{{ url_for('admin_member', member_id=u.id) }}\">Manage</a>",1)

stamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
for path in (APP,ADMIN):
    if os.path.isfile(path): shutil.copy2(path,path+".backup_"+stamp)
with open(APP,"w",encoding="utf-8") as f: f.write(src)
if admin:
    with open(ADMIN,"w",encoding="utf-8") as f: f.write(admin)
with open(os.path.join(TPL,"admin_member.html"),"w",encoding="utf-8") as f: f.write(member_html)
try:
    py_compile.compile(APP,doraise=True)
except Exception as e:
    with open(APP,"w",encoding="utf-8") as f: f.write(old_src)
    if old_admin:
        with open(ADMIN,"w",encoding="utf-8") as f: f.write(old_admin)
    os.remove(os.path.join(TPL,"admin_member.html"))
    sys.exit("Compile failed; app.py and admin.html restored. Details: "+str(e))
print("SUCCESS: admin member tools installed; backups created.")
print("Existing deposit/withdrawal review route was left in place.")
print("Open /admin and use Manage beside a user (if link was detected), or visit /admin/members/USER_ID.")
