from pathlib import Path
from datetime import datetime
import re, shutil

root = Path.cwd()
app = root / "app.py"
base_html = root / "templates" / "base.html"
bill_html = root / "templates" / "bill.html"
instructions_html = root / "templates" / "deposit_instructions.html"

required = [app, base_html, bill_html, instructions_html]
missing = [str(p.relative_to(root)) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing required project files: " + ", ".join(missing))

src_app = app.read_text(encoding="utf-8")
src_base = base_html.read_text(encoding="utf-8")
src_bill = bill_html.read_text(encoding="utf-8")

# Remove the secondary top bar (brand word/logo and notification bell) from pages
# where base.html renders it. The home page has its own separate header.
header_pattern = re.compile(
    r"\{% if request\.endpoint not in \[\"auth\", \"home\", \"team\"\] %\}<header class=\"topbar\">.*?</header>\{% endif %\}",
    re.S
)
if not header_pattern.search(src_base):
    raise SystemExit("Could not safely locate the topbar block in base.html. No files changed.")
src_base = header_pattern.sub("", src_base, count=1)

# Keep the pending deposit in the database/admin queue, but do not render it
# in the customer's Bills page until it is approved/rejected.
loop_pattern = re.compile(r"(\{% for r in [^%]+%\})(.*?)(\{% endfor %\})", re.S)
loop_match = loop_pattern.search(src_bill)
if not loop_match:
    raise SystemExit("Could not safely locate the transaction loop in bill.html. No files changed.")
loop_start, loop_body, loop_end = loop_match.groups()
if "r.status" not in loop_body or "r.kind" not in loop_body:
    raise SystemExit("Bills transaction loop does not use the expected r.kind/r.status fields. No files changed.")
if "pimco-hide-pending-deposit" not in src_bill:
    wrapped = (
        loop_start
        + "{% if not (((r.kind|string)|lower == 'deposit') and ((r.status|string)|lower == 'pending')) %}"
        + loop_body
        + "{% endif %}"
        + loop_end
    )
    src_bill = src_bill[:loop_match.start()] + wrapped + src_bill[loop_match.end():]

# Update the recipient constant when present; otherwise update the value passed
# by the existing deposit-instructions route.
constant_pattern = re.compile(r"(?m)^(\s*DEPOSIT_PHONE\s*=\s*)['\"][^'\"]*['\"]")
if constant_pattern.search(src_app):
    src_app = constant_pattern.sub(r"\g<1>'0731199883'", src_app, count=1)
elif "recipient=DEPOSIT_PHONE" in src_app:
    src_app = src_app.replace("recipient=DEPOSIT_PHONE", "recipient='0731199883'", 1)
else:
    raise SystemExit("Could not locate the deposit recipient setting in app.py. No files changed.")

# Ensure the existing instructions route passes the requested recipient name.
# Only replace the recipient_name argument on the deposit-instructions render call.
route_match = re.search(r"def deposit_instructions\(\):.*?(?=\n@app\.route|\Z)", src_app, re.S)
if route_match:
    block = route_match.group(0)
    block_new = re.sub(r"recipient_name\s*=\s*['\"][^'\"]*['\"]", "recipient_name='Collins'", block, count=1)
    if block_new != block:
        src_app = src_app[:route_match.start()] + block_new + src_app[route_match.end():]
    elif "recipient_name=" not in block:
        src_app = src_app[:route_match.start()] + block.replace(
            "recipient='0731199883'", "recipient='0731199883', recipient_name='Collins'", 1
        ) + src_app[route_match.end():]

# Make the instructions page clear and readable on a phone.
instructions = """{% extends "base.html" %}
{% block content %}
<style>
.deposit-instruction-wrap{width:100%;padding:14px 0 28px;box-sizing:border-box}
.deposit-instruction-card{width:calc(100% - 28px);max-width:500px;margin:8px auto;padding:22px 18px;box-sizing:border-box;border-radius:17px;background:#1c1c38;color:#f6f6fb;border:1px solid rgba(255,195,41,.16);box-shadow:0 10px 28px rgba(0,0,0,.2);text-align:center}
.deposit-instruction-card h2{margin:0 0 10px;color:#ffc329;font-size:22px;line-height:1.3}
.deposit-instruction-card p{color:#c5c5d5;font-size:15px;line-height:1.5;margin:8px 0}
.deposit-recipient{margin:20px 0;padding:18px 12px;border-radius:12px;background:#34354f}
.deposit-recipient small{display:block;color:#c5c5d5;font-size:14px;margin-bottom:7px}
.deposit-recipient strong{display:block;color:#ffc329;font-size:26px;letter-spacing:1px}
.deposit-recipient b{display:block;color:#fff;font-size:18px;margin-top:8px}
.deposit-instruction-card .pending-note{font-size:13px;color:#bdbdd0;margin-top:14px}
.deposit-instruction-card a{display:block;margin-top:18px;padding:13px 14px;border-radius:9px;background:#ffbd16;color:#211a22;text-decoration:none;font-weight:800;font-size:16px}
</style>
<section class="deposit-instruction-wrap">
 <div class="deposit-instruction-card">
  <h2>COMPLETE YOUR DEPOSIT</h2>
  <p>Send the exact amount you entered using Mobile Money to the recipient below.</p>
  <div class="deposit-recipient">
   <small>Send money to</small>
   <strong>0731199883</strong>
   <b>Collins</b>
  </div>
  <p>After sending, keep your Mobile Money confirmation message. Your deposit will be checked by an administrator.</p>
  <p class="pending-note">Your deposit request is pending. Your wallet will only be credited after payment is confirmed.</p>
  <a href="{{ url_for('bill') }}">Continue</a>
 </div>
</section>
{% endblock %}
"""

backup = root / "PIMCO_DEPOSIT_PRIVACY_BACKUP" / datetime.now().strftime("%Y%m%d-%H%M%S")
backup.mkdir(parents=True, exist_ok=True)
for p in (app, base_html, bill_html, instructions_html):
    shutil.copy2(p, backup / p.name)

app.write_text(src_app, encoding="utf-8")
base_html.write_text(src_base, encoding="utf-8")
bill_html.write_text(src_bill, encoding="utf-8")
instructions_html.write_text(instructions, encoding="utf-8")

print("Installed:")
print("- Removed the secondary Amazon/Armazon topbar and bell from base.html pages.")
print("- Deposit instructions now show 0731199883 — Collins.")
print("- Pending deposits remain in the admin queue but are hidden from the user's Bills page.")
print("- Existing approval flow remains responsible for wallet credit.")
print("Backup:", backup)
