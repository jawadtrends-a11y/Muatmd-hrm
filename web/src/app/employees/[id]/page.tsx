"use client";

/**
 * ملف الموظف — ما يفتحه مدير الموارد يوميًا.
 *
 * تبويبات: البيانات · الراتب · الحضور · الإجازات · السلف والعهد ·
 * الوثائق · سجل العمليات (ق-44: السجل يُعرض في مكان التعديل).
 */
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { apiGet, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import {
  IcAlert, IcClock, IcDoc, IcLeave, IcPayroll, IcUser, IcWallet,
} from "@/components/Icons";

const T: Dict = {
  back: { ar: "رجوع", en: "Back" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا بيانات", en: "No data" },
  notFound: { ar: "الموظف غير موجود", en: "Employee not found" },
  // التبويبات
  profile: { ar: "البيانات", en: "Profile" },
  salary: { ar: "الراتب", en: "Salary" },
  attendance: { ar: "الحضور", en: "Attendance" },
  leaves: { ar: "الإجازات", en: "Leaves" },
  assets: { ar: "السلف والعهد", en: "Advances & Assets" },
  documents: { ar: "الوثائق", en: "Documents" },
  audit: { ar: "سجل العمليات", en: "Activity log" },
  // الحقول
  employeeNo: { ar: "الرقم الوظيفي", en: "Employee No." },
  idNumber: { ar: "رقم الهوية", en: "ID Number" },
  nationality: { ar: "الجنسية", en: "Nationality" },
  department: { ar: "القسم", en: "Department" },
  jobTitle: { ar: "المسمى الوظيفي", en: "Job Title" },
  branch: { ar: "الفرع", en: "Branch" },
  joinDate: { ar: "تاريخ المباشرة", en: "Join date" },
  serviceStart: { ar: "بداية الخدمة المحتسبة", en: "Service start" },
  manager: { ar: "المدير المباشر", en: "Direct manager" },
  status: { ar: "الحالة", en: "Status" },
  iban: { ar: "الآيبان", en: "IBAN" },
  paymentMethod: { ar: "طريقة الصرف", en: "Payment method" },
  // التسجيل النظامي
  registration: { ar: "التسجيل النظامي", en: "Statutory registration" },
  gosi: { ar: "التأمينات الاجتماعية", en: "GOSI" },
  mol: { ar: "قوى (وزارة الموارد)", en: "MOL" },
  wps: { ar: "حماية الأجور", en: "WPS" },
  registrationHint: {
    ar: "التوظيف مستقل عن التسجيل — موظف قائم قد لا يكون مسجّلًا بعد",
    en: "Employment is independent of registration",
  },
  // الراتب
  component: { ar: "المكوّن", en: "Component" },
  amount: { ar: "المبلغ", en: "Amount" },
  effectiveFrom: { ar: "ساري من", en: "Effective from" },
  grossMonthly: { ar: "إجمالي الراتب", en: "Gross monthly" },
  noSalary: { ar: "لا هيكل راتب", en: "No salary structure" },
  // عام
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
  registered: { ar: "مسجّل", en: "Registered" },
  notRegistered: { ar: "غير مسجّل", en: "Not registered" },
  soon: { ar: "قريبًا", en: "Coming soon" },
};

const TABS = ["profile", "salary", "attendance", "leaves",
              "assets", "documents", "audit"] as const;
type Tab = (typeof TABS)[number];

type Employee = {
  id: number;
  employee_no: string;
  name_ar: string;
  person_id: number;
  department: string;
  job_title: string;
  join_date: string;
  status: string;
  is_gosi_registered: boolean;
  is_mol_registered: boolean;
  include_in_wps: boolean;
  [k: string]: unknown;
};

function money(v: unknown) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                  maximumFractionDigits: 2 })
    : String(v ?? "—");
}


/* ══ صف بيان — خارج المكوّن الرئيسي ══ */

function Field({
  label, value, numeric,
}: {
  label: string;
  value: React.ReactNode;
  numeric?: boolean;
}) {
  return (
    <div className="spread" style={{
      padding: "9px 0", borderBottom: "1px solid var(--line)",
    }}>
      <span className="muted" style={{ fontSize: ".88rem" }}>{label}</span>
      <span style={{ fontWeight: 500 }}>
        {numeric && value ? <span className="num">{value}</span> : (value || "—")}
      </span>
    </div>
  );
}

/* ══ لوحة البيانات ══ */

function ProfilePanel({
  emp, L,
}: {
  emp: Employee;
  L: (k: string, f?: string) => string;
}) {
  const flag = (on: boolean) => (
    <span className={on ? "badge badge-ok" : "badge badge-warn"}>
      {on ? L("registered") : L("notRegistered")}
    </span>
  );

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
      gap: 16,
    }}>
      <div className="card" style={{ padding: 18 }}>
        <h3 style={{ fontSize: "1rem", marginBottom: 6 }}>{L("profile")}</h3>
        <Field label={L("employeeNo")} value={emp.employee_no} numeric />
        <Field label={L("department")} value={emp.department} />
        <Field label={L("jobTitle")} value={emp.job_title} />
        <Field label={L("joinDate")} value={emp.join_date} numeric />
        <Field label={L("status")}
          value={<span className="badge">{String(emp.status)}</span>} />
      </div>

      <div className="card" style={{ padding: 18 }}>
        <h3 style={{ fontSize: "1rem", marginBottom: 4 }}>
          {L("registration")}
        </h3>
        <div className="muted" style={{ fontSize: ".82rem", marginBottom: 8 }}>
          {L("registrationHint")}
        </div>
        <Field label={L("gosi")} value={flag(emp.is_gosi_registered)} />
        <Field label={L("mol")} value={flag(emp.is_mol_registered)} />
        <Field label={L("wps")} value={flag(emp.include_in_wps)} />
      </div>
    </div>
  );
}

/* ══ لوحة الراتب ══ */

type SalaryLine = { component: string; amount: string };
type Salary = {
  effective_from?: string;
  gross_monthly?: string;
  lines?: SalaryLine[];
};

function SalaryPanel({
  empId, L,
}: {
  empId: number;
  L: (k: string, f?: string) => string;
}) {
  const [data, setData] = useState<Salary | null>(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    apiGet<Salary>(`/employees/${empId}/salary/`)
      .then((d) => { setData(d); setBusy(false); })
      .catch(() => { setData(null); setBusy(false); });
  }, [empId]);

  if (busy) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("loading")}
      </div>
    );
  }

  if (!data || !data.lines || data.lines.length === 0) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("noSalary")}
      </div>
    );
  }

  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="spread" style={{ marginBottom: 14 }}>
        <span className="muted" style={{ fontSize: ".88rem" }}>
          {L("effectiveFrom")}:{" "}
          <span className="num">{data.effective_from}</span>
        </span>
        <span style={{ fontSize: "1.2rem", fontWeight: 600 }}>
          <span className="num">{money(data.gross_monthly)}</span>
        </span>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>{L("component")}</th>
            <th style={{ textAlign: "end" }}>{L("amount")}</th>
          </tr>
        </thead>
        <tbody>
          {data.lines.map((l, i) => (
            <tr key={i}>
              <td>{l.component}</td>
              <td style={{ textAlign: "end" }}>
                <span className="num">{money(l.amount)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ══ لوحة السجل (ق-44) ══ */

type AuditEntry = {
  id: number;
  action_label: string;
  actor: string;
  at: string;
  summary: string;
  changes: { field_label: string; from: unknown; to: unknown }[];
};

function AuditPanel({
  empId, L,
}: {
  empId: number;
  L: (k: string, f?: string) => string;
}) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    apiGet<{ entries: AuditEntry[] }>(`/audit/employment/${empId}/`)
      .then((d) => { setEntries(d.entries || []); setBusy(false); })
      .catch(() => { setEntries([]); setBusy(false); });
  }, [empId]);

  if (busy) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("loading")}
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("empty")}
      </div>
    );
  }

  return (
    <div className="stack" style={{ gap: 10 }}>
      {entries.map((e) => (
        <div key={e.id} className="card" style={{ padding: 14 }}>
          <div className="spread" style={{ marginBottom: 6 }}>
            <span className="badge">{e.action_label}</span>
            <span className="muted" style={{ fontSize: ".82rem" }}>
              {e.actor} · <span className="num">{e.at?.slice(0, 16)}</span>
            </span>
          </div>
          {e.summary && (
            <div style={{ fontSize: ".9rem" }}>{e.summary}</div>
          )}
          {e.changes.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {e.changes.map((c, i) => (
                <div key={i} className="muted" style={{ fontSize: ".85rem" }}>
                  {c.field_label}:{" "}
                  <span style={{ textDecoration: "line-through" }}>
                    {String(c.from ?? "—")}
                  </span>
                  {" ← "}
                  <span style={{ color: "var(--ink)" }}>
                    {String(c.to ?? "—")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}


/* ══ لوحة السلف والعهد ══ */

function ClearancePanel({
  empId, L,
}: {
  empId: number;
  L: (k: string, f?: string) => string;
}) {
  const [data, setData] = useState<{
    advances: { count: number; total_outstanding: string;
                advances: Record<string, string>[] };
    assets: { count: number; total_value: string;
              assets: Record<string, string>[] };
  } | null>(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    apiGet<typeof data>(`/employees/${empId}/clearance/`)
      .then((d) => { setData(d); setBusy(false); })
      .catch(() => { setData(null); setBusy(false); });
  }, [empId]);

  if (busy || !data) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {busy ? L("loading") : L("empty")}
      </div>
    );
  }

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
      gap: 16,
    }}>
      <div className="card" style={{ padding: 18 }}>
        <div className="spread" style={{ marginBottom: 12 }}>
          <h3 style={{ fontSize: "1rem" }}>السلف القائمة</h3>
          <span style={{ fontWeight: 600, color: "var(--danger)" }}>
            <span className="num">{money(data.advances.total_outstanding)}</span>
          </span>
        </div>
        {data.advances.count === 0 ? (
          <div className="muted" style={{ fontSize: ".88rem" }}>{L("empty")}</div>
        ) : (
          data.advances.advances.map((a, i) => (
            <div key={i} className="spread" style={{
              padding: "8px 0", borderBottom: "1px solid var(--line)",
            }}>
              <span className="num" style={{ fontSize: ".9rem" }}>
                {a.advance_no}
              </span>
              <span><span className="num">{money(a.outstanding)}</span></span>
            </div>
          ))
        )}
      </div>

      <div className="card" style={{ padding: 18 }}>
        <div className="spread" style={{ marginBottom: 12 }}>
          <h3 style={{ fontSize: "1rem" }}>العهد</h3>
          <span style={{ fontWeight: 600 }}>
            <span className="num">{money(data.assets.total_value)}</span>
          </span>
        </div>
        {data.assets.count === 0 ? (
          <div className="muted" style={{ fontSize: ".88rem" }}>{L("empty")}</div>
        ) : (
          data.assets.assets.map((a, i) => (
            <div key={i} className="spread" style={{
              padding: "8px 0", borderBottom: "1px solid var(--line)",
            }}>
              <span style={{ fontSize: ".9rem" }}>{a.name_ar}</span>
              <span><span className="num">{money(a.value)}</span></span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ══ الشاشة ══ */

export default function EmployeeDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { L } = useT(T);
  const empId = Number(params.id);

  const [emp, setEmp] = useState<Employee | null>(null);
  const [tab, setTab] = useState<Tab>("profile");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<Employee>(`/employees/${empId}/`)
      .then((d) => { setEmp(d); setBusy(false); })
      .catch((e: ApiError) => { setError(e.message); setBusy(false); });
  }, [empId]);

  if (busy) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("loading")}
      </div>
    );
  }

  if (error || !emp) {
    return (
      <div className="card" style={{
        padding: 32, textAlign: "center", color: "var(--danger)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{error || L("notFound")}</div>
      </div>
    );
  }

  const ICONS: Record<Tab, React.ComponentType<{ size?: number }>> = {
    profile: IcUser,
    salary: IcPayroll,
    attendance: IcClock,
    leaves: IcLeave,
    assets: IcWallet,
    documents: IcDoc,
    audit: IcDoc,
  };

  return (
    <div className="stack">
      <div>
        <button className="btn btn-sm btn-ghost"
          onClick={() => router.push("/employees")}>
          ← {L("back")}
        </button>
        <h1 style={{ marginTop: 8 }}>{emp.name_ar}</h1>
        <div className="muted" style={{ fontSize: ".9rem" }}>
          <span className="num">{emp.employee_no}</span>
          {emp.department ? ` · ${emp.department}` : ""}
          {emp.job_title ? ` · ${emp.job_title}` : ""}
        </div>
      </div>

      <div className="row" style={{ gap: 4, flexWrap: "wrap" }}>
        {TABS.map((t) => {
          const Icon = ICONS[t];
          return (
            <button key={t}
              className={`btn btn-sm ${tab === t ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setTab(t)}>
              <Icon size={16} />
              {L(t)}
            </button>
          );
        })}
      </div>

      {tab === "profile" && <ProfilePanel emp={emp} L={L} />}
      {tab === "salary" && <SalaryPanel empId={empId} L={L} />}
      {tab === "assets" && <ClearancePanel empId={empId} L={L} />}
      {tab === "audit" && <AuditPanel empId={empId} L={L} />}
      {["attendance", "leaves", "documents"].includes(tab) && (
        <div className="card" style={{
          padding: 36, textAlign: "center", color: "var(--ink-3)",
        }}>
          {L("soon")}
        </div>
      )}
    </div>
  );
}
