import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import PageShell from "../components/PageShell";
import api from "../lib/api";

type PendingUser = { id: string; email: string; created_at: string };

export default function AdminApprovals() {
  const { t } = useTranslation();
  const [pending, setPending] = useState<PendingUser[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const { data } = await api.get<PendingUser[]>("/admin/pending-users");
      setPending(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? t("admin.loadError"));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function approve(id: string) {
    await api.post(`/admin/pending-users/${id}/approve`);
    load();
  }

  async function reject(id: string) {
    const reason = window.prompt(t("admin.rejectPrompt")) ?? undefined;
    await api.post(`/admin/pending-users/${id}/reject`, { reason });
    load();
  }

  return (
    <PageShell title={t("admin.title")}>
      {error && <p className="text-sm text-red-400 mb-4">{error}</p>}
      <div className="space-y-2">
        {pending.length === 0 && !error && (
          <p className="text-slate-400 text-sm">{t("admin.noPending")}</p>
        )}
        {pending.map((u) => (
          <div key={u.id} className="flex items-center justify-between bg-slate-900 rounded p-3">
            <div>
              <div className="text-sm">{u.email}</div>
              <div className="text-xs text-slate-500">{t("admin.requested")} {new Date(u.created_at).toLocaleString()}</div>
            </div>
            <div className="space-x-2">
              <button onClick={() => approve(u.id)} className="rounded bg-indiagreen px-3 py-1 text-xs font-semibold">
                {t("admin.approve")}
              </button>
              <button onClick={() => reject(u.id)} className="rounded bg-red-800 px-3 py-1 text-xs font-semibold">
                {t("admin.reject")}
              </button>
            </div>
          </div>
        ))}
      </div>
    </PageShell>
  );
}
