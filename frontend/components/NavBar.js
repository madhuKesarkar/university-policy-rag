"use client";
import Link from "next/link";
import { useAuth } from "../lib/auth";

export default function NavBar() {
  const { user, logout } = useAuth();

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link href="/chat" className="brand">
          University Policy Assistant
        </Link>
        {user && (
          <nav className="nav-links">
            <Link href="/chat">Ask a question</Link>
            {user.role === "admin" && <Link href="/admin">Dashboard</Link>}
            <span className="nav-user">
              {user.full_name} <span className="role-badge">{user.role}</span>
            </span>
            <button className="link-button" onClick={logout}>
              Log out
            </button>
          </nav>
        )}
      </div>
    </header>
  );
}
