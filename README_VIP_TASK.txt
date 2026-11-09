VIP TASK UPDATE
===============

- Adds a compact /vip-task page using the existing dark teal / charcoal platform theme.
- VIP 1-10 targets and rewards are configured from the supplied screenshots and instructions.
- Only direct Level 1 referrals (users.referred_by) with at least one deposits.status='approved' record count.
- Each VIP reward is protected by a UNIQUE(user_id, vip_level) claim and is credited to users.balance once.
- New registrations reached through /i/REFERRALCODE save the referring user as referred_by.
- The VIP page checks eligibility and credits any newly earned reward when opened.

IMPORTANT INTEGRATION NOTE:
This source version does not contain a deposit submission/admin-approval workflow. When your real deposit approval code marks a deposit approved, it must insert/update a row in the deposits table (user_id, amount, status='approved', approved_at) and call process_vip_rewards(con, referrer_user_id) in the same database transaction (or the user will receive the reward on their next VIP Task page visit). Do not mark deposits approved until payment has actually been verified.

The ZIP excludes the local SQLite database and secrets. Back up your own database before replacing project files.
