#!/usr/bin/env python3
import os, shutil, sys, datetime, py_compile
ROOT=os.path.abspath(os.getcwd())
APP=os.path.join(ROOT,"app.py")
HOME=os.path.join(ROOT,"templates","home.html")
if not os.path.isfile(APP) or not os.path.isfile(HOME):
    sys.exit("ERROR: Run from PIMCO_AI folder; app.py and templates/home.html are required.")
src=open(APP,encoding="utf-8").read()
html=open(HOME,encoding="utf-8").read()
old_src,old_html=src,html

if "admin_access=admin_access" not in src:
    start=src.find("def home():")
    if start < 0:
        sys.exit("ERROR: home() route not found. No files changed.")
    uid_line='    uid = session["user_id"]'
    pos=src.find(uid_line,start)
    render_line='return render_template("home.html",active="home",show_login_notice=show_login_notice,metrics=metrics)'
    render_pos=src.find(render_line,start)
    if pos < 0 or render_pos < 0:
        sys.exit("ERROR: Expected home() lines not found. No files changed.")
    pos += len(uid_line)
    lookup = """
    with db() as admin_con:
        admin_row=admin_con.execute("SELECT phone FROM users WHERE id=?", (uid,)).fetchone()
    admin_digits="".join(ch for ch in str(admin_row["phone"] or "") if ch.isdigit()) if admin_row else ""
    admin_access=admin_digits.endswith("758878297")
"""
    src=src[:pos]+lookup+src[pos:]
    src=src.replace(render_line,'return render_template("home.html",active="home",show_login_notice=show_login_notice,metrics=metrics,admin_access=admin_access)',1)

if 'id="pimcoAdminShortcut"' not in html:
    anchor='<div class="home-dashboard">'
    if anchor not in html:
        sys.exit("ERROR: home-dashboard insertion point not found. No files changed.")
    shortcut="""<div class="home-dashboard">
  {% if admin_access %}
  <a id="pimcoAdminShortcut" href="{{ url_for('admin') }}" aria-label="Open admin panel">
    <span class="pimco-admin-shortcut-icon">⚙️</span>
    <span><strong>ADMIN PANEL</strong><small>Manage deposits, withdrawals and users</small></span>
    <span class="pimco-admin-shortcut-arrow">›</span>
  </a>
  <style>
    #pimcoAdminShortcut{display:flex;align-items:center;gap:11px;width:100%;box-sizing:border-box;margin:0 0 13px;padding:11px 13px;border:1px solid rgba(218,177,91,.48);border-radius:12px;background:linear-gradient(110deg,#24232a,#171820);color:#f4d28c;text-decoration:none;box-shadow:0 3px 12px rgba(0,0,0,.12)}
    #pimcoAdminShortcut .pimco-admin-shortcut-icon{width:37px;height:37px;display:grid;place-items:center;border-radius:10px;background:rgba(218,177,91,.14);font-size:20px;flex:0 0 37px}
    #pimcoAdminShortcut strong{display:block;font-size:13px;letter-spacing:.5px}
    #pimcoAdminShortcut small{display:block;margin-top:3px;color:#c5c0b5;font-size:11px}
    #pimcoAdminShortcut .pimco-admin-shortcut-arrow{margin-left:auto;font-size:24px;color:#e5bd6c}
  </style>
  {% endif %}"""
    html=html.replace(anchor,shortcut,1)

stamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy2(APP,APP+".backup_"+stamp)
shutil.copy2(HOME,HOME+".backup_"+stamp)
with open(APP,"w",encoding="utf-8") as f: f.write(src)
with open(HOME,"w",encoding="utf-8") as f: f.write(html)
try:
    py_compile.compile(APP,doraise=True)
except Exception as e:
    with open(APP,"w",encoding="utf-8") as f: f.write(old_src)
    with open(HOME,"w",encoding="utf-8") as f: f.write(old_html)
    sys.exit("ERROR: app.py compile failed; original files restored. "+str(e))
print("SUCCESS: Admin shortcut added to home page.")
print("Only registered phone 0758878297 (or +256758878297) sees the shortcut.")
print("Backups created. Restart using: python app.py")
