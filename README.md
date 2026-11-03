# Site Preview Vault

Sign up / log in, submit a website URL, get a visual preview (screenshot), save it, and browse all previously saved URLs with their previews.

**Stack:** React (Vite) · FastAPI · SQLite (SQLAlchemy) · JWT auth · Playwright (headless Chromium) for previews.

## Prerequisites
- Python 3.10+
- Node.js 18+

## Backend setup
```bash
cd backend
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium                         # downloads the headless browser
export SECRET_KEY="change-me"                       # optional; Windows: set SECRET_KEY=change-me
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

## Frontend setup
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 (Vite proxies `/api` and `/screenshots` to port 8000).

## Usage
1. Create an account (signup logs you in automatically) or log in.
2. Paste a URL, e.g. the test URL:
   `https://www.justdial.com/Hyderabad/Dr-Sarita-Rao-Tx-Hospitals-Near-Masjid-Uppal-Bus-Stand-Bharath-Nagar-Colony-Uppal/040PXX40-XX40-231215200040-Y2E1_BZDET`
3. Click **Preview & save**. Capture takes roughly 5-30 s.
4. All saved URLs appear below as cards (newest first); remove one with Delete.

## API
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/signup` | none | `{email, password}` returns JWT |
| POST | `/api/login` | none | `{email, password}` returns JWT |
| POST | `/api/urls` | Bearer | `{url}` renders, saves, returns the record |
| GET | `/api/urls` | Bearer | Current user's saved URLs |
| DELETE | `/api/urls/{id}` | Bearer | Delete one |

## Design notes
- Passwords hashed with salted PBKDF2-SHA256 (200k iterations); JWTs expire after 12 h.
- Each user only sees their own URLs (queries filtered by `user_id`).
- Preview: headless Chromium screenshot stored in `backend/screenshots/`. If a site blocks automated browsers (JustDial may), the backend falls back to the page's `og:image` and title; if that also fails the card shows "No preview available" but the URL is still saved.
- Token is kept in `sessionStorage` (cleared when the tab closes).

## Limitations / next steps
- SQLite and local disk; use Postgres + object storage in production.
- No SSRF protection against private IPs; add a check before exposing publicly.
- Screenshots run inline in the request; use a job queue at scale.
