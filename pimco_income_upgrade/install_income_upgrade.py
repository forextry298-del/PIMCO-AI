#!/usr/bin/env python3
import os, shutil, sys, datetime, py_compile
ROOT=os.path.abspath(os.getcwd())
APP=os.path.join(ROOT,"app.py")
INCOME=os.path.join(ROOT,"templates","income.html")
WITHDRAW=os.path.join(ROOT,"templates","withdraw.html")
for p in (APP,INCOME,WITHDRAW):
    if not os.path.isfile(p): sys.exit("Missing "+os.path.relpath(p,ROOT)+"; run from PIMCO_AI.")
src=open(APP,encoding="utf-8").read()
income=open(INCOME,encoding="utf-8").read()
withdraw=open(WITHDRAW,encoding="utf-8").read()
old=(src,income,withdraw)

a=src.find('@app.route("/income")')
if a<0: a=src.find("@app.route('/income')")
b=src.find("\\n\\nADMIN_PHONE",a)
if a<0 or b<0: sys.exit("Cannot locate /income route; no files changed.")
route='''@app.route("/income")
def income():
    if not logged_in(): return redirect(url_for("auth"))
    now=datetime.datetime.now(datetime.timezone.utc)
    with db() as con:
        rows=con.execute("SELECT id,machine_code,machine_name,price,purchased_at,daily_income,duration_days,lock_days FROM purchases WHERE user_id=? ORDER BY id DESC",(session["user_id"],)).fetchall()
        machines=[]
        for p in rows:
            try:
                bought=datetime.datetime.fromisoformat(str(p["purchased_at"]).replace("Z","+00:00"))
                if bought.tzinfo is None: bought=bought.replace(tzinfo=datetime.timezone.utc)
                else: bought=bought.astimezone(datetime.timezone.utc)
            except Exception: bought=now
            daily=float(p["daily_income"] or 0); duration=max(0,int(p["duration_days"] or 0)); lock=max(0,int(p["lock_days"] or 0))
            paid=con.execute("SELECT amount FROM daily_earnings WHERE purchase_id=?",(p["id"],)).fetchall()
            earned=sum(float(x["amount"] or 0) for x in paid); paid_days=int(round(earned/daily)) if daily>0 else 0
            elapsed=max(0,int((now-bought).total_seconds()//86400))
            if lock and elapsed<lock: next_at=bought+datetime.timedelta(days=lock); status="Locked"
            elif elapsed<duration: next_at=bought+datetime.timedelta(days=elapsed+1); status="Active"
            else: next_at=None; status="Completed"
            item=next((m for m in MACHINE_CATALOG if m["code"].lower()==str(p["machine_code"]).lower()),{})
            machines.append({"id":p["id"],"code":p["machine_code"],"name":p["machine_name"] or p["machine_code"],"price":float(p["price"] or 0),"purchased_at":p["purchased_at"],"daily":daily,"days":duration,"lock_days":lock,"cycle_total":daily*duration,"earned":earned,"paid_days":paid_days,"image":item.get("image",""),"status":status,"next_payout":next_at.isoformat() if next_at else "","remaining_days":max(0,duration-elapsed)})
    return render_template("income.html",active="income",machines=machines)
'''
src=src[:a]+route+src[b:]

a=src.find("def process_daily_earnings():")
b=src.find("\\n@app.before_request",a)
if a<0 or b<0: sys.exit("Cannot locate process_daily_earnings(); no files changed.")
processor='''def process_daily_earnings():
    # Purchase-anchored, idempotent 24-hour machine payouts.
    now=datetime.datetime.now(datetime.timezone.utc)
    with db() as con:
        rows=con.execute("SELECT * FROM purchases ORDER BY id").fetchall()
        for r in rows:
            daily=float(r["daily_income"] or 0); duration=max(0,int(r["duration_days"] or 0)); lock=max(0,int(r["lock_days"] or 0))
            if daily<=0 or duration<=0: continue
            try:
                bought=datetime.datetime.fromisoformat(str(r["purchased_at"]).replace("Z","+00:00"))
                if bought.tzinfo is None: bought=bought.replace(tzinfo=datetime.timezone.utc)
                else: bought=bought.astimezone(datetime.timezone.utc)
            except Exception: continue
            elapsed=max(0,int((now-bought).total_seconds()//86400)); due=[]
            if lock>0:
                if elapsed>=lock:
                    due.append(("lock-release",daily*min(lock,duration),"locked_machine_income"))
                    for n in range(lock+1,min(elapsed,duration)+1): due.append((f"slot-{n:06d}",daily,"daily_machine_income"))
            else:
                for n in range(1,min(elapsed,duration)+1): due.append((f"slot-{n:06d}",daily,"daily_machine_income"))
            existing=con.execute("SELECT earning_date FROM daily_earnings WHERE purchase_id=?",(r["id"],)).fetchall()
            keys={str(x["earning_date"]) for x in existing}
            legacy_daily=sum(1 for k in keys if not k.startswith("LOCKED-") and not k.startswith("slot-") and k!="lock-release")
            legacy_lock=any(k.startswith("LOCKED-") or k=="lock-release" for k in keys)
            for key,amount,source in due:
                if key=="lock-release":
                    if legacy_lock or key in keys: continue
                else:
                    n=int(key.split("-")[1])
                    if key in keys or (not lock and n<=legacy_daily): continue
                cur=con.execute("INSERT OR IGNORE INTO daily_earnings(purchase_id,user_id,earning_date,amount) VALUES(?,?,?,?)",(r["id"],r["user_id"],key,amount))
                if cur.rowcount:
                    con.execute("UPDATE users SET balance=COALESCE(balance,0)+? WHERE id=?",(amount,r["user_id"]))
                    con.execute("INSERT INTO wallet_ledger(user_id,entry_type,amount,source,reference) VALUES(?,?,?,?,?)",(r["user_id"],"credit",amount,source,str(r["machine_code"])))
                    record_tx(con,r["user_id"],"Machine income",amount,"approved",str(r["machine_code"]))
'''
src=src[:a]+processor+src[b:]

if "phone = request.form.get('phone', '').strip()" not in src: sys.exit("Cannot locate withdrawal phone field; no files changed.")
check="if amount < 3000 or not phone or network not in ('MTN', 'Airtel'):"
if check not in src: sys.exit("Cannot locate withdrawal validation; no files changed.")
src=src.replace(check,"phone_digits=''.join(ch for ch in phone if ch.isdigit())\n        if amount < 3000 or len(phone_digits) not in (9,10,12) or network not in ('MTN', 'Airtel'):",1)

withdraw=withdraw.replace("Registered Mobile Money Number","Number to Receive Withdrawal")
withdraw=withdraw.replace('value="{{ registered_phone|default(\'\') }}" readonly required','value="{{ registered_phone|default(\'\') }}" placeholder="Enter recipient number" required')
withdraw=withdraw.replace("ⓘ Your withdrawal will be sent to this registered Mobile Money number.","ⓘ Enter the MTN or Airtel number that should receive your withdrawal. It may differ from your registered number.")
withdraw=withdraw.replace(" readonly required"," required")

income_html=r'''{% extends "base.html" %}
{% block content %}
<style>
.income-screen{max-width:760px;margin:0 auto;padding:14px 12px 90px;color:#f4f5fa;font-family:Arial,sans-serif}
.income-head{margin:8px 0 16px}.income-brand{font-size:12px;color:#9da9b8;letter-spacing:.8px}
.income-head h1{font-family:Georgia,serif;font-size:29px;margin:8px 0 16px;color:#fff}
.income-currency{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:13px 14px;border:1px solid #164b61;border-radius:15px;background:#03070b;margin-bottom:14px;font-size:13px}
.income-toggle{display:flex;padding:3px;border:1px solid #21495a;border-radius:30px}.income-toggle span{padding:9px 13px;border-radius:24px;color:#c8d0dc;font-weight:bold}.income-toggle .selected{background:#08b9e8;color:white}
.income-machine{display:grid;grid-template-columns:118px minmax(0,1fr);gap:12px;padding:13px;margin:13px 0;border:1px solid #12607a;border-radius:20px;background:rgba(0,0,0,.93);box-shadow:0 0 9px rgba(0,175,220,.12)}
.income-machine>img,.income-image-placeholder{width:118px;height:118px;object-fit:cover;border-radius:9px;background:#111827}
.income-machine-main{min-width:0}.income-machine-top{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.income-machine-name{font:bold 19px Georgia,serif;color:#18c4ed;overflow-wrap:anywhere}.income-status{font-size:10px;border:1px solid #14627a;border-radius:18px;padding:5px 9px;color:#69d8f4;white-space:nowrap}
.income-date{font-size:11px;color:#b7bec8;margin:5px 0}.income-earned{font-size:12px;color:#d5d9e1}.income-earned b{color:#17c7f0}
.income-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:13px}.income-metric{background:#050a10;border-radius:9px;padding:9px 5px;text-align:center;min-width:0}
.income-metric small{display:block;color:#aeb9c6;font-size:9px;text-transform:uppercase;letter-spacing:.4px}.income-metric b{display:block;margin-top:6px;font-size:13px;color:#f3f5f8;overflow-wrap:anywhere}
.income-metric:first-child b{color:#19c5ef}.income-progress{height:5px;border-radius:10px;background:#1c2934;margin:13px 0 7px;overflow:hidden}.income-progress span{display:block;height:100%;background:#09b9e8}
.income-note{font-size:11px;line-height:1.5;color:#b8c0ca}.income-countdown{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-top:12px;padding:10px;border:1px solid #183c4c;border-radius:13px;background:#061019;font-size:11px;color:#b7c6d2}
.income-countdown strong{color:#23c9f1;font-size:13px}.income-empty{padding:25px;text-align:center;background:#050a10;border:1px solid #164b61;border-radius:15px;color:#aeb8c5}
@media(max-width:420px){.income-screen{padding-left:9px;padding-right:9px}.income-machine{grid-template-columns:88px minmax(0,1fr);gap:9px;padding:10px}.income-machine>img,.income-image-placeholder{width:88px;height:96px}.income-machine-name{font-size:16px}.income-metric b{font-size:11px}.income-countdown{font-size:10px}}
</style>
<section class="income-screen">
<header class="income-head"><div class="income-brand">PIMCO AI</div><h1>Income history</h1></header>
<div class="income-currency"><span>Show amounts in UGX</span><div class="income-toggle"><span class="selected">UGX</span><span>USDT</span></div></div>
{% if machines %}{% for machine in machines %}
<article class="income-machine" data-next-payout="{{ machine.next_payout }}">
{% if machine.image %}<img src="{{ url_for('static',filename='images/' ~ machine.image) }}" alt="{{ machine.name }}">{% else %}<div class="income-image-placeholder"></div>{% endif %}
<div class="income-machine-main">
<div class="income-machine-top"><strong class="income-machine-name">{{ machine.name }}</strong><span class="income-status">{{ machine.status }}</span></div>
<div class="income-date">{{ machine.purchased_at }}</div><div class="income-earned">EARNED <b>{{ "{:,.2f}".format(machine.earned) }}</b></div>
<div class="income-metrics"><div class="income-metric"><small>Daily</small><b>{{ "{:,.2f}".format(machine.daily) }}</b></div><div class="income-metric"><small>Paid days</small><b>{{ machine.paid_days }}</b></div><div class="income-metric"><small>Cycle total</small><b>{{ "{:,.2f}".format(machine.cycle_total) }}</b></div></div>
<div class="income-progress"><span style="width:{{ [100, (machine.paid_days*100/machine.days)|int if machine.days else 0]|min }}%"></span></div>
<div class="income-note">Daily payouts — {{ "{:,.2f}".format(machine.earned) }} earned; paid every 24 hours{% if machine.lock_days %}. Lock period: {{ machine.lock_days }} days{% endif %}</div>
{% if machine.next_payout %}<div class="income-countdown"><span>◷ Next payout in</span><strong class="income-timer">Calculating…</strong><span>Ends {{ machine.remaining_days }}d</span></div>{% else %}<div class="income-countdown"><span>Cycle status</span><strong>Completed</strong></div>{% endif %}
</div></article>
{% endfor %}{% else %}<div class="income-empty">No purchased machines yet</div>{% endif %}
</section>
<script>
(function(){function update(){document.querySelectorAll('.income-machine[data-next-payout]').forEach(function(card){var raw=card.getAttribute('data-next-payout'),out=card.querySelector('.income-timer');if(!raw||!out)return;var left=Math.max(0,Math.floor((new Date(raw).getTime()-Date.now())/1000));var h=String(Math.floor(left/3600)).padStart(2,'0'),m=String(Math.floor(left%3600/60)).padStart(2,'0'),s=String(left%60).padStart(2,'0');out.textContent=h+':'+m+':'+s;});}update();setInterval(update,1000);})();
</script>
{% endblock %}
'''
stamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
for p in (APP,INCOME,WITHDRAW): shutil.copy2(p,p+".backup_income_"+stamp)
with open(APP,"w",encoding="utf-8") as f:f.write(src)
with open(INCOME,"w",encoding="utf-8") as f:f.write(income_html)
with open(WITHDRAW,"w",encoding="utf-8") as f:f.write(withdraw)
try: py_compile.compile(APP,doraise=True)
except Exception as e:
    for p,data in zip((APP,INCOME,WITHDRAW),old):
        with open(p,"w",encoding="utf-8") as f:f.write(data)
    sys.exit("Compile failed; originals restored: "+str(e))
print("SUCCESS: Income history, 24-hour payouts and editable withdrawal recipient installed.")
print("Backups created. Run: python -m py_compile app.py && python app.py")
