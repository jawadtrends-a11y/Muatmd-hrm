"use client";
/**
 * مراجعة التواجد (ق-144).
 *
 * ⚠️⚠️ **والخصم يُقترَح ولا يقع** — فساعة البريك مرنة، والموارد
 * تعتمد أو تترك.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "مراجعة التواجد", en: "Presence review" },
  sub: {
    ar: "ما تجاوز التسامح — والخصم قرارك لا حكم النظام",
    en: "Beyond tolerance — the deduction is your call",
  },
  pending: { ar: "بانتظار المراجعة", en: "To review" },
  all: { ar: "الكل", en: "All" },
  day: { ar: "اليوم", en: "Day" },
  employee: { ar: "الموظف", en: "Employee" },
  inside: { ar: "داخل", en: "Inside" },
  outside: { ar: "خارج", en: "Outside" },
  deductible: { ar: "بعد التسامح", en: "After tolerance" },
  suggested: { ar: "المقترَح", en: "Suggested" },
  state: { ar: "القرار", en: "Decision" },
  review: { ar: "مراجعة", en: "Review" },
  min: { ar: "د", en: "m" },
  empty: { ar: "لا شيء ينتظر", en: "Nothing pending" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "التتبّع غير متاح في باقتكم", en: "Not in your plan" },
  reviewTitle: { ar: "قرار الخصم", en: "Deduction decision" },
  approved: { ar: "المبلغ المعتمَد", en: "Approved amount" },
  noDeduct: { ar: "بلا خصم", en: "No deduction" },
  takeSuggested: { ar: "اعتماد المقترَح", en: "Use suggested" },
  note: { ar: "ملاحظة", en: "Note" },
  confirm: { ar: "اعتماد", en: "Confirm" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  doneOk: { ar: "سُجّل القرار", en: "Recorded" },
  deducted: { ar: "خُصم", en: "Deducted" },
  waived: { ar: "أُعفي", en: "Waived" },
};

type Day = {
  id: number; work_date: string; employee: string; employee_no: string;
  inside_minutes: number; outside_minutes: number;
  no_signal_minutes: number; deductible_minutes: number;
  suggested_amount: string | null;
  is_reviewed: boolean; approved_amount: string | null;
  review_note: string; is_applied: boolean;
};

export default function PresencePage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Day[]>([]);
  const [warning, setWarning] = useState("");
  const [onlyPending, setOnlyPending] = useState(true);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [reviewing, setReviewing] = useState<Day | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ days: Day[]; warning: string }>(
        `/presence/?pending=${onlyPending ? "1" : "0"}`);
      setRows(d.days);
      setWarning(d.warning);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [onlyPending]);

  useEffect(() => { load(); }, [load]);

  if (busy) return (
    <div className="card" style={{ padding: 40, textAlign: "center",
                                   color: "var(--ink-3)" }}>{L("loading")}</div>
  );

  if (denied) return (
    <div className="card" style={{ padding: 36, textAlign: "center",
                                   color: "var(--ink-3)" }}>
      <IcAlert size={22} />
      <div style={{ marginTop: 8 }}>{L("noAccess")}</div>
    </div>
  );

  return (
    <div className="stack">
      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("sub")}
        </div>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="row" style={{ gap: 6 }}>
        <button className={`btn btn-sm ${onlyPending ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyPending(true)}>{L("pending")}</button>
        <button className={`btn btn-sm ${!onlyPending ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyPending(false)}>{L("all")}</button>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>
            <IcDoc size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 115 }}>{L("day")}</th>
                  <th>{L("employee")}</th>
                  <th style={{ width: 95 }}>{L("inside")}</th>
                  <th style={{ width: 95 }}>{L("outside")}</th>
                  <th style={{ width: 110 }}>{L("deductible")}</th>
                  <th style={{ width: 110 }}>{L("suggested")}</th>
                  <th style={{ width: 130 }}>{L("state")}</th>
                  <th style={{ width: 90 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.id}>
                    <td><span className="num">{d.work_date}</span></td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{d.employee}</div>
                      <div className="muted num"
                           style={{ fontSize: ".74rem" }}>
                        {d.employee_no}
                      </div>
                    </td>
                    <td>
                      <span className="num">{d.inside_minutes}</span>
                      <span className="muted"> {L("min")}</span>
                    </td>
                    <td>
                      <span className="num">{d.outside_minutes}</span>
                      <span className="muted"> {L("min")}</span>
                    </td>
                    <td>
                      <span className="num"
                            style={{ color: d.deductible_minutes
                              ? "var(--copper)" : undefined }}>
                        {d.deductible_minutes}
                      </span>
                      <span className="muted"> {L("min")}</span>
                    </td>
                    <td>
                      {d.suggested_amount
                        && d.suggested_amount !== "0.00" ? (
                        <span className="num">{d.suggested_amount}</span>
                      ) : <span className="muted">—</span>}
                    </td>
                    <td>
                      {d.is_reviewed ? (
                        Number(d.approved_amount || 0) > 0 ? (
                          <span className="badge badge-warn">
                            {L("deducted")} — {d.approved_amount}
                          </span>
                        ) : (
                          <span className="badge badge-ok">
                            {L("waived")}
                          </span>
                        )
                      ) : (
                        <span className="muted"
                              style={{ fontSize: ".82rem" }}>—</span>
                      )}
                    </td>
                    <td>
                      {!d.is_reviewed && (
                        <button className="btn btn-sm btn-primary"
                                onClick={() => setReviewing(d)}>
                          {L("review")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {reviewing && (
        <ReviewDialog d={reviewing} warning={warning} L={L}
                      onClose={() => setReviewing(null)}
                      onSaved={async () => {
                        setReviewing(null);
                        setMsg(L("doneOk"));
                        setTimeout(() => setMsg(""), 3000);
                        await load();
                      }} />
      )}
    </div>
  );
}


function ReviewDialog({ d, warning, L, onClose, onSaved }: {
  d: Day;
  warning: string;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [amount, setAmount] = useState("0");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost(`/presence/${d.id}/review/`, {
        approved_amount: amount || "0", note,
      });
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose();
    }} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 430,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("reviewTitle")}</h3>
        <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
          {d.employee} — <span className="num">{d.work_date}</span>
        </div>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div style={{ marginTop: 14, padding: "12px 14px",
                      background: "var(--paper-2)",
                      borderRadius: "var(--radius-sm)",
                      fontSize: ".87rem" }}>
          <div className="spread">
            <span className="muted">{L("outside")}</span>
            <span className="num">{d.outside_minutes} {L("min")}</span>
          </div>
          <div className="spread" style={{ marginTop: 5 }}>
            <span className="muted">{L("deductible")}</span>
            <span className="num">{d.deductible_minutes} {L("min")}</span>
          </div>
          <div className="spread" style={{ marginTop: 5,
                                           fontWeight: 600 }}>
            <span>{L("suggested")}</span>
            <span className="num">{d.suggested_amount || "0.00"}</span>
          </div>
        </div>

        {warning && (
          <div style={{ background: "var(--copper-soft)",
                        color: "var(--copper)", padding: "10px 13px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".8rem", lineHeight: 1.8,
                        marginTop: 12 }}>
            {warning}
          </div>
        )}

        <div className="row" style={{ gap: 8, marginTop: 14,
                                      alignItems: "flex-end" }}>
          <label className="field" style={{ width: 160 }}>
            <span className="label">{L("approved")}</span>
            <input className="input num" type="number" min={0} step="0.01"
                   value={amount}
                   onChange={(e) => setAmount(e.target.value)} />
          </label>
          <button className="btn btn-sm" style={{ marginBottom: 2 }}
                  onClick={() => setAmount("0")}>{L("noDeduct")}</button>
          {d.suggested_amount && d.suggested_amount !== "0.00" && (
            <button className="btn btn-sm" style={{ marginBottom: 2 }}
                    onClick={() => setAmount(d.suggested_amount!)}>
              {L("takeSuggested")}
            </button>
          )}
        </div>

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("note")}</span>
          <input className="input" value={note}
                 onChange={(e) => setNote(e.target.value)} />
        </label>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary" disabled={busy}
                  onClick={submit}>{busy ? "…" : L("confirm")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}
