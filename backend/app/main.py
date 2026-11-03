import hashlib, hmac, os, re, secrets, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import httpx, jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, HttpUrl
from sqlalchemy import DateTime, ForeignKey, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

SECRET = os.getenv("SECRET_KEY", "dev-secret-change-me")
BASE = Path(__file__).resolve().parent.parent
SHOTS = BASE / "screenshots"
SHOTS.mkdir(exist_ok=True)

engine = create_engine(f"sqlite:///{BASE/'app.db'}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)

class SavedUrl(Base):
    __tablename__ = "saved_urls"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    url: Mapped[str] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    preview_path: Mapped[str | None] = mapped_column(String, nullable=True)  # /screenshots/xxx.jpg
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(engine)

app = FastAPI(title="Site Preview API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/screenshots", StaticFiles(directory=SHOTS), name="screenshots")


def get_db():
    with SessionLocal() as db:
        yield db

# ---------- auth helpers ----------
def hash_pw(pw: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${h}"

def verify_pw(pw: str, stored: str) -> bool:
    salt, _ = stored.split("$")
    return hmac.compare_digest(hash_pw(pw, salt), stored)

def make_token(uid: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode({"sub": str(uid), "exp": exp}, SECRET, algorithm="HS256")

bearer = HTTPBearer()
def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    try:
        uid = int(jwt.decode(cred.credentials, SECRET, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "User not found")
    return user

# ---------- schemas ----------
class Creds(BaseModel):
    email: EmailStr
    password: str

class UrlIn(BaseModel):
    url: HttpUrl

# ---------- preview generation ----------
async def take_screenshot(url: str, out: Path) -> str | None:
    """Render the page in headless Chromium. Returns the page title."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        )
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(2500)  # let images/JS settle
            await page.screenshot(path=str(out), type="jpeg", quality=70)
            return await page.title()
        finally:
            await browser.close()

async def og_fallback(url: str, out: Path) -> str | None:
    """If screenshotting is blocked, fall back to the page's og:image + title."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=15,
                                 headers={"User-Agent": "Mozilla/5.0"}) as c:
        html = (await c.get(url)).text
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        img = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
        if img:
            r = await c.get(urljoin(url, img.group(1)))
            if r.status_code == 200:
                out.write_bytes(r.content)
        return title.group(1).strip() if title else None

async def build_preview(url: str) -> tuple[str | None, str | None]:
    name = f"{uuid.uuid4().hex}.jpg"
    out = SHOTS / name
    title = None
    try:
        title = await take_screenshot(url, out)
    except Exception as e:
        print("screenshot failed:", e)
    if not out.exists():
        try:
            title = await og_fallback(url, out) or title
        except Exception as e:
            print("fallback failed:", e)
    return title, (f"/screenshots/{name}" if out.exists() else None)

# ---------- routes ----------
@app.post("/api/signup", status_code=201)
def signup(body: Creds, db: Session = Depends(get_db)):
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    u = User(email=body.email.lower(), password_hash=hash_pw(body.password))
    db.add(u); db.commit()
    return {"access_token": make_token(u.id), "token_type": "bearer"}

@app.post("/api/login")
def login(body: Creds, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if not u or not verify_pw(body.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": make_token(u.id), "token_type": "bearer"}

def ser(s: SavedUrl):
    return {"id": s.id, "url": s.url, "title": s.title, "preview": s.preview_path,
            "created_at": s.created_at.replace(tzinfo=None).isoformat() + "Z"}

@app.post("/api/urls", status_code=201)
async def add_url(body: UrlIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    url = str(body.url)
    title, preview = await build_preview(url)
    s = SavedUrl(user_id=user.id, url=url, title=title, preview_path=preview)
    db.add(s); db.commit()
    return ser(s)

@app.get("/api/urls")
def list_urls(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedUrl).where(SavedUrl.user_id == user.id).order_by(SavedUrl.id.desc()))
    return [ser(r) for r in rows]

@app.delete("/api/urls/{uid}", status_code=204)
def delete_url(uid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(SavedUrl, uid)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(s); db.commit()
