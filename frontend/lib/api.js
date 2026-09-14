// Relative by default: goes through the /api/* rewrite in next.config.js (proxied server-side
// to the FastAPI backend), so the browser never needs a direct route to the backend's port.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

async function handleResponse(res) {
  if (!res.ok) {
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
  return handleResponse(res);
}

export async function analytics(token, days = 30) {
  const res = await fetch(`${API_URL}/admin/analytics?days=${days}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse(res);
}
