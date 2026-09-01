"use client";

/**
 * منتقي التاريخ العربي — Custom Date Picker.
 *
 * يستبدل <input type="date"> الأصلي الذي يعرض الصيغة الأمريكية
 * MM/DD/YYYY — والقارئ السعودي يقرأ 08/25/2026 فيظنه اليوم
 * الثامن من الشهر الخامس والعشرين.
 *
 * ═══ العقد ═══
 * value و onChange بصيغة YYYY-MM-DD — نفس العنصر الأصلي تمامًا،
 * فلا يتغيّر شيء بالخادم ولا بمنطق الشاشات. والعرض وحده DD/MM/YYYY.
 */
import { useEffect, useMemo, useRef, useState } from "react";

type Props = {
  value: string;                       // YYYY-MM-DD أو ""
  onChange: (v: string) => void;
  min?: string;
  max?: string;
  disabled?: boolean;
  placeholder?: string;
  style?: React.CSSProperties;
  className?: string;
};

const MONTHS_AR = [
  "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
  "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
];

const DAYS_AR = ["أحد", "إثنين", "ثلاثاء", "أربعاء", "خميس", "جمعة", "سبت"];

/** اليوم بتوقيت المستخدم لا بـUTC — الفرق يعطي تاريخ الأمس فجرًا */
function todayISO(): string {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString().slice(0, 10);
}

function parse(v: string): { y: number; m: number; d: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v || "");
  if (!m) return null;
  return { y: +m[1], m: +m[2], d: +m[3] };
}

function iso(y: number, m: number, d: number): string {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

function display(v: string): string {
  const p = parse(v);
  return p ? `${String(p.d).padStart(2, "0")}/${String(p.m).padStart(2, "0")}/${p.y}` : "";
}

function daysInMonth(y: number, m: number): number {
  return new Date(y, m, 0).getDate();
}

/** أول أيام الشهر — الأحد=0 كما التقويم السعودي */
function firstWeekday(y: number, m: number): number {
  return new Date(y, m - 1, 1).getDay();
}


export default function DateField({
  value, onChange, min, max, disabled, placeholder, style, className,
}: Props) {
  const [open, setOpen] = useState(false);
  const [pickingMonth, setPickingMonth] = useState(false);
  const [flip, setFlip] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  const parsed = parse(value);
  const now = new Date();
  const [viewY, setViewY] = useState(parsed?.y ?? now.getFullYear());
  const [viewM, setViewM] = useState(parsed?.m ?? now.getMonth() + 1);

  // مزامنة العرض مع القيمة الخارجية
  useEffect(() => {
    const p = parse(value);
    if (p) { setViewY(p.y); setViewM(p.m); }
  }, [value]);

  // الإغلاق بالضغط خارجه أو Esc
  useEffect(() => {
    if (!open) return;

    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
        setPickingMonth(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setOpen(false); setPickingMonth(false); }
    };

    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // الانقلاب لأعلى عند حافة الشاشة
  useEffect(() => {
    if (!open || !boxRef.current) return;
    const rect = boxRef.current.getBoundingClientRect();
    setFlip(rect.bottom + 340 > window.innerHeight && rect.top > 340);
  }, [open]);

  const grid = useMemo(() => {
    const total = daysInMonth(viewY, viewM);
    const lead = firstWeekday(viewY, viewM);
    const cells: (number | null)[] = Array(lead).fill(null);
    for (let d = 1; d <= total; d++) cells.push(d);
    while (cells.length % 7 !== 0) cells.push(null);
    return cells;
  }, [viewY, viewM]);

  const today = todayISO();

  const isDisabled = (d: number) => {
    const v = iso(viewY, viewM, d);
    if (min && v < min) return true;
    if (max && v > max) return true;
    return false;
  };

  const move = (delta: number) => {
    let m = viewM + delta;
    let y = viewY;
    if (m < 1) { m = 12; y -= 1; }
    if (m > 12) { m = 1; y += 1; }
    setViewM(m);
    setViewY(y);
  };

  const pick = (d: number) => {
    if (isDisabled(d)) return;
    onChange(iso(viewY, viewM, d));
    setOpen(false);
  };

  return (
    <div ref={boxRef} style={{ position: "relative", ...style }}
      className={className}>
      {/* الحقل */}
      <button
        type="button"
        className="input"
        disabled={disabled}
        onClick={() => !disabled && setOpen((v) => !v)}
        style={{
          width: "100%", textAlign: "start", cursor: disabled
            ? "not-allowed" : "pointer",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          color: value ? "var(--ink)" : "var(--ink-3)",
        }}
      >
        <span className={value ? "num" : ""}>
          {value ? display(value) : (placeholder || "يوم/شهر/سنة")}
        </span>
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"
          style={{ opacity: .6, flexShrink: 0 }}>
          <rect x="3" y="5" width="18" height="16" rx="2" />
          <path d="M16 3v4M8 3v4M3 11h18" />
        </svg>
      </button>

      {/* اللوحة */}
      {open && (
        <div
          className="card"
          style={{
            position: "absolute", insetInlineStart: 0, zIndex: 70,
            width: 290, padding: 12, boxShadow: "var(--shadow-lg)",
            ...(flip ? { bottom: "calc(100% + 6px)" }
                     : { top: "calc(100% + 6px)" }),
          }}
        >
          {pickingMonth ? (
            <MonthYearPicker
              year={viewY} month={viewM}
              onPick={(y, m) => { setViewY(y); setViewM(m); setPickingMonth(false); }}
              onCancel={() => setPickingMonth(false)}
            />
          ) : (
            <>
              {/* الترويسة */}
              <div className="spread" style={{ marginBottom: 10 }}>
                <button type="button" className="btn btn-sm btn-ghost"
                  onClick={() => move(-1)} aria-label="السابق">‹</button>

                <button type="button" className="btn btn-sm btn-ghost"
                  onClick={() => setPickingMonth(true)}
                  style={{ fontWeight: 600 }}>
                  {MONTHS_AR[viewM - 1]} <span className="num">{viewY}</span>
                </button>

                <button type="button" className="btn btn-sm btn-ghost"
                  onClick={() => move(1)} aria-label="التالي">›</button>
              </div>

              {/* أسماء الأيام */}
              <div style={{
                display: "grid", gridTemplateColumns: "repeat(7, 1fr)",
                gap: 2, marginBottom: 4,
              }}>
                {DAYS_AR.map((d) => (
                  <div key={d} style={{
                    textAlign: "center", fontSize: ".72rem",
                    color: "var(--ink-3)", padding: "4px 0",
                  }}>
                    {d}
                  </div>
                ))}
              </div>

              {/* الشبكة */}
              <div style={{
                display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2,
              }}>
                {grid.map((d, i) => {
                  if (d === null) return <div key={i} />;
                  const v = iso(viewY, viewM, d);
                  const selected = v === value;
                  const isToday = v === today;
                  const off = isDisabled(d);
                  const weekend = [5, 6].includes(new Date(viewY, viewM - 1, d).getDay());

                  return (
                    <button
                      key={i}
                      type="button"
                      disabled={off}
                      onClick={() => pick(d)}
                      style={{
                        height: 34, border: "none", borderRadius: "var(--radius-sm)",
                        font: "inherit", fontSize: ".9rem",
                        fontVariantNumeric: "tabular-nums",
                        cursor: off ? "not-allowed" : "pointer",
                        background: selected ? "var(--teal)"
                          : isToday ? "var(--teal-soft)" : "transparent",
                        color: selected ? "#fff"
                          : off ? "var(--ink-3)"
                          : weekend ? "var(--ink-3)" : "var(--ink)",
                        opacity: off ? .4 : 1,
                        fontWeight: selected || isToday ? 600 : 400,
                      }}
                      onMouseEnter={(e) => {
                        if (!off && !selected) {
                          e.currentTarget.style.background = "var(--paper-3)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!selected) {
                          e.currentTarget.style.background =
                            isToday ? "var(--teal-soft)" : "transparent";
                        }
                      }}
                    >
                      {d}
                    </button>
                  );
                })}
              </div>

              {/* الإجراءات */}
              <div className="row" style={{
                marginTop: 10, paddingTop: 10,
                borderTop: "1px solid var(--line)",
              }}>
                <button type="button" className="btn btn-sm btn-ghost"
                  onClick={() => { onChange(today); setOpen(false); }}>
                  اليوم
                </button>
                <div className="grow" />
                <button type="button" className="btn btn-sm btn-ghost"
                  style={{ color: "var(--danger)" }}
                  onClick={() => { onChange(""); setOpen(false); }}>
                  مسح
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* ══ لوحة اختيار الشهر والسنة ══ */

function MonthYearPicker({
  year, month, onPick, onCancel,
}: {
  year: number;
  month: number;
  onPick: (y: number, m: number) => void;
  onCancel: () => void;
}) {
  const [y, setY] = useState(year);

  return (
    <div>
      <div className="spread" style={{ marginBottom: 10 }}>
        <button type="button" className="btn btn-sm btn-ghost"
          onClick={() => setY(y - 1)}>‹</button>
        <strong className="num">{y}</strong>
        <button type="button" className="btn btn-sm btn-ghost"
          onClick={() => setY(y + 1)}>›</button>
      </div>

      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 4,
      }}>
        {MONTHS_AR.map((name, i) => (
          <button
            key={name}
            type="button"
            onClick={() => onPick(y, i + 1)}
            style={{
              padding: "9px 4px", border: "none",
              borderRadius: "var(--radius-sm)", font: "inherit",
              fontSize: ".85rem", cursor: "pointer",
              background: (y === year && i + 1 === month)
                ? "var(--teal)" : "var(--paper-2)",
              color: (y === year && i + 1 === month) ? "#fff" : "var(--ink)",
            }}
          >
            {name}
          </button>
        ))}
      </div>

      <button type="button" className="btn btn-sm btn-ghost"
        style={{ marginTop: 10, width: "100%" }}
        onClick={onCancel}>
        رجوع
      </button>
    </div>
  );
}
