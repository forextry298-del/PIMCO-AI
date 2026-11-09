#!/usr/bin/env python3
from pathlib import Path
import re, shutil, sys

ap=Path.cwd()/"app.py"
hp=Path.cwd()/"templates"/"home.html"
if not ap.is_file() or not hp.is_file():
    print("Run from PIMCO_AI folder."); sys.exit(1)
app=ap.read_text()
home=hp.read_text()
if "def dashboard_metrics(" in app or "team_commissions" in app:
    print("Dashboard patch already appears installed; stopping."); sys.exit(2)

route = """
@app.route("/")
def home():
    if not logged_in():
        return redirect(url_for("auth"))
    show_login_notice = bool(session.pop("show_login_notice", False))
    uid = session["user_id"]
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
    return render_template("home.html",active="home",show_login_notice=show_login_notice,metrics=metrics)
"""
rx=re.compile(r'@app\.route\(["\']/["\']\)\s*\ndef home\(\):[\s\S]*?(?=\n@app\.route\()',re.M)
m=rx.search(app)
if not m:
    print("Home route not found; no changes."); sys.exit(3)
app=app[:m.start()]+route.strip()+app[m.end():]

helper = """
def credit_team_commissions(con, deposit_id, depositor_id, deposit_amount):
    con.execute("CREATE TABLE IF NOT EXISTS team_commissions (id INTEGER PRIMARY KEY AUTOINCREMENT, deposit_id INTEGER NOT NULL, depositor_id INTEGER NOT NULL, beneficiary_id INTEGER NOT NULL, level INTEGER NOT NULL, amount REAL NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(deposit_id,beneficiary_id,level))")
    row=con.execute("SELECT referred_by FROM users WHERE id=?",(depositor_id,)).fetchone()
    parent_id=row["referred_by"] if row else None
    for level in (1,2,3):
        if not parent_id: break
        commission=round(float(deposit_amount)*0.02,2)
        cur=con.execute("INSERT OR IGNORE INTO team_commissions(deposit_id,depositor_id,beneficiary_id,level,amount) VALUES(?,?,?,?,?)",(deposit_id,depositor_id,parent_id,level,commission))
        if cur.rowcount:
            con.execute("UPDATE users SET balance=COALESCE(balance,0)+? WHERE id=?",(commission,parent_id))
            con.execute("INSERT INTO wallet_ledger(user_id,entry_type,amount,source,reference) VALUES(?,?,?,?,?)",(parent_id,"credit",commission,"team_deposit_commission",f"DEP-{deposit_id}-LV{level}"))
        parent=con.execute("SELECT referred_by FROM users WHERE id=?",(parent_id,)).fetchone()
        parent_id=parent["referred_by"] if parent else None

"""
marker="@app.route('/admin', methods=['GET','POST'])"
if marker not in app:
    print("Admin route not found; no changes."); sys.exit(4)
app=app.replace(marker,helper+marker,1)
old="                        con.execute('INSERT INTO wallet_ledger(user_id,entry_type,amount,source,reference) VALUES(?,?,?,?,?)',(row['user_id'],'credit',row['amount'],'deposit_approved',str(rid)))"
if old not in app:
    print("Deposit approval statement not found; no changes."); sys.exit(5)
app=app.replace(old,old+"\n                        credit_team_commissions(con,int(rid),row['user_id'],row['amount'])",1)

for label,value in [
("Deposit details","{{ '%.2f'|format(metrics.deposit_total) }}"),
("Withdraw details","{{ '%.2f'|format(metrics.withdrawal_total) }}"),
("AI Income","{{ '%.2f'|format(metrics.ai_income) }}"),
("Today's earnings","{{ '%.2f'|format(metrics.today_income) }}"),
("Invite Count","{{ metrics.invite_count }}"),
("Team Count","{{ metrics.team_count }}"),
("Team income","{{ '%.2f'|format(metrics.team_income) }}")]:
    pat=re.compile(r'(<b>)[\s\S]*?(</b>\s*<small>\s*'+re.escape(label)+r'\s*</small>)',re.I)
    home,n=pat.subn(lambda x:x.group(1)+value+x.group(2),home,count=1)
    if n!=1:
        print("Dashboard card not found:",label,"No changes made."); sys.exit(6)

for p in (ap,hp):
    backup=p.with_name(p.name+".before_dashboard_metrics_backup")
    if not backup.exists(): shutil.copy2(p,backup)
ap.write_text(app)
hp.write_text(home)
print("Dashboard metrics installed. Backups created.")
print("AI Income = recorded machine earnings; Today's = machine credits today.")
print("Invite Count = direct referrals; Team Count = LV1+LV2+LV3.")
print("Team Income = 2% of each approved deposit at each of up to 3 upline levels.")
print("Deposits = approved only; Withdrawals = approved + pending.")
print("Historical deposits are not retroactively commissioned.")
print("Run python -m py_compile app.py, then restart Flask.")
