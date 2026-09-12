"use client";
/**
 * صرف المخصّصات المعتمدة (ق-134).
 *
 * ⚠️ **القرار هنا لا عند الموظف**: أيُدرج في المسير أم يُصرف
 * خارجه — والمعتمِد أدرى بحال الصرف يومَه.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "صرف المخصّصات", en: "Allowance disbursement" },
  sub: {
    ar: "ما اعتُمد وينتظر الصرف — اختر طريقته",
    en: "Approved claims awaiting disbursement",
  },
  pending: { ar: "بانتظار الصرف", en: "Pending" },
  settled: { ar: "المصروفة", en: "Settled" },
  employee: { ar: "الموظف", en: "Employee" },
  allowance: { ar: "المخصّص", en: "Allowance" },
  date: { ar: "التاريخ", en: "Date" },
  amount: { ar: "المبلغ", en: "Amount" },
  method: { ar: "طريقة الصرف", en: "Method" },
  settle: { ar: "صرف", en: "Settle" },
  inPayroll: { ar: "إدراج في المسير", en: "Add to payroll" },
  outside: { ar: "صُرف خارج المسير", en: "Paid outside" },
  runType: { ar: "المسير", en: "Payroll run" },
  paidOn: { ar: "تاريخ الصرف", en: "Paid on" },
  paidNote: { ar: "ملاحظة", en: "Note" },
  paidNoteHint: {
    ar: "كاش أو حوالة أو غيرها — التوثيق يكفي",
    en: "Cash, transfer or other — a note suffices",
  },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  empty: { ar: "لا مستحقّات تنتظر", en: "Nothing pending" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "المخصّصات غير متاحة في باقتكم", en: "Not in your plan" },
  total: { ar: "الإجمالي", en: "Total" },
  settledOk: { ar: "سُجّل الصرف", en: "Recorded" },
  queued: { ar: "أُدرج في المسير", en: "Queued for payroll" },
  settleTitle: { ar: "طريقة الصرف", en: "Disbursement method" },
};

type Claim = {
  id: number; employment_id: number; employee_no: string;
  employee: string; allowance: string;
  claim_date: string; amount: string;
  method: string; method_label: string;
  payroll_run_type: string; paid_on: string | null;
  is_settled: boolean;
};
type Opt = { value: string; label: string };

export default function ClaimsPage() {
  const { L } = useT(T);
  const [tab, setTab] = useState<"pending" | "settled">("pending");
  const [rows, setRows] = useState<Claim[]>([]);
  const [methods, setMethods] = useState<Opt[]>([]);
  const [runTypes, setRunTypes] = useState<Opt[]>([]);
  const [multi, setMulti] = useState(false);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [settling, setSettling] = useState<Claim | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ claims: Claim[]; methods: Opt[];
                               run_types: Opt[]; multi_payroll: boolean }>(
        `/allowance-claims/?settled=${tab === "settled" ? "1" : "0"}`);
      setRows(d.claims);
      setMethods(d.methods);
      setRunTypes(d.run_types);
      setMulti(d.multi_payroll);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  const total = rows.reduce((s, r) => s + Number(r.amount || 0), 0);

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
        <button className={`btn btn-sm ${tab === "pending" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setTab("pending")}>{L("pending")}</button>
        <button className={`btn btn-sm ${tab === "settled" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setTab("settled")}>{L("settled")}</button>
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
                  <th>{L("employee")}</th>
                  <th style={{ width: 150 }}>{L("allowance")}</th>
                  <th style={{ width: 120 }}>{L("date")}</th>
                  <th style={{ width: 110 }}>{L("amount")}</th>
                  <th style={{ width: 160 }}>{L("method")}</th>
                  <th style={{ width: 90 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{c.employee}</div>
                      <div className="muted num"
                           style={{ fontSize: ".74rem" }}>
                        {c.employee_no}
                      </div>
                    </td>
                    <td className="muted">{c.allowance}</td>
                    <td><span className="num">{c.claim_date}</span></td>
                    <td><span className="num">{c.amount}</span></td>
                    <td>
                      {c.method ? (
                        <span className="badge">
                          {c.method_label}
                          {c.payroll_run_type === "supplementary"
                            && " — إضافي"}
                        </span>
                      ) : (
                        <span className="muted"
                              style={{ fontSize: ".8rem" }}>—</span>
                      )}
                    </td>
                    <td>
                      {!c.is_settled && (
                        <button className="btn btn-sm btn-primary"
                                onClick={() => setSettling(c)}>
                          {L("settle")}
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

      {rows.length > 0 && (
        <div className="muted" style={{ fontSize: ".85rem" }}>
          {L("total")}: <span className="num">{total.toFixed(2)}</span>
        </div>
      )}

      {settling && (
        <SettleDialog c={settling} methods={methods} runTypes={runTypes}
                      multi={multi} L={L}
                      onClose={() => setSettling(null)}
                      onSaved={async (settled) => {
                        setSettling(null);
                        setMsg(settled ? L("settledOk") : L("queued"));
                        setTimeout(() => setMsg(""), 4000);
                        await load();
                      }} />
      )}
    </div>
  );
}


function SettleDialog({ c, methods, runTypes, multi, L, onClose, onSaved }: {
  c: Claim;
  methods: Opt[];
  runTypes: Opt[];
  multi: boolean;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: (settled: boolean) => void;
}) {
  const [method, setMethod] = useState("payroll");
  const [runType, setRunType] = useState("regular");
  const [paidOn, setPaidOn] = useState(
    new Date().toISOString().slice(0, 10));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const out = await apiPost<{ settled: boolean }>(
        `/allowance-claims/${c.id}/settle/`,
        method === "payroll"
          ? { method, payroll_run_type: runType }
          : { method, paid_on: paidOn, paid_note: note });
      onSaved(Boolean(out?.settled));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 430,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("settleTitle")}</h3>
        <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
          {c.employee} — {c.allowance} —{" "}
          <span className="num">{c.amount}</span>
        </div>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="stack" style={{ gap: 12, marginTop: 16 }}>
          <label className="field">
            <span className="label">{L("method")}</span>
            <select className="select" value={method}
                    onChange={(e) => setMethod(e.target.value)}>
              {methods.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </label>

          {method === "payroll" && multi && (
            <label className="field">
              <span className="label">{L("runType")}</span>
              <select className="select" value={runType}
                      onChange={(e) => setRunType(e.target.value)}>
                {runTypes.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </label>
          )}

          {method === "outside" && (
            <>
              <div className="field">
                <label className="label">{L("paidOn")}</label>
                <DateField value={paidOn} onChange={setPaidOn} />
              </div>
              <label className="field">
                <span className="label">{L("paidNote")}</span>
                <input className="input" value={note}
                       onChange={(e) => setNote(e.target.value)} />
                <span className="muted" style={{ fontSize: ".78rem" }}>
                  {L("paidNoteHint")}
                </span>
              </label>
            </>
          )}
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary" disabled={busy}
                  onClick={submit}>{busy ? "…" : L("save")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}
