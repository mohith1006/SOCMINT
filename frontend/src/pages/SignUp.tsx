import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import api from "../lib/api";
import LanguageSwitcher from "../components/LanguageSwitcher";

export default function SignUp() {
  const { t } = useTranslation();
  const [form, setForm] = useState({
    email: "", full_name: "", organisation: "", phone_number: "", passcode: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const FIELD_LABELS: Record<string, string> = {
    email: t("auth.signUp.email"),
    full_name: t("auth.signUp.fullName"),
    organisation: t("auth.signUp.organisation"),
    phone_number: t("auth.signUp.phoneNumber"),
  };

  const FIELD_TYPES: Record<string, string> = {
    email: "email",
    full_name: "text",
    organisation: "text",
    phone_number: "tel",
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/auth/signup", form);
      setSubmitted(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? t("auth.signUp.genericError"));
    }
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="max-w-md text-center space-y-3">
          <h1 className="text-xl font-semibold">{t("auth.signUp.submittedTitle")}</h1>
          <p className="text-slate-400">{t("auth.signUp.submittedBody")}</p>
          <Link to="/login" className="text-saffron underline">{t("auth.signUp.backToSignIn")}</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4 bg-slate-900 p-6 rounded-lg">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-saffron">{t("auth.signUp.title")}</h1>
          <LanguageSwitcher />
        </div>
        <p className="text-xs text-slate-400">{t("auth.signUp.hint")}</p>

        {(["email", "full_name", "organisation", "phone_number"] as const).map((field) => (
          <input
            key={field}
            required
            type={FIELD_TYPES[field]}
            placeholder={FIELD_LABELS[field]}
            value={(form as any)[field]}
            onChange={(e) => setForm({ ...form, [field]: e.target.value })}
            className="w-full rounded bg-slate-800 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-saffron"
          />
        ))}
        <input
          required
          type="password"
          placeholder={t("auth.signUp.passcodePlaceholder")}
          value={form.passcode}
          onChange={(e) => setForm({ ...form, passcode: e.target.value })}
          className="w-full rounded bg-slate-800 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-saffron"
        />

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button type="submit" className="w-full rounded bg-saffron py-2 text-sm font-semibold text-slate-950">
          {t("auth.signUp.submit")}
        </button>
        <p className="text-xs text-slate-400 text-center">
          {t("auth.signUp.alreadyApproved")}{" "}
          <Link to="/login" className="text-saffron underline">{t("auth.signUp.signIn")}</Link>
        </p>
      </form>
    </div>
  );
}
