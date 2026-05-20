# QR Stempel

A minimal, mobile-first **digital stamp card** for cafés, bakeries, and small shops.
No app install, no email signup — customers' stamps are tied to a token stored in their browser.

- **Host** generates one-time stamp QR codes at the counter.
- **Customer** scans with their phone camera (any browser), the stamp lands on their card.
- After N stamps the customer generates a redemption QR for the host to scan.

Built with Flask + SQLite. Designed to fit on a single Fly.io machine (256 MB) or any tiny VPS.

---

## Quickstart (local)

```bash
# 1. Run with Docker Compose
docker compose up --build
# → http://localhost:9001

# 2. Or run natively
cd services/web
pip install -r requirements.txt
python manage.py run -h 0.0.0.0 -p 5000
```

Create a host/company account so the login page lists it:

No setup is needed — visit `/login`, leave the token field empty, and a fresh card is created.

## How it works

QR Stempel is **peer-to-peer**: every user can both give and collect stamps.
There's no separate "host" account.

1. **Give a stamp.** On your `/me` page, tap *Generate stamp QR*. The QR encodes
   `/scan/<one-time-claim>`. Anyone who scans it (with their phone camera) gets
   redirected to your server, which binds the stamp to *their* card.
2. **Collect.** Each person you've collected stamps from shows up as a card on
   your `/me` page.
3. **Redeem.** When a card is full, tap *Redeem* — the app shows a QR encoding
   `/r/<one-time-redeem>`. The host scans it; the server verifies it's their
   card and marks N stamps as used.

### Security model

The user's `user_token` is a bearer credential (paste it on a new device to
restore your card). It is **never** put into URLs, QR codes, or HTML rendered
for anyone else:

- Auth is a **Flask session cookie**, set on login.
- QR codes only carry one-shot random UUIDs (`Stempel.token`, `RedeemRequest.redeem_token`).
- Cross-user identifiers in URLs are the public `User.id` integer.
- `/api/token` (auth-gated) is the only way for the browser to retrieve the
  user's own recovery token.

## Configuration

| Env var            | Default                            | Purpose                                      |
|--------------------|------------------------------------|----------------------------------------------|
| `DATABASE_URL`     | `sqlite:///services/web/data/...`  | SQLAlchemy DB URL                            |
| `SECRET_KEY`       | `dev-secret-change-me`             | Flask secret key                             |
| `STAMPS_TO_REDEEM` | `3`                                | Number of stamps required for one redemption |
| `PORT`             | `8000`                             | gunicorn bind port                           |

## License

MIT
