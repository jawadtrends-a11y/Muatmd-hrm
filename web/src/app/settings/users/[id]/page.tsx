"use client";

/**
 * صفحة المستخدم — معلومات حسابه وصلاحياته (ق-67 وق-78).
 *
 * الصلاحية تحمل مداها في اسمها، فمدير الحساب يقرأ الجملة ويشغّل
 * المفتاح بلا خطوة ثانية. والموروث من الدور مميّز عن الاستثناء
 * الشخصي، فيعرف ما غيّره بيده.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { apiGet, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcUser } from "@/components/Icons";

const T: Dict = {
  back: { ar: "← المستخدمون", en: "← Users" },
  account: { ar: "معلومات الحساب", en: "Account" },
  permissions: { ar: "الصلاحيات", en: "Permissions" },
  permHint: {
    ar: "الصلاحيات الخاصة بالمستخدم — والمظلّلة موروثة من دوره",
    en: "User permissions — highlighted ones come from their role",
  },
  search: { ar: "بحث", en: "Search" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  saved: { ar: "حُفظت الصلاحيات", en: "Permissions saved" },
  inherited: { ar: "من الدور", en: "From role" },
  added: { ar: "مُضافة", en: "Added" },
  removed: { ar: "منزوعة", en: "Removed" },
  employeeNo: { ar: "الرقم الوظيفي", en: "Employee no." },
  roles: { ar: "الدور", en: "Role" },
  owner: { ar: "مالك الحساب", en: "Account owner" },
  ownerHint: {
    ar: "مالك الحساب يملك كل الصلاحيات ولا تُنزع منه",
    en: "The account owner holds all permissions",
  },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  scopesTitle: {
    ar: "أنواع الطلبات التي يقرّر فيها",
    en: "Request types they decide on",
  },
  scopesAll: {
    ar: "بلا تخصيص — يقرّر في كل الأنواع",
    en: "No restriction — decides on all types",
  },
  scopesSome: {
    ar: "يتابع كل الطلبات ويقرّر في المحدَّدة وحدها",
    en: "Follows all requests, decides only on the selected",
  },
  saveScopes: { ar: "حفظ التخصيص", en: "Save assignment" },
  scopesSaved: { ar: "حُفظ التخصيص", en: "Assignment saved" },
  noAccess: { ar: "لا تملك هذه الصلاحية", en: "Not permitted" },
};

const MODULES: Record<string, { ar: string; en: string }> = {
  account: { ar: "الحساب والشركات", en: "Account" },
  org: { ar: "الهيكل التنظيمي", en: "Organization" },
  employees: { ar: "الموظفون", en: "Employees" },
  attendance: { ar: "الحضور والانصراف", en: "Attendance" },
  leaves: { ar: "الإجازات", en: "Leaves" },
  requests: { ar: "الطلبات", en: "Requests" },
  payroll: { ar: "الرواتب", en: "Payroll" },
  compliance: { ar: "الامتثال", en: "Compliance" },
  access: { ar: "الصلاحيات", en: "Access" },
};

type Perm = {
  key: string;
  name_ar: string;
  granted: boolean;
  inherited: boolean;
  is_override: boolean;
};

type ScopeType = { code: string; name_ar: string; assigned: boolean };


type Data = {
  employment_id: number;
  employee_no: string;
  name_ar: string;
  roles: string[];
  is_account_owner: boolean;
  modules: { module: string; permissions: Perm[] }[];
};

export default function UserPage() {
  const { L, lang } = useT(T);
  const params = useParams();
  const id = params?.id as string;

  const [tab, setTab] = useState<"account" | "permissions">("account");
  /** ق-74: أنواع الطلبات التي يعتمدها — بلا تخصيص يعتمد الكل */
  const [scopes, setScopes] = useState<ScopeType[]>([]);
  const [scopeOn, setScopeOn] = useState<Set<string>>(new Set());
  const [savingScopes, setSavingScopes] = useState(false);
  /** ق-76: المدير العام يرى ولا يعدّل — فالزر يختفي */
  const [canEdit, setCanEdit] = useState(false);
  const [data, setData] = useState<Data | null>(null);
  const [on, setOn] = useState<Set<string>>(new Set());
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const [denied, setDenied] = useState(false);

  const load = useCallback(() => {
    apiGet<Data>(`/access/members/${id}/permissions/`)
      .then((d) => {
        setData(d);
        setOn(new Set(d.modules.flatMap((m) =>
          m.permissions.filter((p) => p.granted).map((p) => p.key))));
        setBusy(false);
      })
      .catch((e: ApiError) => {
        setDenied(e.status === 403 || e.status === 404);
        setBusy(false);
      });
  }, [id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((d) => setCanEdit((d.permissions || []).includes("access.manage")))
      .catch(() => setCanEdit(false));
    apiGet<{ types: ScopeType[] }>(
      `/access/members/${id}/approver-scopes/`)
      .then((d) => {
        setScopes(d.types || []);
        setScopeOn(new Set((d.types || [])
          .filter((t) => t.assigned).map((t) => t.code)));
      })
      .catch(() => setScopes([]));
  }, [id]);

  async function saveScopes() {
    setSavingScopes(true);
    try {
      await apiPut(`/access/members/${id}/approver-scopes/`,
                   { types: [...scopeOn] });
      setToast(L("scopesSaved"));
    } catch (e) {
      setToast((e as ApiError).message);
    } finally {
      setSavingScopes(false);
      setTimeout(() => setToast(""), 4000);
    }
  }

  async function save() {
    setSaving(true);
    try {
      await apiPut(`/access/members/${id}/permissions/`,
                   { permissions: [...on] });
      setToast(L("saved"));
      load();
    } catch (e) {
      setToast((e as ApiError).message);
    } finally {
      setSaving(false);
      setTimeout(() => setToast(""), 4000);
    }
  }

  if (busy) {
    return (
      <div className="card" style={{
        padding: 40, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("loading")}
      </div>
    );
  }

  if (denied || !data) {
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
      <Link href="/settings/users" className="muted"
        style={{ fontSize: ".88rem" }}>
        {L("back")}
      </Link>

      <div className="row" style={{ gap: 16, alignItems: "flex-start" }}>
        {/* ══ بطاقة المستخدم والتبويبات ══ */}
        <div className="card" style={{ padding: 0, width: 260, flexShrink: 0 }}>
          <div style={{ padding: 18, borderBottom: "1px solid var(--line)" }}>
            <div className="row" style={{ gap: 10 }}>
              <span style={{
                width: 44, height: 44, borderRadius: "50%",
                background: "var(--teal-soft)", color: "var(--teal)",
                display: "grid", placeItems: "center", flexShrink: 0,
              }}>
                <IcUser size={22} />
              </span>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600 }} className="truncate">
                  {data.name_ar}
                </div>
                <div className="muted num" style={{ fontSize: ".8rem" }}>
                  {data.employee_no}
                </div>
              </div>
            </div>
          </div>
          {(["account", "permissions"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} style={{
              display: "block", width: "100%", textAlign: "start",
              padding: "12px 18px", border: "none", cursor: "pointer",
              font: "inherit", fontWeight: tab === t ? 600 : 500,
              color: tab === t ? "var(--teal)" : "var(--ink-2)",
              background: tab === t ? "var(--teal-soft)" : "transparent",
              borderInlineStartWidth: 3, borderInlineStartStyle: "solid",
              borderInlineStartColor: tab === t ? "var(--teal)" : "transparent",
            }}>
              {L(t)}
            </button>
          ))}
        </div>

        {/* ══ المحتوى ══ */}
        <div className="grow" style={{ minWidth: 0 }}>
          {tab === "account" ? (
            <div className="card" style={{ padding: 20 }}>
              <h3 style={{ fontSize: "1rem", marginBottom: 14 }}>
                {L("account")}
              </h3>
              <div className="stack" style={{ gap: 12 }}>
                <div className="spread">
                  <span className="muted">{L("employeeNo")}</span>
                  <span className="num">{data.employee_no}</span>
                </div>
                <div className="spread">
                  <span className="muted">{L("roles")}</span>
                  <span>{data.roles.join("، ") || "—"}</span>
                </div>
                {data.is_account_owner && (
                  <div className="spread">
                    <span className="muted">{L("owner")}</span>
                    <span className="badge badge-teal">✓</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="card" style={{ padding: 0, overflow: "hidden" }}>
              <div className="spread" style={{
                padding: "14px 18px", borderBottom: "1px solid var(--line)",
              }}>
                <div>
                  <h3 style={{ fontSize: "1rem" }}>{L("permissions")}</h3>
                  <div className="muted" style={{ fontSize: ".82rem" }}>
                    {L("permHint")}
                  </div>
                </div>
                {toast && <span className="badge badge-teal">{toast}</span>}
              </div>

              {data.is_account_owner ? (
                <div style={{
                  padding: 28, textAlign: "center", color: "var(--ink-3)",
                }}>
                  {L("ownerHint")}
                </div>
              ) : (
                <>
                  <div style={{ padding: "12px 18px" }}>
                    <input className="input" placeholder={L("search")}
                      value={q} onChange={(e) => setQ(e.target.value)} />
                  </div>

                  <div style={{ maxHeight: 520, overflowY: "auto" }}>
                    {data.modules.map((m) => {
                      const perms = q
                        ? m.permissions.filter((p) => p.name_ar.includes(q))
                        : m.permissions;
                      if (perms.length === 0) return null;
                      const label = MODULES[m.module];
                      return (
                        <div key={m.module}>
                          <div style={{
                            padding: "9px 18px", fontWeight: 600,
                            fontSize: ".85rem", color: "var(--teal)",
                            background: "var(--paper-2)",
                          }}>
                            {label ? (lang === "en" ? label.en : label.ar)
                                   : m.module}
                          </div>
                          {perms.map((p) => {
                            const isOn = on.has(p.key);
                            return (
                              <label key={p.key} className="spread" style={{
                                padding: "11px 18px", cursor: "pointer",
                                borderBottom: "1px solid var(--line)",
                              }}>
                                <span style={{ fontSize: ".9rem" }}>
                                  {p.name_ar}
                                  {p.inherited && (
                                    <span className="muted" style={{
                                      fontSize: ".72rem",
                                      marginInlineStart: 8,
                                    }}>
                                      · {L("inherited")}
                                    </span>
                                  )}
                                  {!p.inherited && isOn && (
                                    <span style={{
                                      fontSize: ".72rem", color: "var(--teal)",
                                      marginInlineStart: 8,
                                    }}>
                                      · {L("added")}
                                    </span>
                                  )}
                                  {p.inherited && !isOn && (
                                    <span style={{
                                      fontSize: ".72rem",
                                      color: "var(--danger)",
                                      marginInlineStart: 8,
                                    }}>
                                      · {L("removed")}
                                    </span>
                                  )}
                                </span>
                                <input type="checkbox" checked={isOn}
                                  disabled={!canEdit}
                                  onChange={() => setOn((s) => {
                                    const n = new Set(s);
                                    if (n.has(p.key)) n.delete(p.key);
                                    else n.add(p.key);
                                    return n;
                                  })}
                                  style={{ width: 18, height: 18,
                                           accentColor: "var(--teal)",
                                           cursor: "pointer" }} />
                              </label>
                            );
                          })}
                        </div>
                      );
                    })}
                  </div>

                  {/* ق-74: أنواع الطلبات التي يقرّر فيها.
                      والطلب يظهر له في الحالين — فالمتابعة حق
                      الجميع، والقرار مسؤولية مَن كُلّف. */}
                  {scopes.length > 0 && (
                    <div style={{ borderTop: "1px solid var(--line)" }}>
                      <div style={{
                        padding: "12px 18px", background: "var(--paper-2)",
                      }}>
                        <div style={{
                          fontWeight: 600, fontSize: ".9rem",
                          color: "var(--teal)",
                        }}>
                          {L("scopesTitle")}
                        </div>
                        <div className="muted" style={{ fontSize: ".78rem" }}>
                          {scopeOn.size === 0 ? L("scopesAll")
                            : L("scopesSome")}
                        </div>
                      </div>

                      <div style={{ maxHeight: 240, overflowY: "auto" }}>
                        {scopes.map((t) => (
                          <label key={t.code} className="spread" style={{
                            padding: "9px 18px", cursor: "pointer",
                            borderBottom: "1px solid var(--line)",
                          }}>
                            <span style={{ fontSize: ".88rem" }}>
                              {t.name_ar}
                            </span>
                            <input type="checkbox"
                              checked={scopeOn.has(t.code)}
                              disabled={!canEdit}
                              onChange={() => setScopeOn((v) => {
                                const n = new Set(v);
                                if (n.has(t.code)) n.delete(t.code);
                                else n.add(t.code);
                                return n;
                              })}
                              style={{ width: 17, height: 17,
                                       accentColor: "var(--teal)",
                                       cursor: "pointer" }} />
                          </label>
                        ))}
                      </div>

                      <div style={{ padding: "10px 18px" }}>
                        {canEdit && (
                        <button className="btn btn-sm btn-primary"
                          disabled={savingScopes} onClick={saveScopes}>
                          {savingScopes ? L("saving") : L("saveScopes")}
                        </button>
                        )}
                      </div>
                    </div>
                  )}

                  <div style={{
                    padding: "12px 18px", borderTop: "1px solid var(--line)",
                  }}>
                    {canEdit && (
                    <button className="btn btn-primary" disabled={saving}
                      onClick={save}>
                      <IcCheck size={17} />
                      {saving ? L("saving") : L("save")}
                    </button>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
