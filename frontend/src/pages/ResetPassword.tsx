import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import api from "../lib/api";
import LanguageSwitcher from "../components/LanguageSwitcher";

export default function ResetPassword() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [newPasscode, setNewPasscode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/auth/reset-password", { token, new_passcode: newPasscode });
      setDone(true);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? t("auth.resetPassword.genericError"));
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-full max-w-sm space-y-4 bg-slate-900 p-6 rounded-lg">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-saffron">{t("auth.resetPassword.title")}</h1>
          <LanguageSwitcher />
        </div>

        {!token && <p className="text-sm text-red-400">{t("auth.resetPassword.missingToken")}</p>}

        {done ? (
          <p className="text-sm text-slate-300">{t("auth.resetPassword.done")}</p>
        ) : token && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              required type="password" placeholder={t("auth.signUp.passcodePlaceholder")} value={newPasscode}
              onChange={(e) => setNewPasscode(e.target.value)}
              className="w-full rounded bg-slate-800 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-saffron"
            />
            {error && <p className="text-sm text-red-400">{error}</p>}
            <button type="submit" className="w-full rounded bg-saffron py-2 text-sm font-semibold text-slate-950">
              {t("auth.resetPassword.submit")}
            </button>
          </form>
        )}
        <p className="text-xs text-slate-400 text-center">
          <Link to="/login" className="text-saffron underline">{t("auth.signUp.backToSignIn")}</Link>
        </p>
      </div>
    </div>
  );
}
