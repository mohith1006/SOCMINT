import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import PageShell from "../components/PageShell";
import api from "../lib/api";

type DashboardSummary = {
  post_count: number;
  synthetic_post_count: number;
  live_post_count: number;
  active_trends_count: number;
  ledger: { valid: boolean; brokenAtIndex: number | null; block_count: number };
  user_count?: number;
  pending_approval_count?: number;
};

function StatCard({ label, value, accent, footer }: { label: string; value: React.ReactNode; accent?: "ok" | "warn"; footer?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${accent === "warn" ? "text-red-400" : accent === "ok" ? "text-emerald-400" : "text-slate-100"}`}>
        {value}
      </div>
      {footer && <div className="mt-1 text-xs text-slate-500">{footer}</div>}
    </div>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.get<DashboardSummary>("/dashboard/summary")
      .then(({ data }) => setSummary(data))
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <PageShell title={t("nav.dashboard")}>
        <p className="text-sm text-red-400">{t("dashboard.loadError")}</p>
      </PageShell>
    );
  }

  if (!summary) {
    return (
      <PageShell title={t("nav.dashboard")}>
        <p className="text-sm text-slate-500">{t("dashboard.loading")}</p>
      </PageShell>
    );
  }

  return (
    <PageShell title={t("nav.dashboard")}>
      <p className="mb-4 text-sm text-slate-400">{t("dashboard.subtitle")}</p>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <StatCard
          label={t("dashboard.totalPosts")}
          value={summary.post_count}
          footer={`${summary.live_post_count} ${t("dashboard.livePosts").toLowerCase()} · ${summary.synthetic_post_count} ${t("dashboard.syntheticPosts").toLowerCase()}`}
        />
        <StatCard label={t("dashboard.activeTrends")} value={summary.active_trends_count} />
        <Link to="/ledger" className="block">
          <StatCard
            label={t("dashboard.ledgerStatus")}
            value={summary.ledger.valid ? "✓" : "✗"}
            accent={summary.ledger.valid ? "ok" : "warn"}
            footer={
              summary.ledger.valid
                ? `${t("dashboard.ledgerValid")} · ${t("dashboard.blockCount", { count: summary.ledger.block_count })}`
                : t("dashboard.ledgerBroken", { index: summary.ledger.brokenAtIndex })
            }
          />
        </Link>
        {summary.user_count !== undefined && (
          <StatCard label={t("dashboard.totalUsers")} value={summary.user_count} />
        )}
        {summary.pending_approval_count !== undefined && (
          <Link to="/admin" className="block">
            <StatCard
              label={t("dashboard.pendingApprovals")}
              value={summary.pending_approval_count}
              accent={summary.pending_approval_count > 0 ? "warn" : undefined}
            />
          </Link>
        )}
      </div>
    </PageShell>
  );
}
