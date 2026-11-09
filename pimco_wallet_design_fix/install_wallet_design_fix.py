from pathlib import Path
from datetime import datetime
import shutil

root = Path.cwd()
app = root / "app.py"
td = root / "templates"
bundle = Path(__file__).resolve().parent / "templates"
if not app.exists() or not td.exists():
    raise SystemExit("Run from the PIMCO_AI project root containing app.py and templates/.")

src = app.read_text(encoding="utf-8")
# The screenshot-style pages do not ask for a separate network field.
# Allow the network to be blank while retaining the phone-number and amount checks.
deposit_old = "if not phone or network not in ('MTN', 'Airtel'):"
deposit_new = "if not phone:"
withdraw_old = "if amount < 3000 or not phone or network not in ('MTN', 'Airtel'):"
withdraw_new = "if amount < 3000 or not phone:"
if deposit_old not in src:
    raise SystemExit("Could not find the expected deposit validation line. No files changed.")
if withdraw_old not in src:
    raise SystemExit("Could not find the expected withdrawal validation line. No files changed.")

backup = root / "PIMCO_WALLET_DESIGN_BACKUP" / datetime.now().strftime("%Y%m%d-%H%M%S")
backup.mkdir(parents=True, exist_ok=True)
shutil.copy2(app, backup / "app.py")
for name in ("deposit.html", "withdraw.html"):
    if (td / name).exists():
        shutil.copy2(td / name, backup / name)

src = src.replace(deposit_old, deposit_new, 1)
src = src.replace(withdraw_old, withdraw_new, 1)
app.write_text(src, encoding="utf-8")
for name in ("deposit.html", "withdraw.html"):
    shutil.copy2(bundle / name, td / name)

print("Installed screenshot-style Deposit and Withdrawal pages.")
print("Deposit minimum: UGX 30,000. Withdrawal minimum: UGX 3,000; fee remains 10%.")
print("No network selector is shown; the entered/registered phone number is saved.")
print("Backup:", backup)
