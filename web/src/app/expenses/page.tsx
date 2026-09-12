"use client";
/**
 * المصروفات (ق-139).
 *
 * ⚠️ **والفاتورة إلزامية** — فالمصروف يُثبَت لا يُدّعى.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, apiUpload, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import AuthImage from "@/components/AuthImage";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "المصروفات", en: "Expenses" },
  sub: {
    ar: "ما دفعتَه لأجل العمل — بفاتورته",
    en: "What you paid for work — with a receipt",
  },
  add: { ar: "مطالبة جديدة", en: "New claim" },
  no: { ar: "الرقم", en: "No." },
  employee: { ar: "الموظف", en: "Employee" },
  category: { ar: "الفئة", en: "Category" },
  spentOn: { ar: "تاريخ الصرف", en: "Spent on" },
  amount: { ar: "المبلغ", en: "Amount" },
  what: { ar: "البيان", en: "Description" },
  receipt: { ar: "الفاتورة", en: "Receipt" },
  receiptHint: {
    ar: "إلزامية — فالمصروف يُثبَت لا يُدّعى",
    en: "Required — expenses are proven, not claimed",
  },
  state: { ar: "الحالة", en: "Status" },
  approve: { ar: "اعتماد", en: "Approve" },
  reject: { ar: "رفض", en: "Reject" },
  settle: { ar: "صرف", en: "Settle" },
  pick: { ar: "اختر صورة", en: "Choose file" },
  uploading: { ar: "جارٍ الرفع…", en: "Uploading…" },
  save: { ar: "إرسال", en: "Send" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  empty: { ar: "لا مطالبات", en: "No claims" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "المصروفات غير متاحة في باقتكم", en: "Not in your plan" },
  newTitle: { ar: "مطالبة مصروف", en: "Expense claim" },
  caps: { ar: "الحدود", en: "Limits" },
  perClaim: { ar: "سقف المطالبة", en: "Per claim" },
  perMonth: { ar: "سقف الشهر", en: "Per month" },
  noCap: { ar: "بلا حدّ", en: "No limit" },
  rejectReason: { ar: "سبب الرفض", en: "Rejection reason" },
  sentOk: { ar: "أُرسلت مطالبتك", en: "Claim sent" },
  doneOk: { ar: "سُجّل القرار", en: "Recorded" },
  all: { ar: "الكل", en: "All" },
};

type Category = {
  id: number; code: string; name_ar: string;
  max_per_claim: string | null; max_per_month: string | null;
  is_active: boolean;
};
type Claim = {
  id: number; claim_no: string; employment_id: number;
  employee: string; employee_no: string; category: string;
  spent_on: string; amount: string; description: string;
  receipt_url: string; status: string; status_label: string;
  decision_note: string; method: string; paid_on: string | null;
};
type Opt = { value: string; label: string };

const TONE: Record<string, string> = {
  pending: "badge-warn", approved: "badge-ok",
  rejected: "badge-danger", settled: "badge",
};

export default function ExpensesPage() {
  const { L } = useT(T);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [statuses, setStatuses] = useState<Opt[]>([]);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [adding, setAdding] = useState(false);
  const [acting, setActing] = useState(false);
  const [shown, setShown] = useState<Claim | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ claims: Claim[]; categories: Category[];
                               statuses: Opt[] }>(
        `/expenses/${filter ? `?status=${filter}` : ""}`);
      setClaims(d.claims);
      setCats(d.categories);
      setStatuses(d.statuses);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const decide = async (c: Claim, approve: boolean) => {
    setActing(true); setErr("");
    try {
      const note = approve ? "" : (prompt(L("rejectReason")) || "");
      await apiPost(`/expenses/${c.id}/decide/`, { approve, note });
      setMsg(L("doneOk"));
      setTimeout(() => setMsg(""), 3000);
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  const settle = async (c: Claim) => {
    setActing(true); setErr("");
    try {
      await apiPost(`/expenses/${c.id}/settle/`, { method: "outside" });
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

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
      <div className="spread">
        <div>
          <h1 style={{ margin: 0 }}>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("sub")}
          </div>
        </div>
        <button className="btn btn-primary btn-sm"
                onClick={() => setAdding(true)}>{L("add")}</button>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
        <button className={`btn btn-sm ${!filter ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setFilter("")}>{L("all")}</button>
        {statuses.map((s) => (
          <button key={s.value}
                  className={`btn btn-sm ${filter === s.value ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setFilter(s.value)}>{s.label}</button>
        ))}
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {claims.length === 0 ? (
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
                  <th style={{ width: 135 }}>{L("no")}</th>
                  <th style={{ width: 160 }}>{L("employee")}</th>
                  <th style={{ width: 120 }}>{L("category")}</th>
                  <th style={{ width: 115 }}>{L("spentOn")}</th>
                  <th style={{ width: 105 }}>{L("amount")}</th>
                  <th style={{ width: 110 }}>{L("state")}</th>
                  <th style={{ width: 190 }} />
                </tr>
              </thead>
              <tbody>
                {claims.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <span className="num" style={{ fontSize: ".8rem" }}>
                        {c.claim_no}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{c.employee}</div>
                      <div className="muted truncate"
                           style={{ fontSize: ".75rem", maxWidth: 150 }}>
                        {c.description}
                      </div>
                    </td>
                    <td className="muted">{c.category}</td>
                    <td><span className="num">{c.spent_on}</span></td>
                    <td><span className="num">{c.amount}</span></td>
                    <td>
                      <span className={`badge ${TONE[c.status] || "badge"}`}>
                        {c.status_label}
                      </span>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 5 }}>
                        <button className="btn btn-sm btn-ghost"
                                onClick={() => setShown(c)}>
                          {L("receipt")}
                        </button>
                        {c.status === "pending" && (
                          <>
                            <button className="btn btn-sm btn-primary"
                                    disabled={acting}
                                    onClick={() => decide(c, true)}>
                              {L("approve")}
                            </button>
                            <button className="btn btn-sm btn-danger"
                                    disabled={acting}
                                    onClick={() => decide(c, false)}>
                              {L("reject")}
                            </button>
                          </>
                        )}
                        {c.status === "approved" && (
                          <button className="btn btn-sm" disabled={acting}
                                  onClick={() => settle(c)}>
                            {L("settle")}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {adding && (
        <ClaimDialog cats={cats} L={L} onClose={() => setAdding(false)}
                     onSaved={async () => {
                       setAdding(false);
                       setMsg(L("sentOk"));
                       setTimeout(() => setMsg(""), 4000);
                       await load();
                     }} />
      )}

      {shown && (
        <div onClick={() => setShown(null)} style={{
          position: "fixed", inset: 0, background: "rgba(16,28,38,.5)",
          display: "grid", placeItems: "center", padding: 20, zIndex: 80,
        }}>
          <div className="card" style={{ padding: 20, maxWidth: 560 }}
               onClick={(e) => e.stopPropagation()}>
            <div className="spread">
              <strong>{shown.claim_no}</strong>
              <span className="num">{shown.amount}</span>
            </div>
            <div className="muted" style={{ fontSize: ".84rem",
                                            marginTop: 4 }}>
              {shown.description}
            </div>
            {shown.decision_note && (
              <div style={{ color: "var(--danger)", fontSize: ".84rem",
                            marginTop: 8 }}>
                {shown.decision_note}
              </div>
            )}
            <AuthImage src={shown.receipt_url} alt=""
                       style={{ marginTop: 14, maxWidth: "100%",
                                borderRadius: "var(--radius-sm)" }} />
            <button className="btn" style={{ marginTop: 14 }}
                    onClick={() => setShown(null)}>{L("cancel")}</button>
          </div>
        </div>
      )}
    </div>
  );
}


function ClaimDialog({ cats, L, onClose, onSaved }: {
  cats: Category[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    category_id: "", amount: "", description: "",
    spent_on: new Date().toISOString().slice(0, 10),
  });
  const [receipt, setReceipt] = useState("");
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const cat = cats.find((c) => String(c.id) === f.category_id);

  const upload = async (file: File) => {
    setUploading(true); setErr("");
    try {
      const res = await apiUpload<{ url: string }>("/files/", file);
      setReceipt(res.url);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "تعذّر رفع الفاتورة");
    } finally { setUploading(false); }
  };

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/expenses/", {
        ...f, category_id: Number(f.category_id),
        receipt_url: receipt,
      });
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 470,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("newTitle")}</h3>

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
            <span className="label">{L("category")}</span>
            <select className="select" value={f.category_id}
                    onChange={(e) => setF({ ...f,
                      category_id: e.target.value })}>
              <option value="">—</option>
              {cats.map((c) => (
                <option key={c.id} value={c.id}>{c.name_ar}</option>
              ))}
            </select>
            {cat && (cat.max_per_claim || cat.max_per_month) && (
              <span className="muted" style={{ fontSize: ".78rem" }}>
                {L("perClaim")}: {cat.max_per_claim || L("noCap")}
                {" · "}
                {L("perMonth")}: {cat.max_per_month || L("noCap")}
              </span>
            )}
          </label>

          <div className="row" style={{ gap: 12 }}>
            <label className="field" style={{ width: 140 }}>
              <span className="label">{L("amount")}</span>
              <input className="input num" type="number" min={0}
                     step="0.01" value={f.amount}
                     onChange={(e) => setF({ ...f,
                       amount: e.target.value })} />
            </label>
            <div className="field" style={{ flex: 1 }}>
              <label className="label">{L("spentOn")}</label>
              <DateField value={f.spent_on}
                         onChange={(v) => setF({ ...f, spent_on: v })} />
            </div>
          </div>

          <label className="field">
            <span className="label">{L("what")}</span>
            <input className="input" value={f.description}
                   onChange={(e) => setF({ ...f,
                     description: e.target.value })} />
          </label>

          <div className="field">
            <span className="label">
              {L("receipt")}
              <span style={{ color: "var(--danger)" }}> *</span>
            </span>
            <input ref={fileRef} type="file" accept="image/*,.pdf"
                   style={{ display: "none" }}
                   onChange={(e) => e.target.files?.[0]
                     && upload(e.target.files[0])} />
            {receipt ? (
              <div className="row" style={{ gap: 8, alignItems: "center" }}>
                <span className="badge badge-ok">✓</span>
                <button className="btn btn-sm btn-ghost"
                        onClick={() => setReceipt("")}>×</button>
              </div>
            ) : (
              <button className="btn btn-sm" disabled={uploading}
                      onClick={() => fileRef.current?.click()}>
                {uploading ? L("uploading") : L("pick")}
              </button>
            )}
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {L("receiptHint")}
            </span>
          </div>
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.category_id || !f.amount
                            || !f.description.trim() || !receipt}
                  onClick={submit}>{busy ? "…" : L("save")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}
