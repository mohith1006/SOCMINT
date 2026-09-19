import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import PageShell from "../components/PageShell";
import api from "../lib/api";

type SeriesRow = { date: string; emotion_bucket: string; count: number };
type TimelinePayload = { mode: string; series: SeriesRow[] };

const BUCKET_COLORS: Record<string, string> = {
  happy: "#FFC15E",
  joyful: "#138808",
  sad: "#3B82F6",
  angry: "#EF4444",
  low_mood_distress_signal: "#8B5CF6",
};
const BUCKET_ORDER = ["happy", "joyful", "sad", "angry", "low_mood_distress_signal"];

function pivot(series: SeriesRow[]) {
  const byDate: Record<string, any> = {};
  for (const row of series) {
    byDate[row.date] ??= { date: row.date };
    byDate[row.date][row.emotion_bucket] = row.count;
  }
  return Object.values(byDate).sort((a: any, b: any) => a.date.localeCompare(b.date));
}

export default function SentimentTimeline() {
  const { t } = useTranslation();
  const [payload, setPayload] = useState<TimelinePayload | null>(null);
  const [region, setRegion] = useState<string>("");
  const [processing, setProcessing] = useState(false);
  const [canProcess, setCanProcess] = useState(false);

  async function load() {
    const params: Record<string, string> = {};
    if (region) params.region_tag = region;
    const { data } = await api.get<TimelinePayload>("/sentiment/timeline", { params });
    setPayload(data);
  }

  useEffect(() => {
    load();
    api.get("/auth/me").then(({ data }) => {
      setCanProcess(["admin", "analyst", "investigator"].includes(data.role));
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [region]);

  async function runProcessing() {
    setProcessing(true);
    try {
      await api.post("/nlp/process", null, { params: { limit: 200 } });
      await load();
    } finally {
      setProcessing(false);
    }
  }

  const chartData = payload ? pivot(payload.series) : [];

  return (
    <PageShell title={t("nav.sentiment")}>
      <div className="mb-3 flex items-center justify-between">
        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-200 outline-none focus:ring-1 focus:ring-saffron"
        >
          <option value="">{t("sentiment.filters.allRegions")}</option>
          <option value="india">{t("sentiment.filters.india")}</option>
          <option value="unclassified">{t("sentiment.filters.unclassified")}</option>
        </select>

        {canProcess && (
          <button
            onClick={runProcessing}
            disabled={processing}
            className="rounded bg-saffron px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
          >
            {processing ? t("sentiment.processing") : t("sentiment.runProcessing")}
          </button>
        )}
      </div>

      {chartData.length === 0 ? (
        <p className="text-slate-400 text-sm">{t("sentiment.emptyState")}</p>
      ) : (
        <div className="h-96 rounded bg-slate-900 p-4">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94A3B8" }} />
              <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} allowDecimals={false} />
              <Tooltip contentStyle={{ backgroundColor: "#0F172A", border: "1px solid #1E293B", fontSize: 12 }} />
              <Legend
                formatter={(value: string) => t(`sentiment.buckets.${value}`)}
                wrapperStyle={{ fontSize: 11 }}
              />
              {BUCKET_ORDER.map((bucket) => (
                <Bar key={bucket} dataKey={bucket} stackId="emotions" fill={BUCKET_COLORS[bucket]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <p className="mt-3 text-xs text-slate-500">{t("sentiment.sarcasmNote")}</p>
    </PageShell>
  );
}
