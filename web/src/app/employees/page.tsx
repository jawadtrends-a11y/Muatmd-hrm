"use client";

/**
 * شاشة الموظفين.
 *
 * ق-15: التوظيف مستقل عن التسجيل النظامي — الأعلام الثلاثة
 * تُعرض صراحةً فيرى مدير الموارد من سُجّل ومن لم يُسجّل.
 */
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

import DocList, { type Column, type Stat } from "@/components/DocList";
import { apiUpload, downloadFile, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";

const T: Dict = {
  title: { ar: "الموظفون", en: "Employees" },
  subtitle: {
    ar: "الملفات الوظيفية وحالة التسجيل النظامي",
    en: "Employment records and statutory registration",
  },
  active: { ar: "على رأس العمل", en: "Active" },
  leaving: { ar: "إنهاء قيد الإنجاز", en: "Leaving" },
  importBtn: { ar: "استيراد موظفين", en: "Import" },
  notMol: { ar: "غير مسجّل بقوى", en: "Not in MOL" },
  importTitle: { ar: "استيراد الموظفين", en: "Import employees" },
  step1: { ar: "١ — نزّل القالب وعبّئه", en: "1 — Download template" },
  step2: { ar: "٢ — ارفع الملفّ وراجع المعاينة", en: "2 — Upload" },
  download: { ar: "تنزيل القالب", en: "Download template" },
  pick: { ar: "اختر الملفّ", en: "Choose file" },
  checking: { ar: "جارٍ الفحص…", en: "Checking…" },
  valid: { ar: "صالح", en: "Valid" },
  invalid: { ar: "به خطأ", en: "With errors" },
  row: { ar: "السطر", en: "Row" },
  blocked: {
    ar: "⚠️ لا يُستورَد الملفّ حتى تُصلَح كل الأخطاء — فاستيرادٌ نصفُه ناقصٌ أسوأ من لا شيء",
    en: "All errors must be fixed first",
  },
  doImport: { ar: "تنفيذ الاستيراد", en: "Import now" },
  importedOk: { ar: "استُورد", en: "Imported" },
  employee: { ar: "موظفًا", en: "employees" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  all: { ar: "الكل", en: "All" },
  terminated: { ar: "منتهية خدمتهم", en: "Terminated" },
  suspended: { ar: "موقوفون", en: "Suspended" },
  emptyHint: {
    ar: "ابدأ بإضافة أول موظف",
    en: "Add your first employee",
  },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
};

type Employee = {
  id: number;
  employee_no: string;
  name_ar: string;
  department: string;
  job_title: string;
  join_date: string;
  status: string;
  is_gosi_registered: boolean;
  is_mol_registered: boolean;
  include_in_wps: boolean;
  /** ق-82: فصل معتمَد — الخدمة تنتهي بإتمام المخالصة */
  termination_pending_from?: string | null;
};

const STATUSES = ["active", "", "suspended", "terminated"] as const;

export default function EmployeesPage() {
  // ق-154: الاستيراد الجماعيّ
  const [importing, setImporting] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const router = useRouter();
  const { L } = useT(T);
  const [status, setStatus] = useState<string>("active");

  const flag = (on: boolean) => (
    <span className={on ? "badge badge-ok" : "badge"}>
      {on ? L("yes") : L("no")}
    </span>
  );

  const columns: Column<Employee>[] = [
    { key: "employee_no", label: { ar: "الرقم الوظيفي", en: "Employee No." },
      width: 120, numeric: true },
    { key: "name_ar", label: { ar: "الموظف", en: "Employee" }, width: 240 },
    { key: "department", label: { ar: "القسم", en: "Department" }, width: 150 },
    { key: "job_title", label: { ar: "المسمى الوظيفي", en: "Job Title" },
      width: 160 },
    { key: "join_date", label: { ar: "المباشرة", en: "Joined" },
      width: 115, numeric: true },
    { key: "gosi", label: { ar: "التأمينات", en: "GOSI" }, width: 95,
      render: (r) => flag(r.is_gosi_registered) },
    { key: "mol", label: { ar: "قوى", en: "MOL" }, width: 85,
      render: (r) => flag(r.is_mol_registered) },
    { key: "wps", label: { ar: "حماية الأجور", en: "WPS" }, width: 110,
      render: (r) => flag(r.include_in_wps) },
    { key: "status", label: { ar: "الحالة", en: "Status" }, width: 170,
      render: (r) => (
        <div className="row" style={{ gap: 5, flexWrap: "wrap" }}>
          <span className={
            r.status === "active" ? "badge badge-ok"
              : r.status === "terminated" ? "badge" : "badge badge-warn"
          }>
            {r.status === "active" ? L("active") : r.status === "terminated" ? L("terminated") : L("suspended")}
          </span>
          {/* ق-82: الفصل المعتمَد يفتح المخالصة ولا يُنهي الخدمة —
              فمن هو في طريقه للخروج يُعرف ومعاملاته تُنجز وهو نشط */}
          {r.termination_pending_from && (
            <span className="badge badge-danger"
              title={String(r.termination_pending_from)}>
              {L("leaving")}
            </span>
          )}
        </div>
      ) },
  ];

  const stats = (rows: Employee[]): Stat[] => [
    { label: { ar: "الموظفون", en: "Employees" }, value: rows.length },
    { label: { ar: "مسجّلون بالتأمينات", en: "GOSI registered" },
      value: rows.filter((r) => r.is_gosi_registered).length, tone: "ok" },
    { label: { ar: "في حماية الأجور", en: "In WPS" },
      value: rows.filter((r) => r.include_in_wps).length, tone: "ok" },
    { label: { ar: "غير مسجّلين بقوى", en: "Not in MOL" },
      value: rows.filter((r) => !r.is_mol_registered).length, tone: "warn" },
  ];

  const filterBar = (
    <div className="row" style={{ gap: 6 }}>
      {STATUSES.map((s) => (
        <button
          key={s || "all"}
          className={`btn btn-sm ${status === s ? "btn-primary" : ""}`}
          onClick={() => setStatus(s)}
        >
          {L(s === "" ? "all" : s)}
        </button>
      ))}
    </div>
  );

  return (
    <div className="stack">
      <div>
        <h1>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".9rem", marginTop: 2 }}>
          {L("subtitle")}
        </div>
      </div>

      <DocList<Employee>
        endpoint="/employees/"
        filters={{ status }}
        columns={columns}
        rowKey={(r) => r.id}
        stats={stats}
        filterBar={filterBar}
        searchFields={(r) =>
          `${r.employee_no} ${r.name_ar} ${r.department} ${r.job_title}`}
        actions={
          <button className="btn" onClick={() => setImporting(true)}>
            {L("importBtn")}
          </button>
        }
        cardView={(r) => (
          <>
            <div className="spread">
              <strong>{r.name_ar}</strong>
              <span className="muted num"
                    style={{ fontSize: ".78rem" }}>
                {r.employee_no}
              </span>
            </div>
            <div className="muted" style={{ fontSize: ".82rem",
                                            marginTop: 6 }}>
              {r.job_title || "—"}
            </div>
            <div className="muted" style={{ fontSize: ".8rem" }}>
              {r.department || "—"}
            </div>
            <div className="row" style={{ gap: 4, marginTop: 10,
                                          flexWrap: "wrap" }}>
              {r.is_gosi_registered && (
                <span className="badge badge-ok"
                      style={{ fontSize: ".68rem" }}>GOSI</span>
              )}
              {r.include_in_wps && (
                <span className="badge badge-ok"
                      style={{ fontSize: ".68rem" }}>WPS</span>
              )}
              {!r.is_mol_registered && (
                <span className="badge badge-warn"
                      style={{ fontSize: ".68rem" }}>
                  {L("notMol")}
                </span>
              )}
            </div>
          </>
        )}
        refreshKey={refreshKey}
        newHref="/employees/new"
        newLabel={{ ar: "موظف جديد", en: "New employee" }}
        onRowClick={(r) => router.push(`/employees/${r.id}`)}
        emptyHint={T.emptyHint}
      />

      {importing && (
        <ImportDialog L={L} onClose={() => setImporting(false)}
                      onDone={() => {
                        setImporting(false);
                        setRefreshKey((n) => n + 1);
                      }} />
      )}
    </div>
  );
}


/* ══ نافذة الاستيراد (ق-154) ══ */

function ImportDialog({ L, onClose, onDone }: {
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{
    total: number; valid: number; invalid: number;
    can_import: boolean;
    errors: { row: number; employee_no: string;
              errors: string[] }[];
    sample: { employee_no: string; name: string;
              join_date: string }[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const check = async (f: File) => {
    setFile(f); setBusy(true); setErr(""); setPreview(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      setPreview(await apiUpload("/employees/import/preview/", f,
                                 "file"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const run = async () => {
    if (!file) return;
    setBusy(true); setErr("");
    try {
      const out = await apiUpload<{ created: number }>(
        "/employees/import/execute/", file, "file");
      alert(`${L("importedOk")} ${out.created} ${L("employee")}`);
      onDone();
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
      <div className="card" style={{ padding: 24, maxWidth: 620,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("importTitle")}</h3>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="card" style={{ padding: 14, marginTop: 16,
                                       background: "var(--paper-2)" }}>
          <div style={{ fontWeight: 500, fontSize: ".88rem" }}>
            {L("step1")}
          </div>
          <button className="btn btn-sm" style={{ marginTop: 8 }}
                  onClick={() => downloadFile(
                    "/employees/import/template/")}>
            {L("download")}
          </button>
        </div>

        <div className="card" style={{ padding: 14, marginTop: 12,
                                       background: "var(--paper-2)" }}>
          <div style={{ fontWeight: 500, fontSize: ".88rem" }}>
            {L("step2")}
          </div>
          <input ref={fileRef} type="file" accept=".csv,text/csv"
                 style={{ display: "none" }}
                 onChange={(e) => e.target.files?.[0]
                   && check(e.target.files[0])} />
          <button className="btn btn-sm" style={{ marginTop: 8 }}
                  disabled={busy}
                  onClick={() => fileRef.current?.click()}>
            {busy ? L("checking") : (file?.name || L("pick"))}
          </button>
        </div>

        {preview && (
          <div style={{ marginTop: 16 }}>
            <div className="row" style={{ gap: 20 }}>
              <div style={{ textAlign: "center" }}>
                <div className="muted" style={{ fontSize: ".76rem" }}>
                  {L("valid")}
                </div>
                <div className="num" style={{ fontSize: "1.4rem",
                                              color: "var(--ok)" }}>
                  {preview.valid}
                </div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div className="muted" style={{ fontSize: ".76rem" }}>
                  {L("invalid")}
                </div>
                <div className="num" style={{ fontSize: "1.4rem",
                  color: preview.invalid ? "var(--danger)"
                                         : undefined }}>
                  {preview.invalid}
                </div>
              </div>
            </div>

            {/* ⚠️ والأخطاء كلّها تُعرض — فلا يُكرَّر الرفع عشرًا */}
            {preview.errors.length > 0 && (
              <>
                <div style={{ background: "var(--copper-soft)",
                              color: "var(--copper)",
                              padding: "10px 13px",
                              borderRadius: "var(--radius-sm)",
                              fontSize: ".82rem", lineHeight: 1.9,
                              marginTop: 12 }}>
                  {L("blocked")}
                </div>
                <div style={{ maxHeight: 240, overflowY: "auto",
                              marginTop: 10 }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th style={{ width: 70 }}>{L("row")}</th>
                        <th style={{ width: 110 }}>#</th>
                        <th>—</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.errors.map((e, i) => (
                        <tr key={i}>
                          <td><span className="num">{e.row}</span></td>
                          <td>
                            <span className="num"
                                  style={{ fontSize: ".8rem" }}>
                              {e.employee_no}
                            </span>
                          </td>
                          <td style={{ fontSize: ".82rem",
                                       color: "var(--danger)" }}>
                            {e.errors.join(" · ")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          {preview?.can_import && (
            <button className="btn btn-primary" disabled={busy}
                    onClick={run}>
              {busy ? "…" : `${L("doImport")} (${preview.valid})`}
            </button>
          )}
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}
