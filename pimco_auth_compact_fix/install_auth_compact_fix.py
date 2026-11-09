#!/usr/bin/env python3
from pathlib import Path
import re, shutil, sys

target = Path.cwd() / "templates" / "auth.html"
if not target.is_file():
    print("ERROR: Run from the PIMCO_AI project folder; templates/auth.html was not found.")
    sys.exit(1)

html = target.read_text()
required = [".auth-stage", ".auth-content", ".wave-auth-form", ".wave-field", ".wave-submit"]
if not all(token in html for token in required):
    print("ERROR: The expected PIMCO AI auth layout was not found. No changes made.")
    sys.exit(2)

css = """<style>
/* Compact, responsive registration and login layout */
.auth-stage{box-sizing:border-box;min-height:0;display:flex;align-items:flex-start;justify-content:center;padding:10px 10px 18px}
.auth-content{box-sizing:border-box;width:100%;max-width:430px;margin:0 auto}
.auth-brand-word{text-align:center;font-size:22px;line-height:1.2;font-weight:900;color:#20c5e8;margin:2px 0 5px}
.auth-welcome{text-align:center;font-size:20px;line-height:1.25;margin:0 0 12px}
.wave-auth-form{box-sizing:border-box;width:100%;padding:15px 14px;border-radius:15px;background:rgba(7,30,65,.96);border:1px solid rgba(65,190,230,.38);box-shadow:0 7px 20px #0002;display:flex;flex-direction:column;gap:9px}
.wave-field{box-sizing:border-box;width:100%;height:47px;min-height:47px;display:flex;align-items:center;padding:0 11px;border-radius:9px;background:#ffffff18;border:1px solid #ffffff26}
.wave-field input{box-sizing:border-box;width:100%;min-width:0;height:45px;border:0;outline:0;background:transparent;color:white;font-size:14px;padding:0}
.wave-field input::placeholder{color:#ffffffb8;opacity:1}
.wave-submit{width:100%;height:45px;min-height:45px;border:0;border-radius:9px;background:linear-gradient(110deg,#0879c9,#20c5e8);color:white;font-weight:800;font-size:14px}
.wave-auth-switch{text-align:center;font-size:12px;line-height:1.4;padding-top:2px}
.wave-auth-switch a{color:#75def4;text-decoration:none;font-weight:700}
@media(max-width:380px){.auth-stage{padding:7px 8px 14px}.wave-auth-form{padding:13px 11px;gap:8px}.auth-welcome{font-size:19px}}
</style>"""

updated, n = re.subn(r"<style>[\s\S]*?</style>", lambda m: css, html, count=1)
if n != 1:
    print("ERROR: Could not safely locate the auth stylesheet. No changes made.")
    sys.exit(3)

backup = target.with_name("auth.html.before_compact_backup")
if not backup.exists():
    shutil.copy2(target, backup)
target.write_text(updated)
print("SUCCESS: Registration and login forms now use a compact responsive layout.")
print("Existing form fields, routes, password confirmation script, and validation are preserved.")
print("Backup:", backup)
