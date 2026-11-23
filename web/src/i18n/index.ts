import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import uz from "./locales/uz.json";
import ru from "./locales/ru.json";
import en from "./locales/en.json";

export const LANGS = [
  { code: "uz", label: "O'zbek" },
  { code: "ru", label: "Русский" },
  { code: "en", label: "English" },
] as const;

function stored(): string {
  try {
    return localStorage.getItem("clpe.lang") || "uz";
  } catch {
    return "uz";
  }
}

i18n.use(initReactI18next).init({
  resources: { uz: { translation: uz }, ru: { translation: ru }, en: { translation: en } },
  lng: stored(),
  fallbackLng: "uz",
  interpolation: { escapeValue: false },
});

i18n.on("languageChanged", (l) => {
  try {
    localStorage.setItem("clpe.lang", l);
  } catch {
    /* ignore */
  }
  document.documentElement.lang = l;
});

export default i18n;
