"use client";

/**
 * قائمة الحسابات (ق-46).
 *
 * ملخص لا بيانات: عدد الموظفين وحالة الاشتراك — بلا رواتب.
 * الدخول للبيانات عبر الانتحال بخطوة صريحة.
 */
import { useEffect, useState } from "react";

import { pGet, pPost, can, AdminError, type PlatformUser } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcSearch, IcUser } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الحسابات", en: "Accounts" },
  subtitle: {
    ar: "ملخص الحسابات — الدخول للبيانات عبر جلسة دعم فني",
    en: "Account summaries — data access via support session",
  },
  search: { ar: "بحث…", en: "Search…" },
  account: { ar: "الحساب", en: "Account" },
  companies: { ar: "الشركات", en: "Companies" },
  employees: { ar: "الموظفون", en: "Employees" },
  plan: { ar: "الباقة", en: "Plan" },
  state: { ar: "الحالة", en: "State" },
  daysLeft: { ar: "المتبقي", en: "Days left" },
  unpaid: { ar: "فواتير معلّقة", en: "Unpaid" },
  impersonate: { ar: "دخول للدعم", en: "Support access" },
  activate: { ar: "تفعيل", en: "Activate" },
  extend: { ar: "تمديد", en: "Extend" },
  activateTitle: { ar: "تفعيل اشتراك يدويًّا", en: "Activate manually" },
  activateHint: {
    ar: "للشركات التي تدفع بتحويل بنكي — يُفعَّل بلا مرور بالبوابة",
    en: "For bank-transfer customers — no gateway involved",
  },
  extendTitle: { ar: "تمديد الاشتراك", en: "Extend subscription" },
  extendHint: {
    ar: "يمدّد التجربة أو المهلة إلى تاريخ تختاره",
    en: "Extends trial or grace to a chosen date",
  },
  fPlan: { ar: "الباقة", en: "Plan" },
  fCycle: { ar: "الدورة", en: "Cycle" },
  fMonthly: { ar: "شهري", en: "Monthly" },
  fAnnual: { ar: "سنوي", en: "Annual" },
  fEmployees: { ar: "عدد الموظفين المتفق عليه", en: "Agreed employees" },
  fStart: { ar: "بداية الفترة", en: "Period start" },
  fUntil: { ar: "حتى تاريخ", en: "Until" },
  fNote: { ar: "ملاحظة", en: "Note" },
  fCustomPrice: { ar: "سعر خاص (اختياري)", en: "Custom price (optional)" },
  go: { ar: "تنفيذ", en: "Apply" },
  cancel2: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا حسابات", en: "No accounts" },
  total: { ar: "الإجمالي", en: "Total" },
  reason: { ar: "سبب الدخول", en: "Reason" },
  reasonHint: {
    ar: "يُسجَّل مع الجلسة ويظهر في سجل العمليات",
    en: "Logged with the session",
  },
  asRole: { ar: "بدور", en: "As role" },
  fullAccess: { ar: "بكامل الصلاحيات", en: "Full access" },
  start: { ar: "بدء الجلسة", en: "Start session" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  warning: {
    ar: "ستدخل حساب العميل — كل تعديل يُسجَّل باسمك ويظهر له",
    en: "Every change is logged under your name",
  },
  sandbox: { ar: "تجريبي", en: "Sandbox" },
  noSub: { ar: "بلا اشتراك", en: "No subscription" },
};

type Account = {
  account_id: number;
  slug: string;
  name: string;
  is_sandbox: boolean;
  companies: number;
  employees: number;
  unpaid_invoices: number;
  subscription: {
    state: string | null;
    state_label: string;
    plan: string | null;
    days_left: number | null;
  };
};

const STATE_TONE: Record<string, string> = {
  trial: "badge-teal",
  active: "badge-ok",
  grace: "badge-warn",
  past_due: "badge-warn",
  read_only: "badge",
  cancelled: "badge-danger",
};

function ImpersonateDialog({
  account, L, onStart, onClose, busy,
}: {
  account: Account;
  L: (k: string, f?: string) => string;
  onStart: (reason: string, asRole: string) => void;
  onClose: () => void;
  busy: boolean;
}) {
  const [reason, setReason] = useState("");
  const [asRole, setAsRole] = useState("");

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.5)",
      display: "grid", placeItems: "center", zIndex: 60, padding: 20,
    }}>
      <div className="card" style={{ width: "100%", maxWidth: 420, padding: 24 }}>
        <h2 style={{ fontSize: "1.1rem", marginBottom: 6 }}>
          {L("impersonate")}
        </h2>
        <div style={{ fontWeight: 500, marginBottom: 14 }}>{account.name}</div>

        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 12px", borderRadius: "var(--radius-sm)",
          fontSize: ".87rem", marginBottom: 16,
          display: "flex", gap: 8, alignItems: "flex-start",
        }}>
          <IcAlert size={17} />
          {L("warning")}
        </div>

        <div className="stack">
          <div className="field">
            <label className="label">{L("reason")}</label>
            <input className="input" value={reason} autoFocus
              onChange={(e) => setReason(e.target.value)} />
            <div className="hint">{L("reasonHint")}</div>
          </div>

          <div className="field">
            <label className="label">{L("asRole")}</label>
            <select className="select" value={asRole}
              onChange={(e) => setAsRole(e.target.value)}>
              <option value="">{L("fullAccess")}</option>
              <option value="hr_manager">مدير الموارد البشرية</option>
              <option value="hr_staff">موظف موارد بشرية</option>
              <option value="employee">موظف</option>
            </select>
          </div>

          <div className="row">
            <button className="btn btn-primary" disabled={busy || !reason.trim()}
              onClick={() => onStart(reason.trim(), asRole)}>
              {L("start")}
            </button>
            <button className="btn btn-ghost" onClick={onClose}>
              {L("cancel")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


export default function AccountsPage() {
  const { L } = useT(T);
  const [user, setUser] = useState<PlatformUser | null>(null);
  const [rows, setRows] = useState<Account[]>([]);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(true);
  const [dialog, setDialog] = useState<Account | null>(null);
  const [acting, setActing] = useState(false);
  const [actDialog, setActDialog] = useState<Account | null>(null);
  const [extDialog, setExtDialog] = useState<Account | null>(null);
  const [plans, setPlans] = useState<{ id: number; code: string;
                                       name_ar: string }[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      pGet<PlatformUser>("/platform/auth/me").catch(() => null),
      pGet<{ accounts: Account[] }>("/platform/accounts/")
        .then((d) => d.accounts)
        .catch(() => [] as Account[]),
      pGet<{ plans: { id: number; code: string; name_ar: string }[] }>(
        "/platform/plans/").then((d) => d.plans).catch(() => []),
    ]).then(([u, a, p]) => {
      setUser(u);
      setRows(a);
      setPlans(p);
      setBusy(false);
    });
  }, []);

  const visible = search.trim()
    ? rows.filter((r) =>
        `${r.name} ${r.slug}`.toLowerCase().includes(search.toLowerCase()))
    : rows;

  async function startSession(reason: string, asRole: string) {
    if (!dialog) return;
    setActing(true);
    try {
      await pPost(`/platform/accounts/${dialog.account_id}/impersonate`, {
        reason, as_role: asRole,
      });
      setDialog(null);
      location.reload();
    } catch (e) {
      setError((e as AdminError).message);
    } finally {
      setActing(false);
    }
  }

  async function reload() {
    const d = await pGet<{ accounts: Account[] }>("/platform/accounts/")
      .catch(() => ({ accounts: [] as Account[] }));
    setRows(d.accounts);
  }

  async function doActivate(body: Record<string, unknown>) {
    if (!actDialog) return;
    setActing(true); setError("");
    try {
      // ق-46: العملية غير قابلة للتراجع، فتُرسل بتأكيد صريح
      await pPost(`/platform/accounts/${actDialog.account_id}/activate/`,
                  { ...body, confirm: true });
      setActDialog(null);
      await reload();
    } catch (e) {
      setError((e as AdminError).message);
    } finally { setActing(false); }
  }

  async function doExtend(body: Record<string, unknown>) {
    if (!extDialog) return;
    setActing(true); setError("");
    try {
      await pPost(`/platform/accounts/${extDialog.account_id}/extend/`,
                  { ...body, confirm: true });
      setExtDialog(null);
      await reload();
    } catch (e) {
      setError((e as AdminError).message);
    } finally { setActing(false); }
  }

  const mayImpersonate = can(user, "account.impersonate");
  const mayWrite = can(user, "account.write");

  return (
    <div className="stack">
      <div>
        <h1>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("subtitle")}
        </div>
      </div>

      {error && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
        }}>
          {error}
        </div>
      )}

      <div style={{ position: "relative", maxWidth: 340 }}>
        <span style={{
          position: "absolute", insetInlineStart: 11, top: 10,
          color: "var(--ink-3)", pointerEvents: "none",
        }}>
          <IcSearch size={17} />
        </span>
        <input className="input" style={{ paddingInlineStart: 36 }}
          placeholder={L("search")} value={search}
          onChange={(e) => setSearch(e.target.value)} />
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : visible.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("empty")}
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <colgroup>
                <col style={{ width: "240px" }} />
                <col style={{ width: "90px" }} />
                <col style={{ width: "100px" }} />
                <col style={{ width: "150px" }} />
                <col style={{ width: "130px" }} />
                <col style={{ width: "90px" }} />
                <col style={{ width: "110px" }} />
                <col style={{ width: "150px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th>{L("account")}</th>
                  <th style={{ textAlign: "end" }}>{L("companies")}</th>
                  <th style={{ textAlign: "end" }}>{L("employees")}</th>
                  <th>{L("plan")}</th>
                  <th>{L("state")}</th>
                  <th style={{ textAlign: "end" }}>{L("daysLeft")}</th>
                  <th style={{ textAlign: "end" }}>{L("unpaid")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => {
                  const s = r.subscription;
                  return (
                    <tr key={r.account_id}>
                      <td>
                        <div style={{ fontWeight: 500 }}>{r.name}</div>
                        <div className="muted" style={{ fontSize: ".8rem" }}>
                          {r.slug}
                          {r.is_sandbox && (
                            <span className="badge" style={{
                              marginInlineStart: 6, fontSize: ".72rem",
                            }}>
                              {L("sandbox")}
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ textAlign: "end" }}>
                        <span className="num">{r.companies}</span>
                      </td>
                      <td style={{ textAlign: "end" }}>
                        <span className="num">{r.employees}</span>
                      </td>
                      <td className="muted">{s.plan || "—"}</td>
                      <td>
                        <span className={
                          `badge ${STATE_TONE[s.state || ""] || "badge"}`}>
                          {s.state_label || L("noSub")}
                        </span>
                      </td>
                      <td style={{ textAlign: "end" }}>
                        {s.days_left != null ? (
                          <span className="num" style={{
                            color: s.days_left <= 5 ? "var(--copper)" : undefined,
                          }}>
                            {s.days_left}
                          </span>
                        ) : "—"}
                      </td>
                      <td style={{ textAlign: "end" }}>
                        {r.unpaid_invoices > 0 ? (
                          <span className="badge badge-warn">
                            <span className="num">{r.unpaid_invoices}</span>
                          </span>
                        ) : "—"}
                      </td>
                      <td style={{ textAlign: "end" }}>
                        <div className="row" style={{ gap: 5,
                                                      justifyContent: "flex-end" }}>
                          {mayWrite && (
                            <>
                              <button className="btn btn-sm"
                                onClick={() => { setActDialog(r); setError(""); }}>
                                {L("activate")}
                              </button>
                              <button className="btn btn-sm"
                                onClick={() => { setExtDialog(r); setError(""); }}>
                                {L("extend")}
                              </button>
                            </>
                          )}
                          {mayImpersonate && (
                            <button className="btn btn-sm"
                              onClick={() => setDialog(r)}>
                              <IcUser size={15} />
                              {L("impersonate")}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {!busy && visible.length > 0 && (
        <div className="muted" style={{ fontSize: ".85rem" }}>
          {L("total")}: <span className="num">{visible.length}</span>
        </div>
      )}

      {dialog && (
        <ImpersonateDialog account={dialog} L={L} onStart={startSession}
          onClose={() => setDialog(null)} busy={acting} />
      )}

      {actDialog && (
        <ActivateDialog account={actDialog} plans={plans} L={L}
          onApply={doActivate} onClose={() => setActDialog(null)}
          busy={acting} />
      )}

      {extDialog && (
        <ExtendDialog account={extDialog} L={L} onApply={doExtend}
          onClose={() => setExtDialog(null)} busy={acting} />
      )}
    </div>
  );
}


/* ══ تفعيل يدويّ (ق-48) ══ */

function ActivateDialog({
  account, plans, L, onApply, onClose, busy,
}: {
  account: Account;
  plans: { id: number; code: string; name_ar: string }[];
  L: (k: string, f?: string) => string;
  onApply: (b: Record<string, unknown>) => void;
  onClose: () => void;
  busy: boolean;
}) {
  const [planCode, setPlanCode] = useState(plans[0]?.code || "");
  const [cycle, setCycle] = useState("monthly");
  const [employees, setEmployees] = useState(String(account.employees || 1));
  const [start, setStart] = useState(new Date().toISOString().slice(0, 10));
  const [price, setPrice] = useState("");
  const [note, setNote] = useState("");

  return (
    <Overlay onClose={onClose}>
      <h3 style={{ margin: 0 }}>{L("activateTitle")}</h3>
      <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
        {account.name} — {L("activateHint")}
      </div>

      <div className="stack" style={{ gap: 12, marginTop: 16 }}>
        <label className="field">
          <span className="muted" style={{ fontSize: ".85rem" }}>
            {L("fPlan")}
          </span>
          <select className="select" value={planCode}
                  onChange={(e) => setPlanCode(e.target.value)}>
            {plans.map((p) => (
              <option key={p.id} value={p.code}>{p.name_ar}</option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="muted" style={{ fontSize: ".85rem" }}>
            {L("fCycle")}
          </span>
          <select className="select" value={cycle}
                  onChange={(e) => setCycle(e.target.value)}>
            <option value="monthly">{L("fMonthly")}</option>
            <option value="annual">{L("fAnnual")}</option>
          </select>
        </label>

        <label className="field">
          <span className="muted" style={{ fontSize: ".85rem" }}>
            {L("fEmployees")}
          </span>
          <input className="input" type="number" min={1} value={employees}
                 onChange={(e) => setEmployees(e.target.value)} />
        </label>

        <label className="field">
          <span className="muted" style={{ fontSize: ".85rem" }}>
            {L("fStart")}
          </span>
          <input className="input" type="date" value={start} dir="ltr"
                 onChange={(e) => setStart(e.target.value)} />
        </label>

        <label className="field">
          <span className="muted" style={{ fontSize: ".85rem" }}>
            {L("fCustomPrice")}
          </span>
          <input className="input" value={price} dir="ltr"
                 onChange={(e) => setPrice(e.target.value)} />
        </label>

        <label className="field">
          <span className="muted" style={{ fontSize: ".85rem" }}>
            {L("fNote")}
          </span>
          <input className="input" value={note}
                 onChange={(e) => setNote(e.target.value)} />
        </label>
      </div>

      <div className="row" style={{ gap: 8, marginTop: 18 }}>
        <button className="btn btn-primary" disabled={busy || !planCode}
                onClick={() => onApply({
                  plan_code: planCode, cycle,
                  employees: Number(employees) || 1,
                  period_start: start,
                  custom_price: price || undefined,
                  note,
                })}>
          {busy ? "…" : L("go")}
        </button>
        <button className="btn" onClick={onClose}>{L("cancel2")}</button>
      </div>
    </Overlay>
  );
}


/* ══ تمديد (ق-48) ══ */

function ExtendDialog({
  account, L, onApply, onClose, busy,
}: {
  account: Account;
  L: (k: string, f?: string) => string;
  onApply: (b: Record<string, unknown>) => void;
  onClose: () => void;
  busy: boolean;
}) {
  const plus = new Date();
  plus.setDate(plus.getDate() + 14);
  const [until, setUntil] = useState(plus.toISOString().slice(0, 10));
  const [note, setNote] = useState("");

  return (
    <Overlay onClose={onClose}>
      <h3 style={{ margin: 0 }}>{L("extendTitle")}</h3>
      <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
        {account.name} — {L("extendHint")}
      </div>

      <div className="stack" style={{ gap: 12, marginTop: 16 }}>
        <label className="field">
          <span className="muted" style={{ fontSize: ".85rem" }}>
            {L("fUntil")}
          </span>
          <input className="input" type="date" value={until} dir="ltr"
                 onChange={(e) => setUntil(e.target.value)} />
        </label>
        <label className="field">
          <span className="muted" style={{ fontSize: ".85rem" }}>
            {L("fNote")}
          </span>
          <input className="input" value={note}
                 onChange={(e) => setNote(e.target.value)} />
        </label>
      </div>

      <div className="row" style={{ gap: 8, marginTop: 18 }}>
        <button className="btn btn-primary" disabled={busy || !until}
                onClick={() => onApply({ until, note })}>
          {busy ? "…" : L("go")}
        </button>
        <button className="btn" onClick={onClose}>{L("cancel2")}</button>
      </div>
    </Overlay>
  );
}


/* ══ غلاف النوافذ ══ */

function Overlay({ children, onClose }: {
  children: React.ReactNode; onClose: () => void;
}) {
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 420,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}
