"use client";

/**
 * المستخدمون — إدارة حسابات الدخول وصلاحياتها.
 *
 * داخل الإعدادات لا في ملف الموظف: فهي إدارة وصول لا بيانات
 * موظفين. ولا يراها إلا من يملك إدارة الصلاحيات.
 */
import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet, ApiError } from "@/lib/api";
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
};

type Row = {
  id: number;
  employee_no: string;
  name_ar: string;
  department?: string | null;
  username?: string | null;
  roles?: string[];
};

export default function UsersPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Row[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
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
        <input className="input" style={{ maxWidth: 260 }}
          placeholder={L("search")} value={q}
          onChange={(e) => setQ(e.target.value)} />
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
                        {r.name_ar}
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
                        {r.username && (
                          <Link href={`/settings/users/${r.id}`}
                            className="btn btn-sm">
                            {L("details")}
                          </Link>
                        )}
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
    </div>
  );
}
