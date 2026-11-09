#!/usr/bin/env python3
from pathlib import Path
import re, shutil, sys
from urllib.parse import quote

ROOT = Path.cwd()
TARGET = ROOT / "templates" / "my.html"
if not TARGET.exists():
    print("ERROR: templates/my.html not found. Run from ~/storage/downloads/PIMCO_AI")
    sys.exit(1)

html = TARGET.read_text()
original = html

def backup(path):
    b = path.with_name(path.name + ".manager_salary_backup")
    if not b.exists():
        shutil.copy2(path, b)
        print("Backup created:", b)

# Manager shortcut: preserve its contents and styling; only change its destination.
manager_url = "https://wa.me/971529547643?text=" + quote(
    "Hello manager, am a new member in PIMCO, I just wanted some guidance."
)
manager_count = 0

# Update href on the <a> element that contains the Manager label.
anchor_pattern = re.compile(r'<a\b(?P<attrs>[^>]*)>(?P<body>[\s\S]*?</a>)', re.I)
def update_manager(match):
    global manager_count
    if not re.search(r'>\s*Manager\s*<', match.group("body"), re.I):
        return match.group(0)
    attrs = match.group("attrs")
    if re.search(r'\bhref\s*=', attrs, re.I):
        attrs = re.sub(r'\bhref\s*=\s*(["\']).*?\1',
                       'href="' + manager_url + '"', attrs, count=1, flags=re.I)
    else:
        attrs += ' href="' + manager_url + '"'
    manager_count += 1
    return '<a' + attrs + '>' + match.group("body")

html = anchor_pattern.sub(update_manager, html)

# If Manager is implemented as a button rather than an anchor, open WhatsApp on click.
if manager_count == 0:
    button_pattern = re.compile(r'<button\b(?P<attrs>[^>]*)>(?P<body>[\s\S]*?</button>)', re.I)
    def update_manager_button(match):
        global manager_count
        if not re.search(r'>\s*Manager\s*<', match.group("body"), re.I):
            return match.group(0)
        attrs = match.group("attrs")
        action = "window.location.href='" + manager_url + "'"
        if re.search(r'\bonclick\s*=', attrs, re.I):
            attrs = re.sub(r'\bonclick\s*=\s*(["\']).*?\1',
                           'onclick="' + action + '"', attrs, count=1, flags=re.I)
        else:
            attrs += ' onclick="' + action + '"'
        manager_count += 1
        return '<button' + attrs + '>' + match.group("body")
    html = button_pattern.sub(update_manager_button, html)

# Salary action: keep the button and its appearance; show the requested notice instead.
salary_message = "Monthly salary starts next month on 2nd Dec."
salary_count = 0
def update_salary_anchor(match):
    global salary_count
    if not re.search(r"Get\s+last\s+month'?s\s+salary", match.group("body"), re.I):
        return match.group(0)
    attrs = match.group("attrs")
    action = "alert(" + repr(salary_message) + "); return false;"
    if re.search(r'\bonclick\s*=', attrs, re.I):
        attrs = re.sub(r'\bonclick\s*=\s*(["\']).*?\1',
                       'onclick="' + action + '"', attrs, count=1, flags=re.I)
    else:
        attrs += ' onclick="' + action + '"'
    attrs = re.sub(r'\bhref\s*=\s*(["\']).*?\1', 'href="#"', attrs, count=1, flags=re.I)
    salary_count += 1
    return '<a' + attrs + '>' + match.group("body")

html = anchor_pattern.sub(update_salary_anchor, html)

if salary_count == 0:
    button_pattern = re.compile(r'<button\b(?P<attrs>[^>]*)>(?P<body>[\s\S]*?</button>)', re.I)
    def update_salary_button(match):
        global salary_count
        if not re.search(r"Get\s+last\s+month'?s\s+salary", match.group("body"), re.I):
            return match.group(0)
        attrs = match.group("attrs")
        action = "alert(" + repr(salary_message) + "); return false;"
        if re.search(r'\bonclick\s*=', attrs, re.I):
            attrs = re.sub(r'\bonclick\s*=\s*(["\']).*?\1',
                           'onclick="' + action + '"', attrs, count=1, flags=re.I)
        else:
            attrs += ' onclick="' + action + '"'
        salary_count += 1
        return '<button' + attrs + '>' + match.group("body")
    html = button_pattern.sub(update_salary_button, html)

if manager_count == 0:
    print("ERROR: Could not find a Manager link/button in templates/my.html. No files changed.")
    sys.exit(2)
if salary_count == 0:
    print("ERROR: Could not find the Get last month's salary link/button in templates/my.html. No files changed.")
    sys.exit(3)

if html != original:
    backup(TARGET)
    TARGET.write_text(html)

print("SUCCESS: Manager opens WhatsApp with the requested pre-filled message.")
print("SUCCESS: Salary button displays:", salary_message)
print("All other page content and styling have been preserved.")
