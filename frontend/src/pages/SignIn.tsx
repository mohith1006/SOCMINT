import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import api from "../lib/api";
import LanguageSwitcher from "../components/LanguageSwitcher";

type Stage = "credentials" | "mfa";

export default function SignIn() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [stage, setStage] = useState<Stage>("credentials");
  const [email, setEmail] = useState("");
  const [passcode, setPasscode] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [challengeToken, setChallengeToken] = useState("");
  const [qr, setQr] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submitCredentials(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const { data } = await api.post("/auth/login", { email, passcode });
      setChallengeToken(data.mfa_challenge_token);
      setQr(data.provisioning_qr_png_b64 ?? null);
      setStage("mfa");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? t("auth.signIn.invalidCredentials"));
    }
  }

  async function submitMfa(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const { data } = await api.post("/auth/mfa/verify", {
        mfa_challenge_token: challengeToken,
        totp_code: totpCode,
      });
      localStorage.setItem("socmint_access_token", data.access_token);
      localStorage.setItem("socmint_refresh_token", data.refresh_token);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? t("auth.signIn.invalidMfa"));
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-full max-w-sm space-y-4 bg-slate-900 p-6 rounded-lg">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-saffron">{t("auth.signIn.title")}</h1>
          <LanguageSwitcher />
        </div>

        {stage === "credentials" && (
          <form onSubmit={submitCredentials} className="space-y-4">
            <input
              required type="email" placeholder={t("auth.signIn.email")} value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded bg-slate-800 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-saffron"
            />
            <input
              required type="password" placeholder={t("auth.signIn.passcode")} value={passcode}
              onChange={(e) => setPasscode(e.target.value)}
              className="w-full rounded bg-slate-800 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-saffron"
            />
            {error && <p className="text-sm text-red-400">{error}</p>}
            <button type="submit" className="w-full rounded bg-saffron py-2 text-sm font-semibold text-slate-950">
              {t("auth.signIn.continue")}
            </button>
            <p className="text-xs text-slate-400 text-center">
              <Link to="/forgot-password" className="text-saffron underline">{t("auth.signIn.forgotPasscode")}</Link>
            </p>
            <p className="text-xs text-slate-400 text-center">
              {t("auth.signIn.noAccount")}{" "}
              <Link to="/signup" className="text-saffron underline">{t("auth.signIn.requestOne")}</Link>
            </p>
          </form>
        )}

        {stage === "mfa" && (
          <form onSubmit={submitMfa} className="space-y-4">
            {qr && (
              <div className="text-center space-y-2">
                <p className="text-xs text-slate-400">{t("auth.signIn.mfaScanHint")}</p>
                <img
                  src={`data:image/png;base64,${qr}`}
                  alt="TOTP enrollment QR code"
                  className="mx-auto rounded bg-white p-2"
                  width={160} height={160}
                />
              </div>
            )}
            <input
              required placeholder={t("auth.signIn.mfaCodePlaceholder")} value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              className="w-full rounded bg-slate-800 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-saffron"
            />
            {error && <p className="text-sm text-red-400">{error}</p>}
            <button type="submit" className="w-full rounded bg-saffron py-2 text-sm font-semibold text-slate-950">
              {t("auth.signIn.verifyAndSignIn")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
