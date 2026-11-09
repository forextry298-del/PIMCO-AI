ARMAZON LOCAL TEST BUILD

Implemented in this build:
- Deposit form with MTN/Airtel pending requests and USDT unavailable message.
- Deposit instructions for 0731199883 (Colins).
- Withdrawal checks users.balance and deducts only when sufficient; rejection refunds.
- Bill transaction list.
- Admin route restricted to registered phone 0758878297; deposit/withdraw approve/reject, user block/password reset, machine settings including Sold Out.
- Idempotent machine earnings processing on requests using Uganda UTC+3 calendar date. No-lock purchases credit daily through duration. Locked purchases credit the accumulated lock-period amount on expiry.
- Manager support message inbox (text only; image upload and live AI responses are not wired in this local build).

IMPORTANT:
- This is a local development/test build, not a live payment gateway. Deposit approvals must only be made after verifying actual payment.
- The admin account must be registered with 0758878297 before the admin route is accessible.
- Existing database is not included in the ZIP. Keep a backup of instance/amazon.db before replacing files.
- The admin machine editor saves machine_settings. Existing catalogue values remain code defaults unless overridden in future catalogue integration.
- Daily earnings are idempotent but triggered by application requests, not a persistent midnight scheduler. For reliable 00:00 processing in production, configure a scheduled job to invoke process_daily_earnings().
