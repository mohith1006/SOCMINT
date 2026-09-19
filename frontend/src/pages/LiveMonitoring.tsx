import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import PageShell from "../components/PageShell";
import api from "../lib/api";

export default function LiveMonitoring() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    api.get("/live/status").then(({ data }) => setStatus(data));
  }, []);

  return (
    <PageShell title={t("nav.live")}>
      <div className="mb-3 inline-block rounded bg-amber-900/40 px-3 py-1 text-xs text-amber-300">
        {t("stub.live.modeLabel")}: {status?.mode ?? "..."} — {t("stub.live.modeNote")}
      </div>
      <p className="text-slate-400 text-sm">{t("stub.live.body")}</p>
    </PageShell>
  );
}
