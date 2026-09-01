"use client";

/**
 * منتقي الجنسية — قائمة قابلة للبحث بالعربي والإنجليزي.
 *
 * **يعرض بلغة الواجهة، ويبحث بكلتيهما** — فمن يكتب "Egypt"
 * أو «مصر» يجد المطلوب.
 *
 * والقيمة رمز ISO من حرفين — معيار عالمي تفهمه الأنظمة
 * الحكومية والبنوك.
 */
import { useEffect, useMemo, useRef, useState } from "react";

import { usePrefs } from "@/lib/prefs";

type Props = {
  value: string;
  onChange: (code: string) => void;
  disabled?: boolean;
  placeholder?: string;
};

/** (الرمز، بالعربي، بالإنجليزي) — مرتّبة بشيوعها في السعودية */
export const NATIONALITIES: [string, string, string][] = [
  ["SA", "السعودية", "Saudi Arabia"],
  ["EG", "مصر", "Egypt"],
  ["IN", "الهند", "India"],
  ["PK", "باكستان", "Pakistan"],
  ["BD", "بنغلاديش", "Bangladesh"],
  ["PH", "الفلبين", "Philippines"],
  ["SD", "السودان", "Sudan"],
  ["YE", "اليمن", "Yemen"],
  ["SY", "سوريا", "Syria"],
  ["JO", "الأردن", "Jordan"],
  ["LB", "لبنان", "Lebanon"],
  ["PS", "فلسطين", "Palestine"],
  ["IQ", "العراق", "Iraq"],
  ["NP", "نيبال", "Nepal"],
  ["LK", "سريلانكا", "Sri Lanka"],
  ["ID", "إندونيسيا", "Indonesia"],
  ["ET", "إثيوبيا", "Ethiopia"],
  ["KE", "كينيا", "Kenya"],
  ["UG", "أوغندا", "Uganda"],
  ["NG", "نيجيريا", "Nigeria"],
  ["MA", "المغرب", "Morocco"],
  ["TN", "تونس", "Tunisia"],
  ["DZ", "الجزائر", "Algeria"],
  ["LY", "ليبيا", "Libya"],
  ["MR", "موريتانيا", "Mauritania"],
  ["SO", "الصومال", "Somalia"],
  ["DJ", "جيبوتي", "Djibouti"],
  ["KM", "جزر القمر", "Comoros"],
  ["TD", "تشاد", "Chad"],
  ["ML", "مالي", "Mali"],
  ["NE", "النيجر", "Niger"],
  ["SN", "السنغال", "Senegal"],
  ["BF", "بوركينا فاسو", "Burkina Faso"],
  ["GH", "غانا", "Ghana"],
  ["CM", "الكاميرون", "Cameroon"],
  ["TZ", "تنزانيا", "Tanzania"],
  ["ER", "إريتريا", "Eritrea"],
  ["AE", "الإمارات", "United Arab Emirates"],
  ["KW", "الكويت", "Kuwait"],
  ["QA", "قطر", "Qatar"],
  ["BH", "البحرين", "Bahrain"],
  ["OM", "عُمان", "Oman"],
  ["TR", "تركيا", "Turkey"],
  ["IR", "إيران", "Iran"],
  ["AF", "أفغانستان", "Afghanistan"],
  ["MY", "ماليزيا", "Malaysia"],
  ["TH", "تايلاند", "Thailand"],
  ["VN", "فيتنام", "Vietnam"],
  ["CN", "الصين", "China"],
  ["KR", "كوريا الجنوبية", "South Korea"],
  ["JP", "اليابان", "Japan"],
  ["GB", "بريطانيا", "United Kingdom"],
  ["US", "الولايات المتحدة", "United States"],
  ["CA", "كندا", "Canada"],
  ["FR", "فرنسا", "France"],
  ["DE", "ألمانيا", "Germany"],
  ["IT", "إيطاليا", "Italy"],
  ["ES", "إسبانيا", "Spain"],
  ["NL", "هولندا", "Netherlands"],
  ["BE", "بلجيكا", "Belgium"],
  ["SE", "السويد", "Sweden"],
  ["RU", "روسيا", "Russia"],
  ["UA", "أوكرانيا", "Ukraine"],
  ["PL", "بولندا", "Poland"],
  ["RO", "رومانيا", "Romania"],
  ["BR", "البرازيل", "Brazil"],
  ["AR", "الأرجنتين", "Argentina"],
  ["MX", "المكسيك", "Mexico"],
  ["AU", "أستراليا", "Australia"],
  ["ZA", "جنوب أفريقيا", "South Africa"],
];

export function nationalityLabel(code: string, lang = "ar"): string {
  const row = NATIONALITIES.find((n) => n[0] === code);
  if (!row) return code || "";
  return lang === "en" ? row[2] : row[1];
}

/** يزيل التشكيل ويوحّد الألف والهاء — فالبحث يتسامح مع الإملاء */
function normalize(s: string): string {
  return s
    .toLowerCase()
    .replace(/[\u064B-\u065F\u0670]/g, "")
    .replace(/[أإآ]/g, "ا")
    .replace(/ة/g, "ه")
    .replace(/ى/g, "ي")
    .trim();
}


export default function NationalityField({
  value, onChange, disabled, placeholder,
}: Props) {
  const { lang } = usePrefs();
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);

  const selected = NATIONALITIES.find((n) => n[0] === value);
  const label = selected ? (lang === "en" ? selected[2] : selected[1]) : "";

  // البحث بالعربي والإنجليزي معًا — أيًّا كانت لغة الواجهة
  const results = useMemo(() => {
    const q = normalize(query);
    if (!q) return NATIONALITIES;
    return NATIONALITIES.filter(([code, ar, en]) =>
      normalize(ar).includes(q) ||
      normalize(en).includes(q) ||
      code.toLowerCase() === q);
  }, [query]);

  useEffect(() => { setHighlight(0); }, [query]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  function pick(code: string) {
    onChange(code);
    setOpen(false);
    setQuery("");
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "Escape") { setOpen(false); setQuery(""); return; }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(h + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter" && results[highlight]) {
      e.preventDefault();
      pick(results[highlight][0]);
    }
  }

  return (
    <div ref={boxRef} style={{ position: "relative" }}>
      <button
        type="button"
        className="input"
        disabled={disabled}
        onClick={() => !disabled && setOpen((v) => !v)}
        style={{
          width: "100%", textAlign: "start",
          cursor: disabled ? "not-allowed" : "pointer",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          color: label ? "var(--ink)" : "var(--ink-3)",
        }}
      >
        <span>{label || placeholder || "اختر الجنسية"}</span>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2" style={{ opacity: .5 }}>
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div className="card" style={{
          position: "absolute", insetInlineStart: 0, top: "calc(100% + 4px)",
          width: "100%", minWidth: 240, zIndex: 70, padding: 8,
          boxShadow: "var(--shadow-lg)",
        }}>
          <input
            ref={inputRef}
            className="input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKey}
            placeholder={lang === "en" ? "Search…" : "ابحث بالعربي أو الإنجليزي…"}
            style={{ marginBottom: 6 }}
          />

          <div style={{ maxHeight: 260, overflowY: "auto" }}>
            {results.length === 0 ? (
              <div style={{
                padding: 16, textAlign: "center", color: "var(--ink-3)",
                fontSize: ".88rem",
              }}>
                {lang === "en" ? "No results" : "لا نتائج"}
              </div>
            ) : (
              results.map(([code, ar, en], i) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => pick(code)}
                  onMouseEnter={() => setHighlight(i)}
                  style={{
                    display: "flex", width: "100%", alignItems: "center",
                    justifyContent: "space-between", gap: 10,
                    padding: "8px 10px", border: "none",
                    borderRadius: "var(--radius-sm)", font: "inherit",
                    fontSize: ".9rem", cursor: "pointer", textAlign: "start",
                    background: code === value ? "var(--teal)"
                      : i === highlight ? "var(--paper-3)" : "transparent",
                    color: code === value ? "#fff" : "var(--ink)",
                  }}
                >
                  <span>{lang === "en" ? en : ar}</span>
                  <span className="num" style={{
                    fontSize: ".78rem", opacity: .55,
                  }}>
                    {code}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
