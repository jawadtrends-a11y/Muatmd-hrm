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
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      pGet<PlatformUser>("/platform/auth/me").catch(() => null),
      pGet<{ accounts: Account[] }>("/platform/accounts/")
        .then((d) => d.accounts)
        .catch(() => [] as Account[]),
    ]).then(([u, a]) => {
      setUser(u);
      setRows(a);
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

  const mayImpersonate = can(user, "account.impersonate");

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
                        {mayImpersonate && (
                          <button className="btn btn-sm"
                            onClick={() => setDialog(r)}>
                            <IcUser size={15} />
                            {L("impersonate")}
                          </button>
                        )}
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
    </div>
  );
}
