// Relative by default: goes through the /api/* rewrite in next.config.js (proxied server-side
// to the FastAPI backend), so the browser never needs a direct route to the backend's port.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

// `authed: true` means this call carries a token that's expected to already be valid — a 401
// there means the token expired (JWTs are set to expire after 2 hours; see backend/app/config.py),
// not "wrong password", so the right move is to clear it and send the user back to log in again
// rather than show a raw "Could not validate credentials" error on whatever page they were on.
// login/register calls must NOT set this — a 401 there is a real "wrong password" the user needs
// to see and correct, not a session expiry.
async function handleResponse(res, { authed = false } = {}) {
  if (!res.ok) {
    if (authed && res.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {
      // response body wasn't JSON; fall back to statusText
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function login(email, password) {
  // OAuth2PasswordRequestForm on the backend expects x-www-form-urlencoded with a
  // "username" field, even though we authenticate by email.
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  return handleResponse(res);
}

export async function register({ email, password, fullName, role, department }) {
  const res = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      full_name: fullName,
      role,
      department: department || null,
    }),
  });
  return handleResponse(res);
}

export async function me(token) {
  // NOT `authed: true` — AuthProvider calls this on every page load (including /login itself)
  // to silently check a stored token. Auto-redirecting on a 401 here would fire on the login
  // page too, before the user has done anything, and risks a reload loop. AuthProvider already
  // handles an invalid/expired stored token correctly on its own (clears it, leaves `user`
  // null, and each protected page's own redirect effect takes it from there).
  const res = await fetch(`${API_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse(res);
}

export async function ask(token, question) {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ question }),
  });
  return handleResponse(res, { authed: true });
}

export async function analytics(token, days = 30) {
  const res = await fetch(`${API_URL}/admin/analytics?days=${days}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse(res, { authed: true });
}
