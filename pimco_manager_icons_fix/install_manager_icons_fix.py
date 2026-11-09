#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import re, shutil, sys

ROOT = Path.cwd()
MY = ROOT / "templates" / "my.html"
DEPOSIT = ROOT / "templates" / "deposit.html"
WITHDRAW = ROOT / "templates" / "withdraw.html"

required = [MY, DEPOSIT, WITHDRAW]
missing = [str(p.relative_to(ROOT)) for p in required if not p.is_file()]
if missing:
    print("ERROR: Missing required files:", ", ".join(missing))
    sys.exit(1)

changes = {}
my = MY.read_text(encoding="utf-8")
old_link = "https://wa.me/971529547643?text="
new_link = "https://wa.me/971521109383?text="
if old_link in my:
    changes[MY] = my.replace(old_link, new_link)
elif new_link in my:
    print("Manager number is already updated.")
else:
    print("ERROR: Could not find the expected manager WhatsApp link in templates/my.html.")
    sys.exit(1)

# Inline SVG icons are deliberately self-contained; no external icon library is needed.
deposit_icon = (
    '<svg class="pw-title-icon" viewBox="0 0 24 24" aria-hidden="true" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 3v12m-5-5 5 5 5-5"/><path d="M4 17v3h16v-3"/>'
    '</svg>'
)
withdraw_icon = (
    '<svg class="pw-title-icon" viewBox="0 0 24 24" aria-hidden="true" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 21V9m-5 5 5-5 5 5"/><path d="M4 7V4h16v3"/>'
    '</svg>'
)
icon_css = """
<style>
.pw-title{display:flex;align-items:center;gap:10px}
.pw-title-icon{width:27px;height:27px;flex:0 0 27px;color:#ffc329;
  padding:5px;border-radius:9px;background:rgba(255,195,41,.13);box-sizing:border-box}
.pw-prefix-icon{width:19px;height:19px;display:block}
.pw-inputrow .pw-prefix{display:flex;align-items:center;justify-content:center}
</style>
"""

for path, icon in ((DEPOSIT, deposit_icon), (WITHDRAW, withdraw_icon)):
    content = path.read_text(encoding="utf-8")
    if "pw-title-icon" not in content:
        # Decorate the page title without changing its wording.
        content, count = re.subn(
            r'(<h[12][^>]*class=["\'][^"\']*pw-title[^"\']*["\'][^>]*>)',
            lambda m: m.group(1) + icon,
            content, count=1
        )
        if count != 1:
            print(f"ERROR: Could not locate .pw-title heading in {path.relative_to(ROOT)}")
            sys.exit(1)
    if "pw-title-icon" not in content:
        print(f"ERROR: Icon insertion failed for {path.relative_to(ROOT)}")
        sys.exit(1)
    if "pw-title-icon" not in path.read_text(encoding="utf-8"):
        content = content.replace("</head>", icon_css + "\n</head>", 1) if "</head>" in content else icon_css + "\n" + content
    changes[path] = content

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backups = {}
try:
    for path, new_content in changes.items():
        backup = path.with_name(path.name + f".backup_manager_icons_{stamp}")
        shutil.copy2(path, backup)
        backups[path] = backup
        path.write_text(new_content, encoding="utf-8")
    # Ensure the manager number was updated only in the Manager WhatsApp link.
    check = MY.read_text(encoding="utf-8")
    if new_link not in check or old_link in check:
        raise RuntimeError("Manager contact verification failed.")
    print("SUCCESS: Manager WhatsApp number updated to +971521109383.")
    print("SUCCESS: Deposit and withdrawal pages now have matching gold SVG title icons.")
    print("Backups created:")
    for backup in backups.values():
        print(" -", backup.name)
except Exception as exc:
    for path, backup in backups.items():
        shutil.copy2(backup, path)
    print("ERROR: Installation failed; original files restored:", exc)
    sys.exit(1)
