import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import PageShell from "../components/PageShell";
import api from "../lib/api";

type TopicRow = { id: string; label: string; velocity_score: number; first_seen: string };
type TrendsPayload = { mode: string; topics: TopicRow[] };

export default function Trends() {
  const { t } = useTranslation();
  const [payload, setPayload] = useState<TrendsPayload | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [canDetect, setCanDetect] = useState(false);

  async function load() {
    const { data } = await api.get<TrendsPayload>("/trends");
    setPayload(data);
  }

  useEffect(() => {
    load();
    api.get("/auth/me").then(({ data }) => {
      setCanDetect(["admin", "analyst", "investigator"].includes(data.role));
    }).catch(() => {});
  }, []);

  async function runDetection() {
    setDetecting(true);
    try {
      await api.post("/trends/detect");
      await load();
    } finally {
      setDetecting(false);
    }
  }

  const topics = payload?.topics ?? [];
  const maxVelocity = Math.max(1, ...topics.map((topic) => Math.abs(topic.velocity_score)));

  return (
    <PageShell title={t("nav.trends")}>
      {canDetect && (
        <button
          onClick={runDetection}
          disabled={detecting}
          className="mb-4 rounded bg-saffron px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
        >
          {detecting ? t("trends.detecting") : t("trends.runDetection")}
        </button>
      )}

      {topics.length === 0 ? (
        <p className="text-slate-400 text-sm">{t("trends.emptyState")}</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-slate-500 text-left text-xs">
            <tr>
              <th className="py-1 pr-4">{t("trends.columns.topic")}</th>
              <th className="py-1 pr-4">{t("trends.columns.velocity")}</th>
            </tr>
          </thead>
          <tbody>
            {topics.map((topic) => (
              <tr key={topic.id} className="border-t border-slate-800">
                <td className="py-2 pr-4">{topic.label}</td>
                <td className="py-2 pr-4">
                  <div className="flex items-center gap-2">
                    <div className="h-2 rounded bg-saffron" style={{
                      width: `${Math.max(4, (Math.abs(topic.velocity_score) / maxVelocity) * 120)}px`,
                    }} />
                    <span className="text-xs text-slate-400">{topic.velocity_score}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </PageShell>
  );
}
