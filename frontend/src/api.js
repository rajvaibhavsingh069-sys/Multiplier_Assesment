const call = async (path, { method = "GET", body, token } = {}) => {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", ...(token && { Authorization: `Bearer ${token}` }) },
    body: body && JSON.stringify(body),
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw Object.assign(new Error(typeof d === "string" ? d : "Request failed. Check your input."), { status: res.status });
  }
  return data;
};
export const api = {
  signup: (b) => call("/api/signup", { method: "POST", body: b }),
  login: (b) => call("/api/login", { method: "POST", body: b }),
  list: (t) => call("/api/urls", { token: t }),
  add: (t, url) => call("/api/urls", { method: "POST", body: { url }, token: t }),
  remove: (t, id) => call(`/api/urls/${id}`, { method: "DELETE", token: t }),
};
