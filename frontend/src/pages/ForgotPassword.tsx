import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import api from "../lib/api";
import LanguageSwitcher from "../components/LanguageSwitcher";

export default function ForgotPassword() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/auth/forgot-password", { email });
      setSubmitted(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? t("auth.forgotPassword.genericError"));
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-full max-w-sm space-y-4 bg-slate-900 p-6 rounded-lg">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-saffron">{t("auth.forgotPassword.title")}</h1>
          <LanguageSwitcher />
        </div>

        {submitted ? (
          <div className="space-y-3 text-center">
            <p className="text-sm text-slate-300">{t("auth.forgotPassword.submittedBody")}</p>
            <Link to="/login" className="text-saffron underline text-sm">{t("auth.signUp.backToSignIn")}</Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-xs text-slate-400">{t("auth.forgotPassword.hint")}</p>
            <input
              required type="email" placeholder={t("auth.signIn.email")} value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded bg-slate-800 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-saffron"
            />
            {error && <p className="text-sm text-red-400">{error}</p>}
            <button type="submit" className="w-full rounded bg-saffron py-2 text-sm font-semibold text-slate-950">
              {t("auth.forgotPassword.submit")}
            </button>
            <p className="text-xs text-slate-400 text-center">
              <Link to="/login" className="text-saffron underline">{t("auth.signUp.backToSignIn")}</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
