from pathlib import Path
import re, os

root = Path(".")
extensions = {".py", ".html", ".css", ".js", ".txt", ".md"}

# Update source files while preserving the existing database filename.
for p in root.rglob("*"):
    if not p.is_file() or ".git" in p.parts or "instance" in p.parts:
        continue
    if any(x in p.name for x in (".backup", ".before_", ".bill_backup")):
        continue
    if p.suffix.lower() not in extensions:
        continue

    try:
        s = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue

    s = s.replace("amazon.db", "amazon.db")
    s = re.sub(r"pimco-", "pimco-", s, flags=re.I)
    s = re.sub(r"\bAMAZON_PLATFORM\b", "PIMCO_AI", s)
    s = re.sub(r"\bAmazon\b", "PIMCO AI", s, flags=re.I)
    s = s.replace("pimco-local-demo", "pimco-ai-local-demo")
    s = s.replace("amazon.db", "amazon.db")

    if p.as_posix() == "templates/team.html":
        s = s.replace(
            "{{ request.host_url }}i/{{ referral }}",
            "https://met8-vip.com/pages/login/index?type=2&code={{ referral }}"
        )

    p.write_text(s, encoding="utf-8")

# Rename pimco-named images without changing their image contents.
images = root / "static" / "images"
if images.exists():
    for p in list(images.iterdir()):
        if p.is_file() and "PIMCO AI" in p.name.lower():
            new_name = re.sub("PIMCO AI", "pimco", p.name, flags=re.I)
            p.rename(p.with_name(new_name))

print("PIMCO AI branding and invitation link updated.")
