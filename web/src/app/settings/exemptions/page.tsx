"use client";
/**
 * الإعفاء من الحضور والانصراف (ق-104).
 *
 * عرضٌ وإلغاء — والإنشاء يمرّ بطلب معتمد لا بزرّ هنا: فإعفاء
 * موظف من البصمة قرار يوثَّق ويمرّ بمدير إدارته وموظف الموارد.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import { IcAlert, IcCheck, IcClock, IcUser } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الإعفاء من الحضور والانصراف", en: "Attendance exemptions" },
  subtitle: {
    ar: "من لا يُطالَب ببصمة — ولا يُعدّ غائبًا",
    en: "Employees not required to punch — never marked absent",
  },
  howTo: {
    ar: "يُضاف بطلب «إعفاء من البصمة» يعتمده مدير الإدارة ثم موظف الموارد",
    en: "Added via an exemption request approved by the department head then HR",
  },
  employee: { ar: "الموظف", en: "Employee" },
  dept: { ar: "الإدارة", en: "Department" },
  from: { ar: "من", en: "From" },
  to: { ar: "إلى", en: "To" },
  openEnded: { ar: "غير محدّدة", en: "Open-ended" },
  reason: { ar: "السبب", en: "Reason" },
  req: { ar: "الطلب", en: "Request" },
  state: { ar: "الحالة", en: "Status" },
  active: { ar: "ساري", en: "Active" },
  revoked: { ar: "ملغى", en: "Revoked" },
  revoke: { ar: "إلغاء الإعفاء", en: "Revoke" },
  confirmRevoke: {
    ar: "إلغاء هذا الإعفاء؟ سيعود الموظف مطالَبًا بالبصمة من اليوم.",
    en: "Revoke it? The employee must punch again from today.",
  },
  onlyActive: { ar: "السارية فقط", en: "Active only" },
  all: { ar: "الكل", en: "All" },
  empty: { ar: "لا إعفاءات", en: "No exemptions" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا تملك صلاحية عرض الإعفاءات", en: "Not permitted" },
  done: { ar: "أُلغي الإعفاء", en: "Revoked" },
};

type Row = {
  id: number;
  employee_no: string;
  name: string;
  department: string;
  start_date: string;
  end_date: string | null;
  reason: string;
  is_active: boolean;
  request_no: string;
};

export default function ExemptionsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Row[]>([]);
  const [perms, setPerms] = useState<string[]>([]);
  const [busy, setBusy] = useState(true);
  const [onlyActive, setOnlyActive] = useState(true);
  const [revokeId, setRevokeId] = useState<number | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const canView = perms.includes("attendance.view");
  const canEdit = perms.includes("attendance.edit");

  const load = useCallback(async (active: boolean) => {
    setBusy(true);
    try {
      const p = await apiGet<{ permissions: string[] }>("/me/workspace/");
      setPerms(p.permissions || []);
      setRows(await apiGet<Row[]>(
        `/attendance/exemptions/${active ? "?active=1" : ""}`));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(onlyActive); }, [onlyActive, load]);

  const revoke = async () => {
    if (!revokeId) return;
    try {
      await apiPost(`/attendance/exemptions/${revokeId}/revoke/`, {});
      setMsg(L("done"));
      setTimeout(() => setMsg(""), 3000);
      setRevokeId(null);
      await load(onlyActive);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
      setRevokeId(null);
    }
  };

  if (busy && rows.length === 0) return (
    <div className="card" style={{ padding: 40, textAlign: "center",
                                   color: "var(--ink-3)" }}>{L("loading")}</div>
  );

  if (!canView) return (
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
          {L("subtitle")}
        </div>
      </div>

      <div className="card" style={{ padding: "12px 16px",
                                     background: "var(--teal-soft)",
                                     borderColor: "var(--teal)" }}>
        <span style={{ fontSize: ".88rem" }}>{L("howTo")}</span>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="row" style={{ gap: 6 }}>
        <button className={`btn btn-sm ${onlyActive ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyActive(true)}>{L("onlyActive")}</button>
        <button className={`btn btn-sm ${!onlyActive ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyActive(false)}>{L("all")}</button>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>
            <IcUser size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("employee")}</th>
                  <th>{L("dept")}</th>
                  <th style={{ width: 120 }}>{L("from")}</th>
                  <th style={{ width: 130 }}>{L("to")}</th>
                  <th>{L("reason")}</th>
                  <th style={{ width: 90 }}>{L("state")}</th>
                  {canEdit && <th style={{ width: 130 }} />}
                </tr>
              </thead>
              <tbody>
                {rows.map((x) => (
                  <tr key={x.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{x.name}</div>
                      <div className="muted num" style={{ fontSize: ".76rem" }}>
                        {x.employee_no}
                        {x.request_no && ` · ${x.request_no}`}
                      </div>
                    </td>
                    <td className="truncate muted">{x.department || "—"}</td>
                    <td><span className="num">{x.start_date}</span></td>
                    <td>
                      {x.end_date
                        ? <span className="num">{x.end_date}</span>
                        : <span className="muted">{L("openEnded")}</span>}
                    </td>
                    <td className="truncate muted">{x.reason || "—"}</td>
                    <td>
                      <span className={x.is_active ? "badge badge-ok" : "badge"}>
                        {x.is_active ? L("active") : L("revoked")}
                      </span>
                    </td>
                    {canEdit && (
                      <td>
                        {x.is_active && (
                          <button className="btn btn-sm btn-danger"
                                  onClick={() => setRevokeId(x.id)}>
                            <IcClock size={13} /> {L("revoke")}
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={revokeId !== null}
        message={L("confirmRevoke")}
        tone="danger"
        onConfirm={revoke}
        onCancel={() => setRevokeId(null)}
      />
    </div>
  );
}
