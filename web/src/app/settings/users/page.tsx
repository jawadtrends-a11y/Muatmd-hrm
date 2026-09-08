"use client";

/**
 * المستخدمون — إدارة حسابات الدخول وصلاحياتها.
 *
 * داخل الإعدادات لا في ملف الموظف: فهي إدارة وصول لا بيانات
 * موظفين. ولا يراها إلا من يملك إدارة الصلاحيات.
 */
import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcUsers } from "@/components/Icons";

const T: Dict = {
  title: { ar: "المستخدمون", en: "Users" },
  subtitle: {
    ar: "حسابات الدخول وصلاحياتها",
    en: "Login accounts and their permissions",
  },
  search: { ar: "بحث بالاسم أو الرقم", en: "Search by name or number" },
  no: { ar: "الرقم", en: "No." },
  name: { ar: "الموظف", en: "Employee" },
  dept: { ar: "الإدارة/القسم", en: "Department" },
  role: { ar: "الدور", en: "Role" },
  actions: { ar: "الإجراءات", en: "Actions" },
  details: { ar: "تفاصيل", en: "Details" },
  noAccount: { ar: "لا حساب دخول", en: "No login" },
  empty: { ar: "لا مستخدمين", en: "No users" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: {
    ar: "لا تملك صلاحية إدارة المستخدمين",
    en: "You cannot manage users",
  },
  total: { ar: "المجموع", en: "Total" },
  invite: { ar: "دعوة", en: "Invite" },
  inviteAll: { ar: "دعوة من لا حساب له", en: "Invite all without login" },
  inviting: { ar: "جارٍ الإرسال…", en: "Sending…" },
  inviteDone: { ar: "أُنشئت الدعوة", en: "Invitation created" },
  linkLabel: { ar: "رابط الدعوة — صالح سبعة أيام",
               en: "Invitation link — valid for seven days" },
  copy: { ar: "نسخ", en: "Copy" },
  copied: { ar: "نُسخ", en: "Copied" },
  mailSent: { ar: "وأُرسلت بالبريد إلى", en: "Also emailed to" },
  noMail: { ar: "لا بريد للموظف — انسخ الرابط وأرسله إليه",
            en: "No email on file — copy the link and send it" },
  close: { ar: "إغلاق", en: "Close" },
  bulkDone: { ar: "نتيجة الدعوة الجماعية", en: "Bulk invitation result" },
  okCount: { ar: "دُعي", en: "Invited" },
  skipCount: { ar: "تعذّر", en: "Skipped" },
};

type Row = {
  id: number;
  person_id: number;
  employee_no: string;
  email?: string;
  name_ar: string;
  name_en?: string;
  department?: string | null;
  username?: string | null;
  roles?: string[];
};

type InviteResult = {
  name?: string; url?: string; email?: string;
  email_sent?: boolean; error?: string;
};
type BulkResult = {
  counts?: { invited: number; skipped: number };
  skipped?: { name: string; detail: string }[];
  error?: string;
};

export default function UsersPage() {
  const { L, lang } = useT(T);
  const [rows, setRows] = useState<Row[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [perms, setPerms] = useState<string[]>([]);
  const [inviting, setInviting] = useState<number | null>(null);
  const [result, setResult] = useState<InviteResult | null>(null);
  const [bulk, setBulk] = useState<BulkResult | null>(null);
  const [copied, setCopied] = useState(false);

  const canInvite = perms.includes("employees.invite");
  const noLogin = rows.filter((r) => !r.username);

  const reload = () =>
    apiGet<Row[]>("/access/members/").then(setRows).catch(() => {});

  async function inviteOne(r: Row) {
    setInviting(r.person_id);
    try {
      const d = await apiPost<InviteResult>(
        `/employees/${r.person_id}/invite/`, {});
      setResult(d); setCopied(false); await reload();
    } catch (e) {
      setResult({ error: (e as ApiError).message } as InviteResult);
    } finally { setInviting(null); }
  }

  async function inviteAll() {
    setInviting(-1);
    try {
      const d = await apiPost<BulkResult>("/employees/invite-bulk/",
        { person_ids: noLogin.map((r) => r.person_id) });
      setBulk(d); await reload();
    } catch (e) {
      setBulk({ error: (e as ApiError).message } as BulkResult);
    } finally { setInviting(null); }
  }

  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((p) => setPerms(p.permissions || []))
      .catch(() => {});
    apiGet<Row[]>("/access/members/")
      .then((d) => { setRows(d); setBusy(false); })
      .catch((e: ApiError) => {
        setDenied(e.status === 403);
        setBusy(false);
      });
  }, []);

  const visible = q
    ? rows.filter((r) => r.name_ar.includes(q) || r.employee_no.includes(q))
    : rows;

  if (denied) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{L("noAccess")}</div>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        <div className="row" style={{ gap: 8 }}>
          {canInvite && noLogin.length > 0 && (
            <button className="btn btn-primary btn-sm" onClick={inviteAll}
                    disabled={inviting !== null}>
              {inviting === -1 ? L("inviting")
                : `${L("inviteAll")} (${noLogin.length})`}
            </button>
          )}
          <input className="input" style={{ maxWidth: 260 }}
            placeholder={L("search")} value={q}
            onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : visible.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <IcUsers size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <>
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ textAlign: "end" }}>{L("no")}</th>
                    <th>{L("name")}</th>
                    <th>{L("dept")}</th>
                    <th>{L("role")}</th>
                    <th style={{ width: 110 }}>{L("actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((r) => (
                    <tr key={r.id}>
                      <td style={{ textAlign: "end" }}>
                        <span className="num">{r.employee_no}</span>
                      </td>
                      <td className="truncate">
                        {(lang === "en" ? r.name_en : r.name_ar) || r.name_ar}
                        {!r.username && (
                          <span className="muted" style={{
                            fontSize: ".76rem", marginInlineStart: 8,
                          }}>
                            ({L("noAccount")})
                          </span>
                        )}
                      </td>
                      <td className="truncate muted">{r.department || "—"}</td>
                      <td className="truncate muted">
                        {(r.roles || []).join("، ") || "—"}
                      </td>
                      <td>
                        {r.username ? (
                          <Link href={`/settings/users/${r.id}`}
                            className="btn btn-sm">
                            {L("details")}
                          </Link>
                        ) : canInvite ? (
                          <button className="btn btn-sm btn-primary"
                                  onClick={() => inviteOne(r)}
                                  disabled={inviting !== null}>
                            {inviting === r.person_id
                              ? L("inviting") : L("invite")}
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="muted" style={{
              padding: "10px 14px", borderTop: "1px solid var(--line)",
              fontSize: ".85rem",
            }}>
              {L("total")}: <span className="num">{visible.length}</span>
            </div>
          </>
        )}
      </div>

      {result && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
          display: "grid", placeItems: "center", padding: 20, zIndex: 60,
        }} onClick={() => setResult(null)}>
          <div className="card" style={{ padding: 26, maxWidth: 520, width: "100%" }}
               onClick={(e) => e.stopPropagation()}>
            {result.error ? (
              <div style={{ color: "var(--danger)" }}>{result.error}</div>
            ) : (
              <>
                <h3 style={{ margin: "0 0 4px" }}>{L("inviteDone")}</h3>
                <div className="muted" style={{ fontSize: ".9rem" }}>
                  {result.name}
                </div>
                <div className="field" style={{ marginTop: 18 }}>
                  <label className="label">{L("linkLabel")}</label>
                  <div className="row" style={{ gap: 8 }}>
                    <input className="input" readOnly dir="ltr"
                           value={result.url || ""}
                           onFocus={(e) => e.currentTarget.select()} />
                    <button className="btn btn-sm" onClick={() => {
                      navigator.clipboard?.writeText(result.url || "");
                      setCopied(true);
                    }}>{copied ? L("copied") : L("copy")}</button>
                  </div>
                </div>
                <div className="muted" style={{ fontSize: ".85rem", marginTop: 12 }}>
                  {result.email_sent
                    ? `${L("mailSent")} ${result.email}`
                    : L("noMail")}
                </div>
              </>
            )}
            <button className="btn" style={{ marginTop: 20 }}
                    onClick={() => setResult(null)}>{L("close")}</button>
          </div>
        </div>
      )}

      {bulk && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
          display: "grid", placeItems: "center", padding: 20, zIndex: 60,
        }} onClick={() => setBulk(null)}>
          <div className="card" style={{ padding: 26, maxWidth: 560, width: "100%" }}
               onClick={(e) => e.stopPropagation()}>
            <h3 style={{ margin: "0 0 12px" }}>{L("bulkDone")}</h3>
            {bulk.error ? (
              <div style={{ color: "var(--danger)" }}>{bulk.error}</div>
            ) : (
              <>
                <div className="row" style={{ gap: 18 }}>
                  <div>{L("okCount")}:{" "}
                    <b className="num">{bulk.counts?.invited ?? 0}</b></div>
                  <div>{L("skipCount")}:{" "}
                    <b className="num">{bulk.counts?.skipped ?? 0}</b></div>
                </div>
                {(bulk.skipped || []).length > 0 && (
                  <div style={{ marginTop: 14, maxHeight: 240, overflowY: "auto" }}>
                    {(bulk.skipped || []).map((x, i) => (
                      <div key={i} style={{
                        padding: "8px 0", borderTop: "1px solid var(--line)",
                        fontSize: ".88rem",
                      }}>
                        <b>{x.name}</b>
                        <div className="muted">{x.detail}</div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
            <button className="btn" style={{ marginTop: 20 }}
                    onClick={() => setBulk(null)}>{L("close")}</button>
          </div>
        </div>
      )}
    </div>
  );
}
