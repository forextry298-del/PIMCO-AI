from pathlib import Path
from datetime import datetime
import shutil

root = Path.cwd()
app = root / "app.py"
target = root / "templates"
source = Path(__file__).resolve().parent / "templates"
if not app.exists() or not target.exists():
    raise SystemExit("Run this from the PIMCO_AI project root.")
backup = root / "PIMCO_COMPACT_WALLET_BACKUP" / datetime.now().strftime("%Y%m%d-%H%M%S")
backup.mkdir(parents=True, exist_ok=True)
for name in ("deposit.html", "withdraw.html"):
    dst = target / name
    if dst.exists():
        shutil.copy2(dst, backup / name)
    shutil.copy2(source / name, dst)
print("Compact Deposit and Withdrawal layouts installed.")
print("Backup:", backup)
print("Only the two HTML templates were changed; app.py and database were untouched.")
