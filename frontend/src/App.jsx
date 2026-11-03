import { useEffect, useState } from "react";
import { api } from "./api.js";

function AuthForm({ onToken }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      const { access_token } = await api[mode]({ email, password });
      onToken(access_token);
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };

  return (
    <main className="auth">
      <h1>Site Preview Vault</h1>
      <p className="sub">Save a link. Keep a picture of it.</p>
      <form onSubmit={submit}>
        <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label>Password<input type="password" minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        {err && <div className="err">{err}</div>}
        <button disabled={busy}>{busy ? "…" : mode === "login" ? "Log in" : "Create account"}</button>
      </form>
      <button className="link" onClick={() => { setMode(mode === "login" ? "signup" : "login"); setErr(""); }}>
        {mode === "login" ? "No account? Sign up" : "Have an account? Log in"}
      </button>
    </main>
  );
}

function Dashboard({ token, onLogout }) {
  const [url, setUrl] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const load = () => api.list(token).then(setItems).catch((e) => e.status === 401 ? onLogout() : setErr(e.message));
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setLoading(true);
    try {
      const item = await api.add(token, url.trim());
      setItems([item, ...items]);
      setUrl("");
    } catch (e) { e.status === 401 ? onLogout() : setErr(e.message); }
    setLoading(false);
  };

  const del = async (id) => { await api.remove(token, id); setItems(items.filter((i) => i.id !== id)); };

  return (
    <main className="dash">
      <header><h1>Site Preview Vault</h1><button className="link" onClick={onLogout}>Log out</button></header>
      <form className="add" onSubmit={submit}>
        <input type="url" placeholder="https://example.com" value={url} onChange={(e) => setUrl(e.target.value)} required />
        <button disabled={loading}>{loading ? "Capturing…" : "Preview & save"}</button>
      </form>
      {loading && <p className="sub">Rendering the page in a browser. This can take up to 30 seconds.</p>}
      {err && <div className="err">{err}</div>}
      <section className="grid">
        {items.map((i) => (
          <article key={i.id} className="card">
            {i.preview ? <img src={i.preview} alt={`Preview of ${i.title || i.url}`} loading="lazy" />
                       : <div className="noimg">No preview available</div>}
            <div className="meta">
              <strong>{i.title || "Untitled page"}</strong>
              <a href={i.url} target="_blank" rel="noreferrer">{i.url}</a>
              <small>{new Date(i.created_at).toLocaleString()}</small>
              <button className="link danger" onClick={() => del(i.id)}>Delete</button>
            </div>
          </article>
        ))}
      </section>
      {!items.length && !loading && <p className="sub">Nothing saved yet. Paste a URL above.</p>}
    </main>
  );
}

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("token"));
  const set = (t) => { t ? sessionStorage.setItem("token", t) : sessionStorage.removeItem("token"); setToken(t); };
  return token ? <Dashboard token={token} onLogout={() => set(null)} /> : <AuthForm onToken={set} />;
}
