import { useState } from "react";
import { useTranslation } from "react-i18next";
import PageShell from "../components/PageShell";
import api from "../lib/api";

export default function Settings() {
  const { t } = useTranslation();
  const [currentPasscode, setCurrentPasscode] = useState("");
  const [newPasscode, setNewPasscode] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    try {
      await api.put("/auth/change-passcode", {
        current_passcode: currentPasscode,
        new_passcode: newPasscode,
      });
      setMessage(t("settings.changePasscode.success"));
      setCurrentPasscode("");
      setNewPasscode("");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? t("settings.changePasscode.genericError"));
    }
  }

  return (
    <PageShell title={t("nav.settings")}>
      <div className="max-w-sm rounded bg-slate-900 p-4">
        <h2 className="mb-3 font-semibold text-saffron">{t("settings.changePasscode.title")}</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            required type="password" placeholder={t("settings.changePasscode.current")} value={currentPasscode}
            onChange={(e) => setCurrentPasscode(e.target.value)}
            className="w-full rounded bg-slate-800 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-saffron"
          />
          <input
            required type="password" placeholder={t("auth.signUp.passcodePlaceholder")} value={newPasscode}
            onChange={(e) => setNewPasscode(e.target.value)}
            className="w-full rounded bg-slate-800 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-saffron"
          />
          {error && <p className="text-sm text-red-400">{error}</p>}
          {message && <p className="text-sm text-indiagreen">{message}</p>}
          <button type="submit" className="rounded bg-saffron px-4 py-2 text-sm font-semibold text-slate-950">
            {t("settings.changePasscode.submit")}
          </button>
        </form>
      </div>

      <p className="mt-4 max-w-sm text-xs text-slate-500">{t("stub.settings.body")}</p>
    </PageShell>
  );
}
