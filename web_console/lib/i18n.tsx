"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Language = "zh" | "en";

export const LANGUAGE_STORAGE_KEY = "ops_console_lang";

type I18nContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (zhText: string, enText: string) => string;
};

const I18nContext = createContext<I18nContextValue>({
  language: "zh",
  setLanguage: () => {},
  t: (zhText) => zhText
});

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>("zh");

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
      if (stored === "zh" || stored === "en") {
        setLanguageState(stored);
      }
    } catch {
      // ignore localStorage access failure in restricted environments
    }
  }, []);

  const setLanguage = (nextLanguage: Language) => {
    setLanguageState(nextLanguage);
    try {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
    } catch {
      // ignore localStorage access failure in restricted environments
    }
  };

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      setLanguage,
      t: (zhText, enText) => (language === "en" ? enText : zhText)
    }),
    [language]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
