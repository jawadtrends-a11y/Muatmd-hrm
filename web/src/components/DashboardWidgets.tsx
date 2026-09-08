"use client";
/**
 * ودجتات اللوحة (ق-106) — عرضٌ موحّد لأنواعها الأربعة.
 *
 * kind: stat (رقم واحد) · stat_list (صفوف) · list_with_count
 * (عدد وقائمة) · bar_list (أشرطة نسبية).
 */
import Link from "next/link";

type Row = { label: string; value: string | number; tone?: string;
             link?: string };
export type Widget = {
  name: string;
  size: "sm" | "md" | "lg";
  kind?: string;
  value?: string | number;
  hint?: string;
  tone?: string;
  count?: number;
  rows?: Row[];
  link?: string;
  empty?: boolean;
  error?: string;
};

const toneColor = (t?: string) =>
  t === "danger" ? "var(--danger)"
  : t === "warn" ? "var(--copper)"
  : t === "ok" ? "var(--ok)"
  : "var(--ink)";

export default function WidgetCard({
  w, arranging = false, onResize,
}: {
  w: Widget;
  arranging?: boolean;
  onResize?: () => void;
}) {
  // العرض يضبطه الأب في وضع الترتيب — فالبطاقة تملأ خانتها.
  return (
    <div className="card" style={{ padding: 18, height: "100%",
                                   position: "relative",
                                   display: "flex", flexDirection: "column" }}>
      <div className="spread" style={{ marginBottom: 12 }}>
        <span style={{ fontWeight: 600, fontSize: ".95rem" }}>{w.name}</span>
        {arranging ? (
          <button className="btn btn-ghost btn-sm"
                  title="تغيير الحجم"
                  onClick={(e) => { e.stopPropagation(); onResize?.(); }}
                  style={{ padding: "2px 8px", fontSize: ".72rem" }}>
            {w.size === "lg" ? "كامل" : w.size === "md" ? "وسط" : "صغير"} ⇄
          </button>
        ) : w.link ? (
          <Link href={w.link} className="muted"
                style={{ fontSize: ".78rem" }}>↗</Link>
        ) : null}
      </div>

      {w.error ? (
        <div className="muted" style={{ fontSize: ".82rem" }}>
          تعذّر عرض هذه البطاقة
        </div>
      ) : w.empty ? (
        <div className="muted" style={{ fontSize: ".85rem" }}>—</div>
      ) : w.kind === "stat" ? (
        <div>
          <div className="num" style={{ fontSize: "2rem", fontWeight: 600,
                                        color: toneColor(w.tone),
                                        lineHeight: 1.1 }}>
            {w.value}
          </div>
          {w.hint && <div className="muted" style={{ fontSize: ".8rem",
                                                     marginTop: 4 }}>
            {w.hint}
          </div>}
        </div>
      ) : w.kind === "stat_list" ? (
        <div style={{ display: "grid", gap: 8 }}>
          {(w.rows || []).map((r, i) => (
            <div key={i} className="spread">
              <span className="muted" style={{ fontSize: ".85rem" }}>
                {r.label}
              </span>
              <span className="num" style={{ fontWeight: 600,
                                             color: toneColor(r.tone) }}>
                {r.value}
              </span>
            </div>
          ))}
        </div>
      ) : w.kind === "list_with_count" ? (
        <div>
          <div className="num" style={{ fontSize: "1.7rem", fontWeight: 600,
                                        color: toneColor(w.tone),
                                        lineHeight: 1.2 }}>
            {w.count ?? 0}
          </div>
          {w.hint && <div className="muted" style={{ fontSize: ".78rem" }}>
            {w.hint}
          </div>}
          <div style={{ marginTop: 10, display: "grid", gap: 6 }}>
            {(w.rows || []).map((r, i) => (
              <div key={i} className="spread" style={{ fontSize: ".84rem" }}>
                <span className="truncate">{r.label}</span>
                <span className="muted truncate"
                      style={{ maxWidth: "50%" }}>{r.value}</span>
              </div>
            ))}
          </div>
        </div>
      ) : w.kind === "bar_list" ? (
        <div style={{ display: "grid", gap: 8 }}>
          {(() => {
            const rows = w.rows || [];
            const max = Math.max(...rows.map((r) => Number(r.value) || 0), 1);
            return rows.map((r, i) => (
              <div key={i}>
                <div className="spread" style={{ fontSize: ".82rem",
                                                 marginBottom: 3 }}>
                  <span className="truncate">{r.label}</span>
                  <span className="num muted">{r.value}</span>
                </div>
                <div style={{ height: 6, background: "var(--paper-3)",
                              borderRadius: 3, overflow: "hidden" }}>
                  <div style={{
                    width: `${((Number(r.value) || 0) / max) * 100}%`,
                    height: "100%", background: "var(--teal)",
                  }} />
                </div>
              </div>
            ));
          })()}
        </div>
      ) : (
        <div className="muted" style={{ fontSize: ".85rem" }}>—</div>
      )}
    </div>
  );
}
