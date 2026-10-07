# E-mail and password reset - Railway variables (2026-10-07)

Names only. Values are set by the owner in Railway (service -> Variables) and are never written to the repo.
Code: `app/services/emailer.py` (sending), `app/services/password_reset.py` (reset links).

## Variables

| Name | Needed? | What it does |
|---|---|---|
| `EMAIL_ENABLED` | already set | `false` switches every e-mail off (reset links, welcome, sign-in alerts). Anything else, or unset, means on. |
| `EMAIL_PROVIDER` | recommended | `resend` = send through Resend's API; `smtp` = send through the `SMTP_*` server; `auto` (default when unset) = Resend if `RESEND_API_KEY` is set, otherwise SMTP if `SMTP_HOST` is set, otherwise nothing is sent. |
| `RESEND_API_KEY` | for Resend | Resend API key (a "sending access" key for smartwarrantyhub.com is enough). |
| `MAIL_FROM` | already set | Sender. Should be `Smart Warranty Hub <noreply@smartwarrantyhub.com>`; this is also the default when unset or empty. |
| `MAIL_REPLY_TO` | optional | Where replies go. Default `support@smartwarrantyhub.com`. |
| `SIGNIN_ALERT_EMAILS` | optional | `1` sends an alert e-mail on every sign-in. **Off by default** (unset or anything else). |
| `EMAIL_DAILY_NONESSENTIAL_STOP` | optional | Daily guard threshold, default `80`. See "Daily guard" below. |
| `APP_BASE_URL` | optional | Start of the links in e-mails. Default `https://www.smartwarrantyhub.com`. |
| `SMTP_HOST`, `SMTP_PORT` | already set | SMTP server and port (used when the provider is `smtp`, or `auto` without `RESEND_API_KEY`). Port default 587. |
| `SMTP_USER`, `SMTP_PASS` | already set | SMTP login. |
| `SMTP_STARTTLS`, `SMTP_SSL` | optional | Encryption: STARTTLS is on by default; set `SMTP_SSL=true` (and usually port 465) for implicit TLS. |
| `RATE_LIMIT_PASSWORD_RESET_REQUEST_MAX` / `_WINDOW_SEC` | optional | Reset requests per client (default 5 per 900 s). |
| `RATE_LIMIT_PASSWORD_RESET_ACCOUNT_MAX` / `_WINDOW_SEC` | optional | Reset e-mails per account (default 3 per 3600 s). |
| `RATE_LIMIT_PASSWORD_RESET_SUBMIT_MAX` / `_WINDOW_SEC` | optional | Link checks and new-password submissions per client (default 10 per 900 s). |

Minimum for Resend: add `RESEND_API_KEY` and `EMAIL_PROVIDER=resend`. If the existing `SMTP_*` variables
already point at Resend's SMTP server, nothing new is needed: SMTP keeps working, but the `app`/`type` tags are only
attached when sending through Resend's API.

## What is sent

| Type tag (`type=`) | When |
|---|---|
| `password_reset` | Someone asks for a reset link for an account with that e-mail address. |
| `welcome` | A new account is created with an e-mail address. |
| `login_alert` | Every sign-in of an account with an e-mail address, **only when `SIGNIN_ALERT_EMAILS=1`**. |
| `product_registered` | A product is registered (existing behaviour). |

Every Resend message carries the tags `app=swh` and `type=<type above>`, so Resend's logs can be filtered.

## Daily guard

Resend's free plan allows 100 e-mails a day. SWH counts every e-mail the provider accepted in the current UTC
day (table `email_daily_counts`; if the database cannot be reached, a count in memory is used). Once 80 have gone
out (`EMAIL_DAILY_NONESSENTIAL_STOP`), only **password-reset** e-mails are still sent until midnight UTC (05:30
India time); welcome, sign-in alerts, product-registered and any reminder e-mails are skipped and logged as
"daily guard". Password resets are never stopped by the guard, so the last 20 of the 100 are kept for them.
Raise the threshold if you move to a paid Resend plan.

## Checks after deploy (owner)

1. Open `/forgot-password`. If it says "Password reset is not available right now", e-mail is not configured:
   check `EMAIL_ENABLED`, `EMAIL_PROVIDER` and the key/host for the chosen provider.
2. Ask for a link for your own account; the e-mail should arrive from `noreply@smartwarrantyhub.com`, with
   Reply-To `support@smartwarrantyhub.com`. In Resend -> Emails it shows tags `app: swh`, `type: password_reset`.
3. Open the link, set a new password, and confirm that a second browser where you were signed in is signed out.
4. Keep Resend **click tracking off** for this domain: it rewrites links, and the reset link must reach the
   site unchanged.
