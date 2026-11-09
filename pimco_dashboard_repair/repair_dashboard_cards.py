#!/usr/bin/env python3
from pathlib import Path
import re, shutil, sys

root=Path.cwd()
app=root/"app.py"
home=root/"templates"/"home.html"
backup=root/"templates"/"home.html.before_dashboard_metrics_backup"
if not app.is_file() or not home.is_file():
    print("ERROR: Run from the PIMCO_AI project folder."); sys.exit(1)
if not backup.is_file():
    print("ERROR: Original dashboard backup not found. No files changed."); sys.exit(2)

source=backup.read_text()
def replace_card(source, card_class, label, value):
    if card_class:
        rx=re.compile(r'(<a\b[^>]*class=["\'][^"\']*\b'+re.escape(card_class)+r'\b[^"\']*["\'][^>]*>)([\s\S]*?)(</a>)',re.I)
    else:
        rx=re.compile(r'(<a\b[^>]*>)([\s\S]*?)(</a>)',re.I)
    matches=list(rx.finditer(source))
    for m in matches:
        body=m.group(2)
        if re.search(r'<small>\s*'+re.escape(label)+r'\s*</small>',body,re.I):
            body2,n=re.subn(r'<b>[\s\S]*?</b>','<b>'+value+'</b>',body,count=1,flags=re.I)
            if n!=1: raise RuntimeError("Could not replace value for "+label)
            return source[:m.start(2)]+body2+source[m.end(2):]
    raise RuntimeError("Card not found: "+label)

try:
    updated=source
    for label,value in [
        ("Deposit details","{{ '%.2f'|format(metrics.deposit_total) }}"),
        ("Withdraw details","{{ '%.2f'|format(metrics.withdrawal_total) }}"),
        ("AI Income","{{ '%.2f'|format(metrics.ai_income) }}"),
        ("Today's earnings","{{ '%.2f'|format(metrics.today_income) }}"),
    ]:
        updated=replace_card(updated,"home-stat",label,value)
    for label,value in [
        ("Invite Count","{{ metrics.invite_count }}"),
        ("Team Count","{{ metrics.team_count }}"),
        ("Team income","{{ '%.2f'|format(metrics.team_income) }}"),
    ]:
        updated=replace_card(updated,None,label,value)
except Exception as e:
    print("ERROR:",e)
    print("No files changed.")
    sys.exit(3)

repair_backup=home.with_name("home.html.before_dashboard_card_repair_v2")
if not repair_backup.exists():
    shutil.copy2(home,repair_backup)
home.write_text(updated)
print("SUCCESS: Dashboard template restored and all seven metrics inserted.")
print("Only templates/home.html was changed. app.py and database were not changed.")
print("Restart Flask and refresh Chrome.")
