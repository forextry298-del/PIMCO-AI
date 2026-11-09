PIMCO AI WALLET + WAVES FIX

From the PIMCO_AI project root (the folder containing app.py), run:
  python pimco_wallet_fix/install_wallet_fix.py

This backs up app.py and existing wallet templates, enforces UGX 30,000 minimum deposits, stores deposit phone/network as pending, and installs animated waves on both wallet pages. Your existing withdrawal route continues to enforce UGX 3,000 minimum, 10% fee, immediate balance debit and pending Bills entry. If an admin rejects a withdrawal, the installer also adds a wallet-ledger refund entry.

Deposit funds are credited only by the existing admin approval process after the actual Mobile Money payment is checked. This package does not pretend to automatically verify MTN/Airtel payments.

Then run:
  python -m py_compile app.py
  python app.py

Log in and test /deposit and /withdraw. Do not deploy until checked.
