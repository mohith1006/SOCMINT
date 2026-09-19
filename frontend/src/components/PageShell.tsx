import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import LanguageSwitcher from "./LanguageSwitcher";
import api from "../lib/api";

export default function PageShell({ title, children }: { title: string; children: React.ReactNode }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [role, setRole] = useState<string | null>(null);

  // Every protected page renders through this shell, so fetching the
  // current user's role here (once) rather than per-page is what lets us
  // hide the Admin nav link from non-admins app-wide. Previously every
  // logged-in user saw the link regardless of role -- clicking it as a
  // non-admin hit a real 403 from the backend (no data was ever exposed,
  // RBAC held) but surfaced as a confusing generic error rather than the
  // link simply not being there for someone who could never use it.
  useEffect(() => {
    api.get("/auth/me").then(({ data }) => setRole(data.role)).catch(() => setRole(null));
  }, []);

  const NAV = [
    { to: "/dashboard", label: t("nav.dashboard") },
    { to: "/live", label: t("nav.live") },
    { to: "/network", label: t("nav.network") },
    { to: "/sentiment", label: t("nav.sentiment") },
    { to: "/trends", label: t("nav.trends") },
    { to: "/demographics", label: t("nav.demographics") },
    { to: "/ledger", label: t("nav.ledger") },
    ...(role === "admin" ? [{ to: "/admin", label: t("nav.admin") }] : []),
    { to: "/settings", label: t("nav.settings") },
  ];

  function logout() {
    localStorage.removeItem("socmint_access_token");
    localStorage.removeItem("socmint_refresh_token");
    navigate("/login");
  }

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 shrink-0 border-r border-slate-800 p-4 flex flex-col">
        <div className="mb-4">
          <div className="text-lg font-bold text-saffron">{t("app.name")}</div>
          <div className="text-xs text-slate-400">{t("app.tagline")}</div>
        </div>
        <LanguageSwitcher className="mb-6 w-full" />
        <nav className="flex-1 space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded px-3 py-2 text-sm ${
                  isActive ? "bg-slate-800 text-white" : "text-slate-400 hover:bg-slate-900"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button onClick={logout} className="text-xs text-slate-500 hover:text-slate-300 text-left">
          {t("nav.signOut")}
        </button>
      </aside>
      <main className="flex-1 p-6">
        <h1 className="text-xl font-semibold mb-4">{title}</h1>
        {children}
      </main>
    </div>
  );
}
