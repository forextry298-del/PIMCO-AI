#!/usr/bin/env python3
from pathlib import Path
import re, shutil, sys

root = Path.cwd()
app_path = root / "app.py"
my_path = root / "templates" / "my.html"
templates = root / "templates"
if not app_path.exists() or not my_path.exists():
    print("ERROR: Run this installer from the PIMCO_AI project folder.")
    sys.exit(1)

def backup(path):
    saved = path.with_name(path.name + ".settings_backup")
    if not saved.exists():
        shutil.copy2(path, saved)
        print("Backup:", saved)

app = app_path.read_text()
my = my_path.read_text()

route = '''

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if not logged_in():
        return redirect(url_for("auth"))
    message = None
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        with db() as con:
            user = con.execute(
                "SELECT password_hash FROM users WHERE id=?",
                (session["user_id"],)
            ).fetchone()
            if not user or not check_password_hash(user["password_hash"], current_password):
                message = ("error", "Your current password is incorrect.")
            elif len(new_password) < 8:
                message = ("error", "New password must contain at least 8 characters.")
            elif new_password != confirm_password:
                message = ("error", "The new passwords do not match.")
            elif check_password_hash(user["password_hash"], new_password):
                message = ("error", "Choose a password different from your current password.")
            else:
                con.execute(
                    "UPDATE users SET password_hash=? WHERE id=?",
                    (generate_password_hash(new_password), session["user_id"])
                )
                message = ("success", "Password changed successfully.")
    return render_template("settings.html", active="my", message=message)
'''

if 'def settings()' not in app:
    backup(app_path)
    marker = re.search(r'(?m)^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', app)
    if marker:
        app = app[:marker.start()] + route + "\n" + app[marker.start():]
    else:
        app = app.rstrip() + "\n" + route
    app_path.write_text(app)
    print("Added /settings route.")
else:
    print("A settings() route already exists; app.py route left unchanged.")

pattern = r'(<a\b[^>]*href="{{\s*url_for\([\'"])(?:my)([\'"]\)\s*}}"[^>]*>[\s\S]*?<span>\s*Settings\s*</span>)'
updated, count = re.subn(pattern, r'\1settings\2', my, count=1)
if count:
    backup(my_path)
    my_path.write_text(updated)
    print("Updated Settings shortcut.")
elif 'url_for("settings")' in my or "url_for('settings')" in my:
    print("Settings shortcut already points to /settings.")
else:
    print("WARNING: Could not safely identify Settings link in my.html.")

page = '''{% extends "base.html" %}
{% block content %}
<style>
.settings-wrap{max-width:420px;margin:14px auto;padding:0 12px}
.settings-card{background:linear-gradient(145deg,#171b35,#101329);border:1px solid rgba(220,184,91,.25);border-radius:15px;padding:17px;color:#f4f3fa;box-shadow:0 10px 28px rgba(0,0,0,.18)}
.settings-card h2{font-size:19px;margin:0 0 5px;color:#e8c66d}
.settings-sub{font-size:12px;color:#aeb2c8;margin:0 0 16px}
.settings-card label{display:block;font-size:12px;color:#c7c9d8;margin:12px 0 6px}
.settings-card input{width:100%;box-sizing:border-box;border:1px solid #353a5c;background:#0d1125;color:#fff;border-radius:9px;padding:12px;font-size:14px;outline:none}
.settings-card input:focus{border-color:#d9b85f}
.settings-submit{width:100%;border:0;border-radius:9px;background:linear-gradient(90deg,#c49a3a,#f0d27c);color:#171525;font-weight:700;padding:12px;margin-top:16px;font-size:14px}
.settings-note{font-size:11px;color:#9fa5bd;margin:12px 0 0}
.settings-message{padding:9px 11px;border-radius:8px;font-size:12px;margin:0 0 12px}
.settings-error{background:#49232d;color:#ffd9df}.settings-success{background:#183c32;color:#c8ffdf}
</style>
<div class="settings-wrap">
  <section class="settings-card">
    <h2>Account Settings</h2>
    <p class="settings-sub">Update your account password securely.</p>
    {% if message %}
      <div class="settings-message {{ 'settings-success' if message[0] == 'success' else 'settings-error' }}">{{ message[1] }}</div>
    {% endif %}
    <form method="post" action="{{ url_for('settings') }}">
      <label for="current_password">Current password</label>
      <input id="current_password" name="current_password" type="password" autocomplete="current-password" required>
      <label for="new_password">New password</label>
      <input id="new_password" name="new_password" type="password" minlength="8" autocomplete="new-password" required>
      <label for="confirm_password">Confirm new password</label>
      <input id="confirm_password" name="confirm_password" type="password" minlength="8" autocomplete="new-password" required>
      <button class="settings-submit" type="submit">CHANGE PASSWORD</button>
    </form>
    <p class="settings-note">Use at least 8 characters. Your password is stored as a secure hash.</p>
  </section>
</div>
{% endblock %}
'''
templates.mkdir(exist_ok=True)
settings_path = templates / "settings.html"
if settings_path.exists():
    backup(settings_path)
settings_path.write_text(page)
print("Created templates/settings.html.")
print("Now run: python -m py_compile app.py")
