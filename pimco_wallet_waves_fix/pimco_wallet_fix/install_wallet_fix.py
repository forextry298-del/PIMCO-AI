
from pathlib import Path
from datetime import datetime
import re, shutil

root = Path.cwd()
bundle = Path(__file__).resolve().parent / "templates"
app = root / "app.py"
td = root / "templates"
if not app.exists() or not td.exists():
    raise SystemExit("Run this from the PIMCO_AI project root containing app.py and templates/.")

src = app.read_text(encoding="utf-8")
backup = root / "PIMCO_WALLET_WAVES_BACKUP" / datetime.now().strftime("%Y%m%d-%H%M%S")
backup.mkdir(parents=True, exist_ok=True)
shutil.copy2(app, backup / "app.py")
for name in ("deposit.html", "withdraw.html"):
    if (td / name).exists():
        shutil.copy2(td / name, backup / name)

route = '''
@app.route('/deposit', methods=['GET','POST'])
def deposit():
    if not logged_in():
        return redirect(url_for('auth'))
    if request.method == 'POST':
        method = request.form.get('method', 'mobile_money').strip().lower()
        if method == 'usdt':
            flash('USDT deposits are not available for this account.', 'error')
            return redirect(url_for('deposit'))
        try:
            amount = float(request.form.get('amount', '0'))
        except (TypeError, ValueError):
            amount = 0
        phone = request.form.get('phone', '').strip()
        network = request.form.get('network', '').strip()
        if amount < 30000:
            flash('Minimum deposit is UGX 30,000.', 'error')
            return redirect(url_for('deposit'))
        if not phone or network not in ('MTN', 'Airtel'):
            flash('Enter your Mobile Money number and select MTN or Airtel.', 'error')
            return redirect(url_for('deposit'))
        with db() as con:
            cols = {r['name'] for r in con.execute('PRAGMA table_info(deposits)').fetchall()}
            if 'phone' not in cols:
                con.execute("ALTER TABLE deposits ADD COLUMN phone TEXT NOT NULL DEFAULT ''")
            if 'network' not in cols:
                con.execute("ALTER TABLE deposits ADD COLUMN network TEXT NOT NULL DEFAULT ''")
            cur = con.execute(
                "INSERT INTO deposits(user_id,amount,status,phone,network) VALUES(?,?,'pending',?,?)",
                (session['user_id'], amount, phone, network))
            record_tx(con, session['user_id'], 'Deposit', amount, 'pending', f'DEP-{cur.lastrowid}')
        session['deposit_pending_id'] = cur.lastrowid
        flash('Deposit request recorded. Wallet credit follows admin confirmation of payment.', 'success')
        return redirect(url_for('deposit_instructions'))
    with db() as con:
        user = con.execute('SELECT balance FROM users WHERE id=?', (session['user_id'],)).fetchone()
    return render_template('deposit.html', active='my',
        balance=float(user['balance'] or 0) if user else 0)
'''
pattern = re.compile(r"@app\.route\('/deposit',\s*methods=\['GET','POST'\]\)\s*\ndef deposit\(\):.*?(?=\n@app\.route|\n\n@app\.route|\Z)", re.S)
match = pattern.search(src)
if not match:
    raise SystemExit("Could not safely locate /deposit route. No project files were changed.")
src = src[:match.start()] + route.strip() + src[match.end():]

app.write_text(src, encoding="utf-8")
for name in ("deposit.html", "withdraw.html"):
    shutil.copy2(bundle / name, td / name)
print("Wallet pages installed. Backup:", backup)
