"use client";
/**
 * اختيار موظفٍ باقتراحاتٍ فورية (ق-167).
 *
 * **بلاغ جواد:** لا خيارات بحثٍ وفلترة — **والاقتراحات تظهر بمجرّد
 * إدخال حرفٍ أو رقم**.
 *
 * ⚠️⚠️ **ويحلّ محلّ المنسدلة**: فشركةٌ بألف موظف **لا تُعرض في
 * قائمةٍ واحدة** — والمتصفّح يثقل، والعين تضيع.
 */
import { useEffect, useRef, useState } from "react";

import { apiGet, qs } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import AuthImage from "@/components/AuthImage";

const T: Dict = {
  placeholder: {
    ar: "الاسم / الرقم الوظيفي / رقم الهوية",
    en: "Name / employee no. / ID",
  },
  searching: { ar: "جارٍ البحث…", en: "Searching…" },
  none: { ar: "لا نتائج", en: "No results" },
  hint: { ar: "اكتب حرفًا أو رقمًا للبحث", en: "Type to search" },
  clear: { ar: "مسح", en: "Clear" },
};

export type PickedEmployee = {
  id: number;
  employee_no: string;
  name_ar: string;
  department?: string;
  job_title?: string;
  avatar_url?: string | null;
};

export default function EmployeePicker({
  value, onChange, endpoint = "/employees/", extraQuery, disabled,
}: {
  value?: PickedEmployee | null;
  onChange: (e: PickedEmployee | null) => void;
  /** ق-159: «/me/team/» لشاشات الفريق — فالإسناد لمرؤوسيه */
  endpoint?: string;
  extraQuery?: Record<string, unknown>;
  disabled?: boolean;
}) {
  const { L } = useT(T);
  const [term, setTerm] = useState("");
  const [rows, setRows] = useState<PickedEmployee[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  // ⚠️ **وبمهلةٍ قصيرة**: فطلبٌ مع كل حرفٍ يُثقل الخادم.
  useEffect(() => {
    if (!open) return;
    const q = term.trim();
    if (!q) { setRows([]); return; }

    let alive = true;
    setBusy(true);
    const t = setTimeout(() => {
      apiGet<{ rows?: PickedEmployee[] } | PickedEmployee[]>(
        `${endpoint}${qs({ ...(extraQuery || {}), q, page_size: 8 })}`)
        .then((res) => {
          if (!alive) return;
          setRows(Array.isArray(res) ? res.slice(0, 8)
                                     : (res.rows ?? []));
        })
        .catch(() => alive && setRows([]))
        .finally(() => alive && setBusy(false));
    }, 300);

    return () => { alive = false; clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [term, open, endpoint]);

  // ⚠️ **والنقر خارجه يُغلقه** — فقائمةٌ عالقة تحجب ما تحتها
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const pick = (e: PickedEmployee) => {
    onChange(e);
    setTerm("");
    setOpen(false);
  };

  return (
    <div ref={boxRef} style={{ position: "relative" }}>
      {value ? (
        <div className="row" style={{
          gap: 10, alignItems: "center", padding: "7px 10px",
          border: "1px solid var(--line)",
          borderRadius: "var(--radius-sm)",
          background: "var(--paper)",
        }}>
          <Avatar row={value} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="truncate" style={{ fontWeight: 500 }}>
              {value.name_ar}
            </div>
            <div className="muted num" style={{ fontSize: ".75rem" }}>
              {value.employee_no}
              {value.department ? ` · ${value.department}` : ""}
            </div>
          </div>
          {!disabled && (
            <button type="button" className="btn btn-sm btn-ghost"
                    onClick={() => onChange(null)}>
              {L("clear")}
            </button>
          )}
        </div>
      ) : (
        <input
          className="input"
          disabled={disabled}
          value={term}
          placeholder={L("placeholder")}
          onFocus={() => setOpen(true)}
          onChange={(e) => { setTerm(e.target.value); setOpen(true); }}
        />
      )}

      {open && !value && (
        <div style={{
          position: "absolute", insetInlineStart: 0, insetInlineEnd: 0,
          top: "calc(100% + 4px)", zIndex: 40,
          background: "var(--paper)",
          border: "1px solid var(--line)",
          borderRadius: "var(--radius-sm)",
          boxShadow: "0 8px 24px rgba(16,28,38,.12)",
          maxHeight: 300, overflowY: "auto",
        }}>
          {busy ? (
            <div className="muted" style={{ padding: "12px 14px",
                                            fontSize: ".85rem" }}>
              {L("searching")}
            </div>
          ) : !term.trim() ? (
            <div className="muted" style={{ padding: "12px 14px",
                                            fontSize: ".85rem" }}>
              {L("hint")}
            </div>
          ) : rows.length === 0 ? (
            <div className="muted" style={{ padding: "12px 14px",
                                            fontSize: ".85rem" }}>
              {L("none")}
            </div>
          ) : (
            rows.map((r) => (
              <button key={r.id} type="button"
                      onClick={() => pick(r)}
                      style={{
                        display: "flex", alignItems: "center", gap: 10,
                        width: "100%", padding: "9px 12px",
                        border: "none", background: "transparent",
                        cursor: "pointer", font: "inherit",
                        textAlign: "start",
                        borderBottom: "1px solid var(--line)",
                      }}>
                <Avatar row={r} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="truncate" style={{ fontWeight: 500 }}>
                    {r.name_ar}
                  </div>
                  <div className="muted" style={{ fontSize: ".75rem" }}>
                    <span className="num">{r.employee_no}</span>
                    {r.department ? ` · ${r.department}` : ""}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}


function Avatar({ row }: { row: PickedEmployee }) {
  const initials = String(row.name_ar || "؟").trim().charAt(0);
  return row.avatar_url ? (
    <AuthImage src={String(row.avatar_url)} alt=""
               style={{ width: 34, height: 34, borderRadius: "50%",
                        objectFit: "cover", flexShrink: 0 }} />
  ) : (
    <div style={{
      width: 34, height: 34, borderRadius: "50%", flexShrink: 0,
      background: "var(--teal-soft)", color: "var(--teal)",
      display: "grid", placeItems: "center", fontWeight: 600,
      fontSize: ".9rem",
    }}>
      {initials}
    </div>
  );
}
