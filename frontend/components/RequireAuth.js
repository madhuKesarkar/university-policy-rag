"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../lib/auth";

/** Wrap a protected page's content. Redirects to /login if not authenticated, and (when
 * `role` is given) to /chat if the logged-in user doesn't have that role — e.g. a student
 * hitting /admin directly gets bounced, not shown a broken/empty dashboard. */
export default function RequireAuth({ role, children }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
    } else if (role && user.role !== role) {
      router.replace("/chat");
    }
  }, [user, loading, role, router]);

  if (loading || !user || (role && user.role !== role)) {
    return <div className="page-loading">Loading…</div>;
  }
  return children;
}
