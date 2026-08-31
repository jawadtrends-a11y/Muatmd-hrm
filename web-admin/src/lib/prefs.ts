"use client";

/**
 * تفضيلات المستخدم: اللغة والوضعية.
 *
 * 🔴 درس من المحاسبي: useState يعطي حالة مستقلة لكل مكوّن،
 * فتبديل اللغة يغيّر مكوّنًا واحدًا فقط. الصواب مخزن على
 * مستوى الوحدة + useSyncExternalStore — فكل المكوّنات تشترك.
 */
import { useSyncExternalStore } from "react";

export type Lang = "ar" | "en";
export type Theme = "light" | "dark" | "auto";

export type Prefs = { lang: Lang; theme: Theme };

const KEY = "muatmd_prefs";
const DEFAULTS: Prefs = { lang: "ar", theme: "light" };

// ── المخزن: على مستوى الوحدة لا داخل مكوّن ──
let state: Prefs = DEFAULTS;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((fn) => fn());
}

function persist(next: Prefs) {
  state = next;
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* الوضع الخاص قد يمنع التخزين — لا يوقف التطبيق */
    }
    applyToDocument(next);
  }
  emit();
}

export function applyToDocument(p: Prefs) {
  if (typeof document === "undefined") return;
  const html = document.documentElement;
  html.lang = p.lang;
  html.dir = p.lang === "ar" ? "rtl" : "ltr";

  const dark =
    p.theme === "dark" ||
    (p.theme === "auto" &&
      window.matchMedia?.("(prefers-color-scheme: dark)").matches);
  html.setAttribute("data-theme", dark ? "dark" : "light");
}

export function loadPrefs(): Prefs {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<Prefs>;
      state = {
        lang: parsed.lang === "en" ? "en" : "ar",
        theme:
          parsed.theme === "dark" || parsed.theme === "auto"
            ? parsed.theme
            : "light",
      };
    }
  } catch {
    state = DEFAULTS;
  }
  applyToDocument(state);
  return state;
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function getSnapshot() {
  return state;
}

function getServerSnapshot() {
  return DEFAULTS;
}

export function usePrefs() {
  const prefs = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  return {
    ...prefs,
    isRtl: prefs.lang === "ar",
    setLang: (lang: Lang) => persist({ ...state, lang }),
    setTheme: (theme: Theme) => persist({ ...state, theme }),
    toggleLang: () => persist({ ...state, lang: state.lang === "ar" ? "en" : "ar" }),
  };
}

/**
 * دالة الترجمة.
 *
 * 🚨 النمط المعتمد: كائن T بأزواج {ar, en} في كل شاشة،
 * والأعمدة تُعرَّف داخل المكوّن. أي شاشة جديدة تُبنى
 * بالقاموس من البداية — لا تُترجم لاحقًا.
 *
 *   const T = { save: { ar: "حفظ", en: "Save" } };
 *   const { L } = useT(T);
 *   <button>{L("save")}</button>
 */
export type Dict = Record<string, { ar: string; en: string }>;

export function useT<D extends Dict>(dict: D) {
  const { lang } = usePrefs();
  return {
    lang,
    L: (key: keyof D & string, fallback = ""): string =>
      dict[key]?.[lang] ?? fallback ?? key,
  };
}
