import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import PageShell from "../components/PageShell";
import api from "../lib/api";

type AggregateRow = { community_label: string; value: string; pct: number };
type DemographicsPayload = {
  mode: string;
  aggregates: { language: AggregateRow[]; region: AggregateRow[]; age_bracket: AggregateRow[] };
};

const DIMENSIONS = ["language", "region", "age_bracket"] as const;

function DimensionTable({ rows }: { rows: AggregateRow[] }) {
  const { t } = useTranslation();
  if (rows.length === 0) return null;
  return (
    <table className="w-full text-xs">
      <thead className="text-slate-500 text-left">
        <tr>
          <th className="py-1 pr-3">{t("demographics.columns.community")}</th>
          <th className="py-1 pr-3">{t("demographics.columns.value")}</th>
          <th className="py-1">{t("demographics.columns.pct")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-t border-slate-800">
            <td className="py-1 pr-3">{row.community_label}</td>
            <td className="py-1 pr-3">{row.value}</td>
            <td className="py-1">
              <div className="flex items-center gap-2">
                <div className="h-2 rounded bg-saffron" style={{ width: `${Math.max(4, row.pct)}px` }} />
                <span className="text-slate-400">{row.pct}%</span>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Demographics() {
  const { t } = useTranslation();
  const [payload, setPayload] = useState<DemographicsPayload | null>(null);
  const [computing, setComputing] = useState(false);
  const [canCompute, setCanCompute] = useState(false);

  async function load() {
    const { data } = await api.get<DemographicsPayload>("/demographics");
    setPayload(data);
  }

  useEffect(() => {
    load();
    api.get("/auth/me").then(({ data }) => {
      setCanCompute(["admin", "analyst", "investigator"].includes(data.role));
    }).catch(() => {});
  }, []);

  async function runCompute() {
    setComputing(true);
    try {
      await api.post("/demographics/compute");
      await load();
    } finally {
      setComputing(false);
    }
  }

  const hasAnyData = payload
    ? DIMENSIONS.some((dim) => payload.aggregates[dim].length > 0)
    : false;

  return (
    <PageShell title={t("nav.demographics")}>
      <div className="mb-3 flex items-center justify-between">
        <p className="max-w-xl text-xs text-slate-500">{t("demographics.privacyNote")}</p>
        {canCompute && (
          <button
            onClick={runCompute}
            disabled={computing}
            className="shrink-0 rounded bg-saffron px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
          >
            {computing ? t("demographics.computing") : t("demographics.runCompute")}
          </button>
        )}
      </div>

      {!hasAnyData ? (
        <p className="text-slate-400 text-sm">{t("demographics.emptyState")}</p>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {DIMENSIONS.map((dim) => (
            <div key={dim} className="rounded bg-slate-900 p-4">
              <h2 className="mb-3 font-semibold text-saffron">{t(`demographics.dimensions.${dim}`)}</h2>
              {payload!.aggregates[dim].length === 0 ? (
                <p className="text-xs text-slate-500">—</p>
              ) : (
                <DimensionTable rows={payload!.aggregates[dim]} />
              )}
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
}
