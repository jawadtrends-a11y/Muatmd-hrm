"use client";
/**
 * الجزاءات التأديبية (ق-119، ق-121).
 *
 * **السجلّ يعرض المخالف والمسؤول يوقّع بضغطة** — فما لا يُعرض لا
 * يُطبَّق، ولا يفتح أحدٌ شاشةً ليبحث عن مخالف.
 */
import { useUrlTab } from "@/lib/useUrlTab";
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  tabDeductions: { ar: "الخصومات", en: "Deductions" },
  dedTitle: { ar: "خصومات البصمات", en: "Attendance deductions" },
  dedHint: {
    ar: "النظام يحسب الغياب والتأخير ونقص الساعات — والقرار لكم: خصم أو إعفاء. وضع الاحتساب (آليّ أو يدويّ) يُضبط في قواعد المسير.",
    en: "The system computes absence, lateness and shortfall — the decision is yours: deduct or waive. The mode is set in payroll rules.",
  },
  dedMonth: { ar: "الشهر", en: "Month" },
  dedStatus: { ar: "الحالة", en: "Status" },
  dedKind: { ar: "النوع", en: "Type" },
  dedSearch: { ar: "بحث بالاسم أو الرقم", en: "Search name or no." },
  dedAll: { ar: "الكل", en: "All" },
  dedPending: { ar: "بانتظار القرار", en: "Pending" },
  dedApplied: { ar: "مخصوم", en: "Deducted" },
  dedWaived: { ar: "معفى", en: "Waived" },
  dedApply: { ar: "خصم", en: "Deduct" },
  dedWaive: { ar: "إعفاء", en: "Waive" },
  dedUndo: { ar: "إلغاء الخصم", en: "Undo" },
  dedReason: { ar: "سبب الإعفاء", en: "Reason for waiving" },
  dedReasonRequired: { ar: "اكتب سبب الإعفاء", en: "Reason is required" },
  dedEmpty: { ar: "لا خصومات في هذه الفترة", en: "No deductions in this period" },
  dedRecalc: {
    ar: "⚠️ أعد احتساب المسير ليأخذ القرار مفعوله",
    en: "Recalculate the payroll run to apply this decision",
  },
  dedQty: { ar: "المقدار", en: "Qty" },
  dedDay: { ar: "اليوم", en: "Day" },
  dedLimit: { ar: "عدد الصفوف", en: "Rows" },
  dedAmount: { ar: "المبلغ", en: "Amount" },
  title: { ar: "الجزاءات", en: "Penalties" },
  sub: {
    ar: "مخالفات لم يُوقَّع عليها — راجعها ووقّع ما تراه",
    en: "Unsigned violations — review and apply",
  },
  tabBoard: { ar: "الجزاءات", en: "Penalties" },
  tabRegister: { ar: "صحيفة الجزاءات", en: "Register" },
  from: { ar: "من", en: "From" },
  to: { ar: "إلى", en: "To" },
  employee: { ar: "الموظف", en: "Employee" },
  date: { ar: "التاريخ", en: "Date" },
  state: { ar: "الحالة", en: "State" },
  minutes: { ar: "الدقائق", en: "Minutes" },
  timeDed: { ar: "حسم الوقت", en: "Time deduction" },
  action: { ar: "إجراء", en: "Action" },
  apply: { ar: "توقيع الجزاء", en: "Apply" },
  applyAll: { ar: "توقيع كل السجلّ", en: "Apply all" },
  applying: { ar: "جارٍ التوقيع…", en: "Applying…" },
  empty: { ar: "لا مخالفات في هذه المدّة", en: "No violations in range" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا تملك عرض الجزاءات", en: "Not permitted" },
  violation: { ar: "المخالفة", en: "Violation" },
  kind: { ar: "الجزاء", en: "Penalty" },
  days: { ar: "الأيام", en: "Days" },
  amount: { ar: "المبلغ", en: "Amount" },
  occurrence: { ar: "التكرار", en: "Occurrence" },
  status: { ar: "الحالة", en: "Status" },
  cancelPenalty: { ar: "إلغاء", en: "Cancel" },
  cancelTitle: { ar: "إلغاء الجزاء", en: "Cancel penalty" },
  cancelHint: {
    ar: "⚠️ الجزاء يُلغى ولا يُحذف — فالسجلّ يبقى، وأثره المالي يزول",
    en: "Cancelled, not deleted",
  },
  cancelReason: { ar: "سبب الإلغاء", en: "Reason" },
  reasonRequired: { ar: "اكتب سبب الإلغاء", en: "Reason required" },
  confirmCancel: { ar: "تأكيد الإلغاء", en: "Confirm" },
  cancelled2: { ar: "أُلغي الجزاء", en: "Cancelled" },
  back2: { ar: "تراجع", en: "Back" },
  dlgTitle: { ar: "توقيع الجزاء", en: "Apply penalty" },
  dlgIntro: {
    ar: "الجزاء المقترح من لائحتكم — راجعه قبل التوقيع",
    en: "Suggested from your policy — review before applying",
  },
  fViolation: { ar: "المخالفة", en: "Violation" },
  fDesc: { ar: "وصف الواقعة", en: "Description" },
  fStatement: { ar: "إفادة الموظف", en: "Employee statement" },
  stmtHint: {
    ar: "ما تجاوز أجر يوم يلزمه سماع أقواله وإثباتها",
    en: "Above one day's wage requires a recorded statement",
  },
  fApply: { ar: "طبّق الخصم", en: "Apply deduction" },
  fCount: { ar: "احتسب في التكرار", en: "Count as repeat" },
  countHint: {
    ar: "غير المحتسَب لا يرفع درجته في المخالفة القادمة",
    en: "Uncounted repeats do not escalate",
  },
  fOccurrence: { ar: "عدد مرات التكرار", en: "Occurrence" },
  occHint: {
    ar: "محسوب تلقائيًّا — يمكنك تعديله",
    en: "Calculated automatically — editable",
  },
  go: { ar: "توقيع", en: "Apply" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  cap: { ar: "تنبيه السقف", en: "Cap notice" },
  done: { ar: "وُقّع {n} جزاءً", en: "{n} applied" },
  someFailed: { ar: "وتعذّر {n}", en: "{n} failed" },
};

type Row = {
  employment_id: number; employee_no: string; name: string;
  date: string; state: string; attendance_status: string;
  minutes: number; time_deduction: string;
};
type Violation = {
  id: number; code: string; name_ar: string; financial_effect: boolean;
};
type Preview = {
  occurrence: number; suggested_occurrence: number;
  kind_label: string; days: string; amount: string;
  deductible: boolean; block_reason: string; capped: boolean;
  cap_note: string; deducted_this_month: string; monthly_cap: string;
};
type RegRow = {
  id: number; name: string; employee_no: string; violation: string;
  occurred_on: string; occurrence: number; kind_label: string;
  days: string; amount: string; status_label: string;
  applied: boolean; counted: boolean; status: string;
};

const monthStart = () => {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
};

export default function PenaltiesPage() {
  const { L } = useT(T);
  // ⚠️⚠️ ق-٢٥٣: **الخصومات قبل الجزاءات** — فالجزاء لا معنى له إن لم
  // يُطبَّق الخصم أصلًا. والخصم يُحسب آليًّا **ويُقرَّر بشرًا**.
  const [tab, setTab] = useUrlTab<"deductions" | "board" | "register">(
    ["deductions", "board", "register"], "deductions");
  const [from, setFrom] = useState(monthStart());
  const [to, setTo] = useState(new Date().toISOString().slice(0, 10));
  const [rows, setRows] = useState<Row[]>([]);
  const [reg, setReg] = useState<RegRow[]>([]);
  const [vios, setVios] = useState<Violation[]>([]);
  const [perms, setPerms] = useState<string[]>([]);
  const [busy, setBusy] = useState(true);
  const [acting, setActing] = useState(false);
  const [bStatus, setBStatus] = useState("");
  const [bLimit, setBLimit] = useState(25);
  const [bQ, setBQ] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [dlg, setDlg] = useState<Row | null>(null);

  const canView = perms.includes("attendance.view")
    || perms.includes("employees.view");
  const canEdit = perms.includes("employees.edit");
  // ق-203: **إلغاء جزاء** — ⚠️ **لا حذفه**: فالسجلّ يبقى
  const [cancelling, setCancelling] = useState<RegRow | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const p = await apiGet<{ permissions: string[] }>("/me/workspace/");
      setPerms(p.permissions || []);
      const [b, v, r] = await Promise.all([
        apiGet<{ rows: Row[] }>(
          `/penalties/board/?from=${from}&to=${to}`).catch(() => ({ rows: [] })),
        apiGet<{ violations: Violation[] }>("/penalties/violations/")
          .catch(() => ({ violations: [] })),
        apiGet<RegRow[]>("/penalties/").catch(() => []),
      ]);
      setRows(b.rows || []);
      setVios(v.violations || []);
      setReg(r);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [from, to]);

  useEffect(() => { load(); }, [load]);

  const applyAll = async () => {
    setActing(true); setErr("");
    try {
      const out = await apiPost<{ issued: number; failed: unknown[] }>(
        "/penalties/issue-batch/",
        { rows, employee_statement: "" });
      setMsg(L("done").replace("{n}", String(out.issued))
        + (out.failed.length
          ? " — " + L("someFailed").replace("{n}", String(out.failed.length))
          : ""));
      setTimeout(() => setMsg(""), 6000);
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  if (busy) return <div className="card" style={{ padding: 40,
    textAlign: "center", color: "var(--ink-3)" }}>{L("loading")}</div>;

  if (!canView) return (
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
        {tab === "board" && canEdit && rows.length > 0 && (
          <button className="btn btn-primary" disabled={acting}
                  onClick={applyAll}>
            {acting ? L("applying") : L("applyAll")}
          </button>
        )}
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="row" style={{ gap: 6 }}>
        <button className={`btn btn-sm ${tab === "deductions" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setTab("deductions")}>{L("tabDeductions")}</button>
        <button className={`btn btn-sm ${tab === "board" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setTab("board")}>{L("tabBoard")}</button>
        <button className={`btn btn-sm ${tab === "register" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setTab("register")}>{L("tabRegister")}</button>
      </div>

      {/* ⚠️ الخصم صلاحية مسير (`payroll.create`) لا صلاحية موظفين */}
      {tab === "deductions" && (
        <DeductionsTab L={L} canEdit={perms.includes("payroll.create")} />
      )}

      {tab === "board" && (
        <>
          <div className="card" style={{ padding: 16 }}>
            <div className="row" style={{ gap: 14, flexWrap: "wrap",
                                          alignItems: "flex-end" }}>
              <div className="field" style={{ minWidth: 160 }}>
                <label className="label">{L("from")}</label>
                <DateField value={from} onChange={setFrom} />
              </div>
              <div className="field" style={{ minWidth: 160 }}>
                <label className="label">{L("to")}</label>
                <DateField value={to} onChange={setTo} />
              </div>
              {/* ⚠️ ق-٢٥٣: نفس فلاتر الخصومات — فالتبويبان صفحةٌ واحدة،
                  واختلافُ الفلاتر بينهما يُربك من ينتقل بينهما. */}
              <label className="field" style={{ minWidth: 150 }}>
                <span className="label">{L("dedStatus")}</span>
                <select className="input" value={bStatus}
                        onChange={(e) => setBStatus(e.target.value)}>
                  <option value="">{L("dedAll")}</option>
                  <option value="proposed">{L("dedPending")}</option>
                  <option value="applied">{L("dedApplied")}</option>
                </select>
              </label>
              <label className="field" style={{ minWidth: 110 }}>
                <span className="label">{L("dedLimit")}</span>
                <select className="input" value={String(bLimit)}
                        onChange={(e) => setBLimit(Number(e.target.value))}>
                  {[10, 25, 50, 100, 250, 500].map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </label>
              <label className="field grow" style={{ minWidth: 180 }}>
                <span className="label">{L("dedSearch")}</span>
                <input className="input" value={bQ}
                       onChange={(e) => setBQ(e.target.value)} />
              </label>
            </div>
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
                      <th style={{ width: 120 }}>{L("date")}</th>
                      <th>{L("state")}</th>
                      <th style={{ width: 90 }}>{L("minutes")}</th>
                      <th style={{ width: 120 }}>{L("timeDed")}</th>
                      {canEdit && <th style={{ width: 140 }} />}
                    </tr>
                  </thead>
                  <tbody>
                    {rows
                      .filter((r) => !bQ || r.name.includes(bQ)
                                     || r.employee_no.includes(bQ))
                      .filter((r) => !bStatus || r.state === bStatus)
                      .slice(0, bLimit)
                      .map((r, i) => (
                      <tr key={`${r.employment_id}-${r.date}-${i}`}>
                        <td>
                          <div style={{ fontWeight: 500 }}>{r.name}</div>
                          <div className="muted num"
                               style={{ fontSize: ".76rem" }}>
                            {r.employee_no}
                          </div>
                        </td>
                        <td><span className="num">{r.date}</span></td>
                        <td>
                          <span className="badge badge-warn">{r.state}</span>
                        </td>
                        <td><span className="num">{r.minutes || "—"}</span></td>
                        <td><span className="num">{r.time_deduction}</span></td>
                        {canEdit && (
                          <td>
                            <button className="btn btn-sm"
                                    onClick={() => { setDlg(r); setErr(""); }}>
                              {L("apply")}
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {tab === "register" && (
        <div className="card" style={{ overflow: "hidden" }}>
          {reg.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center",
                          color: "var(--ink-3)" }}>{L("empty")}</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>{L("employee")}</th>
                    <th>{L("violation")}</th>
                    <th style={{ width: 110 }}>{L("date")}</th>
                    <th style={{ width: 80 }}>{L("occurrence")}</th>
                    <th>{L("kind")}</th>
                    <th style={{ width: 80 }}>{L("days")}</th>
                    <th style={{ width: 110 }}>{L("amount")}</th>
                    <th style={{ width: 90 }}>{L("status")}</th>
                    {/* ق-203: عمود الإلغاء */}
                    <th style={{ width: 90 }} />
                  </tr>
                </thead>
                <tbody>
                  {reg.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <div style={{ fontWeight: 500 }}>{p.name}</div>
                        <div className="muted num"
                             style={{ fontSize: ".76rem" }}>{p.employee_no}</div>
                      </td>
                      <td className="truncate">{p.violation}</td>
                      <td><span className="num">{p.occurred_on}</span></td>
                      <td><span className="num">{p.occurrence}</span></td>
                      <td className="muted">{p.kind_label}</td>
                      <td><span className="num">{p.days}</span></td>
                      <td>
                        <span className="num">
                          {p.applied ? p.amount : "—"}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${
                          p.status === "cancelled" ? "badge-warn" : ""}`}>
                          {p.status_label}
                        </span>
                      </td>
                      {/* ق-203: ⚠️⚠️ **وجزاءٌ صدر خطأً يُلغى لا
                          يُحذف** — وبلا شاشةٍ يبقى ظالمًا. */}
                      <td style={{ textAlign: "end" }}>
                        {canEdit && p.status !== "cancelled" && (
                          <button className="btn btn-sm btn-ghost"
                                  style={{ color: "var(--danger)" }}
                                  onClick={() => setCancelling(p)}>
                            {L("cancelPenalty")}
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
      )}

      {dlg && (
        <ApplyDialog row={dlg} vios={vios} L={L}
                     onClose={() => setDlg(null)}
                     onDone={async () => { setDlg(null); await load(); }} />
      )}

      {/* ق-203: **إلغاء الجزاء** — لا حذفه */}
      {cancelling && (
        <CancelPenaltyDialog row={cancelling} L={L}
          onClose={() => setCancelling(null)}
          onDone={async () => { setCancelling(null); await load(); }} />
      )}
    </div>
  );
}


/* ══ نافذة التوقيع ══ */

function ApplyDialog({ row, vios, L, onClose, onDone }: {
  row: Row;
  vios: Violation[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [vid, setVid] = useState<string>(String(vios[0]?.id || ""));
  const [desc, setDesc] = useState(`${row.state} — ${row.minutes} دقيقة`);
  const [stmt, setStmt] = useState("");
  const [apply, setApply] = useState(true);
  const [count, setCount] = useState(true);
  const [occ, setOcc] = useState<string>("");
  const [pv, setPv] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!vid) return;
    apiPost<Preview>("/penalties/preview/", {
      employment_id: row.employment_id,
      violation_id: Number(vid),
      occurred_on: row.date,
      occurrence: occ ? Number(occ) : undefined,
    }).then(setPv).catch(() => setPv(null));
  }, [vid, row, occ]);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/penalties/issue/", {
        employment_id: row.employment_id,
        violation_id: Number(vid),
        occurred_on: row.date,
        description: desc,
        employee_statement: stmt,
        apply_deduction: apply,
        count_occurrence: count,
        occurrence: occ ? Number(occ) : undefined,
      });
      onDone();
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
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 520,
                                     width: "100%", maxHeight: "88vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("dlgTitle")}</h3>
        <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
          {row.name} · {row.date} · {row.state} — {L("dlgIntro")}
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
            <span className="label">{L("fViolation")}</span>
            <select className="select" value={vid}
                    onChange={(e) => setVid(e.target.value)}>
              {vios.map((v) => (
                <option key={v.id} value={v.id}>{v.name_ar}</option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="label">{L("fOccurrence")}</span>
            <input className="input num" type="number" min={1}
                   placeholder={pv ? String(pv.suggested_occurrence) : ""}
                   value={occ}
                   onChange={(e) => setOcc(e.target.value)} />
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {L("occHint")}
            </span>
          </label>

          {pv && (
            <div style={{ padding: "10px 14px",
                          borderRadius: "var(--radius-sm)",
                          background: "var(--paper-2)",
                          fontSize: ".85rem", display: "grid", gap: 4 }}>
              <div className="spread">
                <span className="muted">{L("occurrence")}</span>
                <span className="num">{pv.occurrence}</span>
              </div>
              <div className="spread">
                <span className="muted">{L("kind")}</span>
                <span>{pv.kind_label}</span>
              </div>
              <div className="spread">
                <span className="muted">{L("days")}</span>
                <span className="num">{pv.days}</span>
              </div>
              <div className="spread" style={{ fontWeight: 600 }}>
                <span>{L("amount")}</span>
                <span className="num">{pv.amount}</span>
              </div>
              {(pv.cap_note || pv.block_reason) && (
                <div style={{ color: "var(--copper)", fontSize: ".8rem",
                              marginTop: 4 }}>
                  {pv.cap_note || pv.block_reason}
                </div>
              )}
            </div>
          )}

          <label className="field">
            <span className="label">{L("fDesc")}</span>
            <input className="input" value={desc}
                   onChange={(e) => setDesc(e.target.value)} />
          </label>

          <label className="field">
            <span className="label">{L("fStatement")}</span>
            <textarea className="input" rows={3} value={stmt}
                      onChange={(e) => setStmt(e.target.value)} />
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {L("stmtHint")}
            </span>
          </label>

          <label className="row" style={{ gap: 8, cursor: "pointer",
                                          fontSize: ".88rem" }}>
            <input type="checkbox" checked={apply}
                   onChange={(e) => setApply(e.target.checked)} />
            <span>{L("fApply")}</span>
          </label>

          <label className="row" style={{ gap: 8, cursor: "pointer",
                                          fontSize: ".88rem",
                                          alignItems: "flex-start" }}>
            <input type="checkbox" checked={count} style={{ marginTop: 3 }}
                   onChange={(e) => setCount(e.target.checked)} />
            <span>
              {L("fCount")}
              <div className="muted" style={{ fontSize: ".78rem" }}>
                {L("countHint")}
              </div>
            </span>
          </label>
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary" disabled={busy || !vid}
                  onClick={submit}>
            {busy ? "…" : L("go")}
          </button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>

  );
}


/**
 * إلغاء جزاء (ق-203).
 *
 * ⚠️⚠️ **وجزاءٌ صدر خطأً يُلغى لا يُحذف**: **فالسجلّ يبقى وأثره
 * المالي يزول** — وبلا شاشةٍ كان يبقى ظالمًا.
 *
 * ⚠️ **ولا إلغاءَ بلا سبب**: فمن يراجع بعد سنة **يحتاج معرفة
 * لماذا** (ق-80).
 */
function CancelPenaltyDialog({ row, L, onClose, onDone }: {
  row: RegRow;
  L: (k: string) => string;
  onClose: () => void;
  onDone: () => void | Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!reason.trim()) { setErr(L("reasonRequired")); return; }
    setBusy(true);
    setErr("");
    try {
      await apiPost(`/penalties/${row.id}/cancel/`,
                    { reason: reason.trim() });
      await onDone();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose();
    }} style={{
      position: "fixed", inset: 0, zIndex: 60,
      background: "rgba(16,28,38,.45)", display: "grid",
      placeItems: "center", padding: 16,
    }}>
      <div className="card" style={{ padding: 22, maxWidth: 440,
                                     width: "100%" }}>
        <h3 style={{ margin: "0 0 4px" }}>{L("cancelTitle")}</h3>
        <div className="muted" style={{ fontSize: ".8rem",
                                        lineHeight: 1.9,
                                        marginBottom: 14 }}>
          {L("cancelHint")}
        </div>

        <div style={{ padding: "10px 12px",
                      background: "var(--paper-2)",
                      borderRadius: "var(--radius-sm)",
                      marginBottom: 14, fontSize: ".86rem" }}>
          <strong>{row.name}</strong>
          <div className="muted" style={{ fontSize: ".78rem",
                                          marginTop: 3 }}>
            {row.violation} ·{" "}
            <span className="num">{row.occurred_on}</span>
          </div>
        </div>

        {err && (
          <div className="card" style={{ borderColor: "var(--danger)",
                                         color: "var(--danger)",
                                         marginBottom: 12 }}>
            {err}
          </div>
        )}

        <label className="field">
          <span className="label">{L("cancelReason")}</span>
          <textarea className="input" rows={3} value={reason}
                    onChange={(e) => setReason(e.target.value)} />
        </label>

        <div className="row" style={{ gap: 8, marginTop: 16,
                                      justifyContent: "flex-end" }}>
          <button className="btn btn-ghost" onClick={onClose}>
            {L("back2")}
          </button>
          <button className="btn btn-danger"
                  disabled={busy || !reason.trim()}
                  onClick={submit}>
            {busy ? "…" : L("confirmCancel")}
          </button>
        </div>
      </div>
    </div>
  );
}


/* ═══ الخصومات (ق-٢٥٣) ═══════════════════════════════════════
 *
 * ⚠️⚠️ **الحساب ليس قرارًا.** كان المسير يقرأ أيام الغياب من الحضور
 * **ويحسمها مباشرةً** — فبلغ الخصم في أول مسيرٍ حقيقيّ **٥٩٪ من الرواتب**،
 * لأن البصم ناقصٌ لا لأن الموظفين غابوا. والبصمة تنقص لعطلٍ في الجهاز، أو
 * مهمةٍ خارج الموقع، أو نسيان — **والغياب في النظام ليس غيابًا في الواقع**.
 *
 * فوضعان في قواعد المسير:
 *   **آليّ**  — يُخصم، وللموارد **إلغاء** خصمٍ بعينه (خطأ أو استثناء)
 *   **يدويّ** — لا يُخصم شيء حتى تُقرَّر كلُّ حالة: **خصم أو إعفاء**
 * ⚠️ **والإعفاء يُعلَّل** — فالمراجع يعرف لماذا سقط خصمٌ مستحَقّ.
 */
type DedRow = {
  id: number; employee_no: string; name_ar: string; period: string;
  kind: string; kind_label: string; quantity: string; amount: string;
  work_date: string; quantity_label: string;
  explanation: string; status: string; status_label: string;
  decision_note: string;
};

function DeductionsTab({ L, canEdit }: {
  L: (k: string) => string;
  canEdit: boolean;
}) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(25);
  const [page, setPage] = useState(1);
  const [meta, setMeta] = useState({ count: 0, pages: 1 });
  const [rows, setRows] = useState<DedRow[]>([]);
  const [totals, setTotals] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [waiving, setWaiving] = useState<number | null>(null);

  const load = useCallback(() => {
    setBusy(true);
    // ⚠️ **البحث في الخادم لا في الصفحة** — فمن بحث عن موظفٍ في الصفحة
    // العاشرة كان لا يجده أبدًا، ويظنّ أنه غير موجود.
    const p = new URLSearchParams({ year: String(year), month: String(month),
                                    limit: String(limit), page: String(page) });
    if (q.trim()) p.set("q", q.trim());
    if (status) p.set("status", status);
    if (kind) p.set("kind", kind);
    apiGet<{ rows: DedRow[]; totals: Record<string, number>;
             count: number; pages: number }>(
      `/payroll/attendance-deductions/?${p}`)
      .then((d) => {
        setRows(d.rows || []);
        setTotals(d.totals || {});
        setMeta({ count: d.count ?? 0, pages: d.pages ?? 1 });
      })
      .catch(() => { setRows([]); setTotals({}); setMeta({ count: 0, pages: 1 }); })
      .finally(() => setBusy(false));
  }, [year, month, status, kind, limit, page, q]);

  // ⚠️ تغييرُ فلترٍ يعيد للصفحة الأولى — وإلا وقف المستخدم على صفحةٍ لا وجود لها
  useEffect(() => { setPage(1); }, [year, month, status, kind, limit, q]);

  useEffect(() => { load(); }, [load]);

  async function decide(id: number, decision: string, reason = "") {
    setErr("");
    try {
      await apiPost(`/payroll/attendance-deductions/${id}/decide/`,
                    { decision, note: reason });
      setWaiving(null);
      setNote("");
      load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
  }

  const shown = rows;

  return (
    <>
      <div className="card" style={{ padding: 16 }}>
        <strong style={{ fontSize: ".95rem" }}>{L("dedTitle")}</strong>
        <p style={{ margin: "6px 0 14px", fontSize: ".85rem",
                    color: "var(--ink-3)" }}>{L("dedHint")}</p>

        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <label className="field" style={{ minWidth: 110 }}>
            <span className="label">{L("dedMonth")}</span>
            <select className="input" value={String(month)}
                    onChange={(e) => setMonth(Number(e.target.value))}>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>{String(m).padStart(2, "0")}</option>
              ))}
            </select>
          </label>
          <label className="field" style={{ minWidth: 110 }}>
            <span className="label">&nbsp;</span>
            <input className="input num" type="number" value={String(year)}
                   onChange={(e) => setYear(Number(e.target.value))} />
          </label>
          <label className="field" style={{ minWidth: 150 }}>
            <span className="label">{L("dedStatus")}</span>
            <select className="input" value={status}
                    onChange={(e) => setStatus(e.target.value)}>
              <option value="">{L("dedAll")}</option>
              <option value="pending">{L("dedPending")}</option>
              <option value="applied">{L("dedApplied")}</option>
              <option value="waived">{L("dedWaived")}</option>
            </select>
          </label>
          <label className="field" style={{ minWidth: 140 }}>
            <span className="label">{L("dedKind")}</span>
            <select className="input" value={kind}
                    onChange={(e) => setKind(e.target.value)}>
              <option value="">{L("dedAll")}</option>
              <option value="absence">غياب</option>
              <option value="late">تأخير</option>
              <option value="shortfall">نقص ساعات</option>
            </select>
          </label>
          <label className="field" style={{ minWidth: 110 }}>
            <span className="label">{L("dedLimit")}</span>
            <select className="input" value={String(limit)}
                    onChange={(e) => setLimit(Number(e.target.value))}>
              {[10, 25, 50, 100, 250, 500].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
          <label className="field grow" style={{ minWidth: 180 }}>
            <span className="label">{L("dedSearch")}</span>
            <input className="input" value={q}
                   onChange={(e) => setQ(e.target.value)} />
          </label>
        </div>

        <div className="row" style={{ gap: 18, marginTop: 14,
                                      fontSize: ".85rem" }}>
          <span>{L("dedPending")}: <b>{(totals.pending ?? 0).toFixed(2)}</b></span>
          <span>{L("dedApplied")}: <b>{(totals.applied ?? 0).toFixed(2)}</b></span>
          <span>{L("dedWaived")}: <b>{(totals.waived ?? 0).toFixed(2)}</b></span>
        </div>
      </div>

      {err && <div className="alert-error" style={{ marginTop: 12 }}>{err}</div>}

      <div className="card" style={{ marginTop: 12, overflow: "hidden" }}>
        {busy ? null : shown.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center",
                        color: "var(--ink-3)" }}>{L("dedEmpty")}</div>
        ) : (
          <table style={{ width: "100%", fontSize: ".88rem" }}>
            <thead>
              <tr style={{ color: "var(--ink-3)" }}>
                <th style={{ textAlign: "start", padding: "10px 12px" }}>
                  {L("dedSearch")}</th>
                <th style={{ textAlign: "start" }}>{L("dedDay")}</th>
                <th style={{ textAlign: "start" }}>{L("dedKind")}</th>
                <th style={{ textAlign: "start" }}>{L("dedQty")}</th>
                <th style={{ textAlign: "start" }}>{L("dedAmount")}</th>
                <th style={{ textAlign: "start" }}>{L("dedStatus")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id} style={{ borderTop: "1px solid var(--line)" }}>
                  <td style={{ padding: "10px 12px" }}>
                    <div>{r.name_ar}</div>
                    <small style={{ color: "var(--ink-3)" }}>{r.employee_no}</small>
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>{r.work_date}</td>
                  <td>{r.kind_label}</td>
                  <td>
                    {r.quantity_label || r.quantity}
                    {r.explanation && (
                      <div><small style={{ color: "var(--ink-3)" }}>
                        {r.explanation}</small></div>
                    )}
                  </td>
                  <td><b>{r.amount}</b></td>
                  <td>
                    <span style={{
                      color: r.status === "applied" ? "var(--danger)"
                           : r.status === "waived" ? "var(--ink-3)"
                           : "var(--warn, var(--ink-2))" }}>
                      {r.status_label}
                    </span>
                    {r.decision_note && (
                      <div><small style={{ color: "var(--ink-3)" }}>
                        {r.decision_note}</small></div>
                    )}
                  </td>
                  <td style={{ textAlign: "end", padding: "8px 12px" }}>
                    {canEdit && waiving === r.id ? (
                      <div className="row" style={{ gap: 6,
                                                    justifyContent: "flex-end" }}>
                        <input className="input" style={{ maxWidth: 200 }}
                               placeholder={L("dedReason")}
                               value={note}
                               onChange={(e) => setNote(e.target.value)} />
                        <button className="btn btn-sm btn-primary"
                                disabled={!note.trim()}
                                onClick={() => decide(r.id, "waived", note)}>
                          {L("dedWaive")}
                        </button>
                        <button className="btn btn-sm btn-ghost"
                                onClick={() => { setWaiving(null); setNote(""); }}>
                          ✕
                        </button>
                      </div>
                    ) : canEdit ? (
                      <div className="row" style={{ gap: 6,
                                                    justifyContent: "flex-end" }}>
                        {r.status !== "applied" && (
                          <button className="btn btn-sm"
                                  onClick={() => decide(r.id, "applied")}>
                            {L("dedApply")}
                          </button>
                        )}
                        {r.status !== "waived" && (
                          <button className="btn btn-sm btn-ghost"
                                  onClick={() => setWaiving(r.id)}>
                            {r.status === "applied" ? L("dedUndo") : L("dedWaive")}
                          </button>
                        )}
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {meta.pages > 1 && (
        <div className="row" style={{ gap: 8, marginTop: 12,
                                      alignItems: "center",
                                      justifyContent: "center" }}>
          <button className="btn btn-sm" disabled={page <= 1}
                  onClick={() => setPage(1)}>«</button>
          <button className="btn btn-sm" disabled={page <= 1}
                  onClick={() => setPage(page - 1)}>‹</button>
          <span style={{ fontSize: ".85rem", color: "var(--ink-3)" }}>
            {page} / {meta.pages} — {meta.count}
          </span>
          <button className="btn btn-sm" disabled={page >= meta.pages}
                  onClick={() => setPage(page + 1)}>›</button>
          <button className="btn btn-sm" disabled={page >= meta.pages}
                  onClick={() => setPage(meta.pages)}>»</button>
        </div>
      )}

      <p style={{ marginTop: 10, fontSize: ".82rem", color: "var(--ink-3)" }}>
        {L("dedRecalc")}
      </p>
    </>
  );
}
