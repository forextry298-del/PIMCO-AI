PIMCO AI wallet pages update

Extract into your PIMCO_AI project folder and run:
python install_wallet_update.py

The installer backs up app.py and the old deposit/withdraw pages, installs the compact navy/gold pages, sets the withdrawal minimum to UGX 3,000 in the matching route, and runs a Python syntax test.

Important: This does not implement mobile-money payment verification or automatically credit deposits. Only credit deposits after a real confirmed payment. Check your existing deposit route and withdrawal ledger/bill logic before using live.
