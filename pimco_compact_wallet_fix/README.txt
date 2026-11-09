PIMCO AI COMPACT WALLET FIX

Run from the project root:
  unzip -o ~/storage/downloads/PIMCO_AI_COMPACT_WALLET_FIX.zip
  python pimco_compact_wallet_fix/install_compact_wallet_fix.py
  python -m py_compile app.py
  python app.py

This replaces only deposit.html and withdraw.html. It restores a compact, centered, single-column card with modest typography and full-width fields, matching the supplied reference style. It includes subtle waves behind the card.

It keeps the existing route names and field names. Deposit min UGX 30,000; withdrawal min UGX 3,000; the existing 10% fee is still calculated by app.py. It does not change backend or database logic. Original templates are backed up.
