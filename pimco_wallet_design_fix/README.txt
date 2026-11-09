PIMCO AI WALLET DESIGN FIX

Run from the project root:
  python pimco_wallet_design_fix/install_wallet_design_fix.py

This backs up app.py and the two wallet templates, installs a full-width responsive layout matching the supplied Deposit and Withdrawal references, and removes the separate network selector from these pages. Deposit remains minimum UGX 30,000. Withdrawal remains minimum UGX 3,000 and 10% fee. Existing form actions are preserved. The app route accepts the phone number without a separate network selector.

The app does not send an actual Mobile Money push prompt unless a payment-provider integration is configured. Deposit requests still require real payment verification/admin approval before wallet credit.

Then run:
  python -m py_compile app.py
  python app.py
