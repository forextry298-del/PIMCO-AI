PIMCO AI HEADER + DEPOSIT PRIVACY FIX

Run from the PIMCO_AI project root:
  unzip -o ~/storage/downloads/PIMCO_AI_DEPOSIT_PRIVACY_FIX.zip
  python pimco_deposit_privacy_fix/install_deposit_privacy_fix.py
  python -m py_compile app.py
  python app.py

Changes:
1. Removes the secondary top header containing the Armazon/Amazon wordmark and bell from pages where base.html displays it. It does not alter the home page's own header.
2. Deposit instructions show Mobile Money recipient 0731199883, Collins.
3. Deposit requests continue to be stored as pending and are available in the admin deposit queue.
4. Pending deposits are hidden from the customer's Bills page until their status changes.
5. Wallet credit still depends on the existing admin approval flow.

The installer backs up app.py, base.html, bill.html and deposit_instructions.html before editing.
