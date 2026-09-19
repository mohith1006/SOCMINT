import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import PageShell from "../components/PageShell";
import api from "../lib/api";

type Block = {
  index: number; timestamp: string; data_hash: string;
  event_type: string; previous_hash: string; hash: string;
};

export default function Ledger() {
  const { t } = useTranslation();
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{ valid: boolean; brokenAtIndex: number | null } | null>(null);
  const [loading, setLoading] = useState(false);

  const PAGE_SIZE = 50;

  // GET /ledger is paginated (page/page_size) but was never wired past
  // page 1 -- every signup, login, MFA check, and analysis run adds a
  // block, so a real demo session can exceed 50 entries quickly. Without
  // this, older blocks (including genesis) become invisible in the UI
  // with no way to reach them, even though /ledger/verify itself always
  // checks the FULL chain regardless of what's currently displayed here.
  async function loadPage(pageNum: number) {
    const { data } = await api.get<Block[]>("/ledger", { params: { page: pageNum, page_size: PAGE_SIZE } });
    setBlocks((prev) => (pageNum === 1 ? data : [...prev, ...data]));
    setHasMore(data.length === PAGE_SIZE);
    setPage(pageNum);
  }

  async function loadMore() {
    setLoadingMore(true);
    try {
      await loadPage(page + 1);
    } finally {
      setLoadingMore(false);
    }
  }

  useEffect(() => {
    loadPage(1);
  }, []);

  async function verify() {
    setLoading(true);
    setVerifyResult(null);
    try {
      const { data } = await api.get("/ledger/verify");
      setVerifyResult(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageShell title={t("ledger.title")}>
      <button
        onClick={verify}
        disabled={loading}
        className="mb-4 rounded bg-saffron px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
      >
        {loading ? t("ledger.verifying") : t("ledger.verify")}
      </button>

      {verifyResult && (
        <div className={`mb-4 rounded p-3 text-sm ${verifyResult.valid ? "bg-indiagreen/20 text-indiagreen" : "bg-red-900/40 text-red-300"}`}>
          {verifyResult.valid
            ? t("ledger.validMsg")
            : t("ledger.brokenMsg", { index: verifyResult.brokenAtIndex })}
        </div>
      )}

      <table className="w-full text-xs">
        <thead className="text-slate-500 text-left">
          <tr>
            <th className="py-1 pr-4">{t("ledger.columns.index")}</th>
            <th className="py-1 pr-4">{t("ledger.columns.event")}</th>
            <th className="py-1 pr-4">{t("ledger.columns.timestamp")}</th>
            <th className="py-1 pr-4">{t("ledger.columns.hash")}</th>
            <th className="py-1">{t("ledger.columns.prevHash")}</th>
          </tr>
        </thead>
        <tbody className="font-mono">
          {blocks.map((b) => (
            <tr key={b.index} className="border-t border-slate-800">
              <td className="py-1 pr-4">{b.index}</td>
              <td className="py-1 pr-4 text-saffron">{b.event_type}</td>
              <td className="py-1 pr-4 text-slate-400">{new Date(b.timestamp).toLocaleString()}</td>
              <td className="py-1 pr-4 truncate max-w-[160px]" title={b.hash}>{b.hash.slice(0, 16)}…</td>
              <td className="py-1 truncate max-w-[160px]" title={b.previous_hash}>{b.previous_hash.slice(0, 16)}…</td>
            </tr>
          ))}
        </tbody>
      </table>

      {hasMore && (
        <button
          onClick={loadMore}
          disabled={loadingMore}
          className="mt-4 rounded border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
        >
          {loadingMore ? t("ledger.loadingMore") : t("ledger.loadMore")}
        </button>
      )}
    </PageShell>
  );
}
