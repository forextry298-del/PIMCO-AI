from pathlib import Path
import shutil
from datetime import datetime

root = Path.cwd()
home = root / "templates" / "home.html"
my = root / "templates" / "my.html"
if not home.exists() or not my.exists():
    raise SystemExit("Run this installer from the PIMCO_AI project root containing templates/home.html and templates/my.html.")

h = home.read_text(encoding="utf-8")
m = my.read_text(encoding="utf-8")

old_home_deposit = '<a href="{{ url_for(\'my\') }}"><span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/></svg></span>Deposit</a>'
old_home_withdraw = '<a href="{{ url_for(\'my\') }}"><span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21V9m-5 5 5-5 5 5M4 7V3h16v4"/></svg></span>Withdraw</a>'

new_home_deposit = old_home_deposit.replace("url_for('my')", "url_for('deposit')")
new_home_withdraw = old_home_withdraw.replace("url_for('my')", "url_for('withdraw')")

if old_home_deposit not in h or old_home_withdraw not in h:
    raise SystemExit("Could not find the exact Deposit and Withdraw shortcuts in home.html. No files changed.")

new_m = m.replace("url_for('home') }}#deposit", "url_for('deposit') }}")
new_m = new_m.replace("url_for('home') }}#withdraw", "url_for('withdraw') }}")
if new_m == m and ("url_for('deposit')" not in m or "url_for('withdraw')" not in m):
    raise SystemExit("Could not identify the My-page Deposit/Withdraw menu links. No files changed.")

backup = root / "PIMCO_NAV_BACKUP" / datetime.now().strftime("%Y%m%d-%H%M%S")
backup.mkdir(parents=True, exist_ok=True)
shutil.copy2(home, backup / "home.html")
shutil.copy2(my, backup / "my.html")

h = h.replace(old_home_deposit, new_home_deposit, 1)
h = h.replace(old_home_withdraw, new_home_withdraw, 1)
home.write_text(h, encoding="utf-8")
my.write_text(new_m, encoding="utf-8")

print("Navigation fixed:")
print("Home Deposit -> /deposit")
print("Home Withdraw -> /withdraw")
print("My-page Deposit -> /deposit")
print("My-page Withdraw -> /withdraw")
print("Backup saved at:", backup)
