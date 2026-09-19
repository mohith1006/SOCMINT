import { useTranslation } from "react-i18next";
import { SUPPORTED_LANGUAGES } from "../i18n";

export default function LanguageSwitcher({ className = "" }: { className?: string }) {
  const { i18n } = useTranslation();

  return (
    <select
      aria-label={SUPPORTED_LANGUAGES.find((l) => l.code === i18n.language)?.label ?? "Language"}
      value={i18n.language}
      onChange={(e) => i18n.changeLanguage(e.target.value)}
      className={`rounded bg-slate-800 px-2 py-1 text-xs text-slate-200 outline-none focus:ring-1 focus:ring-saffron ${className}`}
    >
      {SUPPORTED_LANGUAGES.map((lang) => (
        <option key={lang.code} value={lang.code}>
          {lang.label}
        </option>
      ))}
    </select>
  );
}
