"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { register } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export default function RegisterPage() {
  const { user, loading, login } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/chat");
  }, [user, loading, router]);

  const [form, setForm] = useState({
    fullName: "",
    email: "",
    password: "",
    role: "student",
    department: "",
  });
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(form);
      await login(form.email, form.password);
      router.push("/chat");
    } catch (err) {
      setError(err.message || "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="centered-form-page">
      <div className="card form-card">
        <h1>Create an account</h1>
        <p className="form-subtitle">
          Set up access to the University Policy Assistant.
        </p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="fullName">Full name</label>
          <input id="fullName" required value={form.fullName} onChange={update("fullName")} />

          <label htmlFor="email">Email</label>
          <input id="email" type="email" required value={form.email} onChange={update("email")} />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            required
            minLength={8}
            value={form.password}
            onChange={update("password")}
          />

          <label htmlFor="role">Role</label>
          <select id="role" value={form.role} onChange={update("role")}>
            <option value="student">Student</option>
            <option value="professor">Professor</option>
            <option value="admin">Admin</option>
          </select>
          <div className="form-hint">
            Demo shortcut: a real deployment would assign roles via institutional SSO or an
            admin-only step, not self-registration.
          </div>

          <label htmlFor="department">Department (optional)</label>
          <input id="department" value={form.department} onChange={update("department")} />

          {error && <div className="form-error">{error}</div>}
          <button className="primary" type="submit" disabled={submitting}>
            {submitting ? "Creating account…" : "Create account"}
          </button>
        </form>
        <div className="form-footer">
          Already have an account? <Link href="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
