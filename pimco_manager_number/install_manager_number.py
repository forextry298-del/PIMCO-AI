#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import shutil, sys

root = Path.cwd()
target = root / "templates" / "my.html"
if not target.is_file():
    print("ERROR: Run this installer from the PIMCO_AI project folder; templates/my.html was not found.")
    sys.exit(1)

source = target.read_text(encoding="utf-8")
# wa.me requires the international country code. This is Uganda number 0758878297.
old_links = (
    "https://wa.me/971521109383?text=",
    "https://wa.me/971529547643?text=",
)
new_link = "https://wa.me/256758878297?text="

if new_link in source:
    print("Manager WhatsApp contact is already set to 0758878297.")
    sys.exit(0)

updated = source
for old in old_links:
    updated = updated.replace(old, new_link)

if updated == source:
    print("ERROR: Could not find the previous manager WhatsApp link in templates/my.html.")
    print("No files were changed. Please send the Manager link line from templates/my.html.")
    sys.exit(1)

backup = target.with_name(target.name + ".backup_manager_number_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
shutil.copy2(target, backup)
try:
    target.write_text(updated, encoding="utf-8")
    verify = target.read_text(encoding="utf-8")
    if new_link not in verify:
        raise RuntimeError("Updated manager link could not be verified.")
except Exception as exc:
    shutil.copy2(backup, target)
    print("ERROR: Update failed; original file restored:", exc)
    sys.exit(1)

print("SUCCESS: Manager contact is now 0758878297.")
print("WhatsApp link uses Uganda international format: +256 758 878 297.")
print("Backup created:", backup.name)
