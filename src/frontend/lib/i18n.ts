"use client";

import { useEffect, useState } from "react";

export type Language = "zh" | "en";

export function useLanguage(): Language {
  const [language, setLanguage] = useState<Language>("zh");
  useEffect(() => {
    const sync = () => setLanguage(localStorage.getItem("crm_language") === "en" ? "en" : "zh");
    sync();
    window.addEventListener("crm-language-change", sync);
    return () => window.removeEventListener("crm-language-change", sync);
  }, []);
  return language;
}
