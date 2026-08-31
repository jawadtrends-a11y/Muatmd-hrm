"use client";

/**
 * لوحة الحضور — ما يفتحه مدير الموارد كل صباح.
 *
 * وضعان: يومي (من حضر ومن تأخر) وشهري (الأساس الذي يقرؤه المسير).
 */
import { useEffect, useMemo, useState } from "react";

import { apiGet, qs, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcClock } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الحضور والانصراف", en: "Attendance" },
  daily: { ar: "يومي", en: "Daily" },
  monthly: { ar: "شهري", en: "Monthly" },
  date: { ar: "التاريخ", en: "Date" },
  month: { ar: "الشهر", en: "Month" },
  year: { ar: "السنة", en: "Year" },
  employee: { ar: "الموظف", en: "Employee" },
  department: { ar: "القسم", en: "Department" },
  status: { ar: "الحالة", en: "Status" },
  checkIn: { ar: "الحضور", en: "In" },
  checkOut: { ar: "الانصراف", en: "Out" },
  late: { ar: "التأخير (د)", en: "Late (m)" },
  overtime: { ar: "الإضافي (د)", en: "OT (m)" },
  approvedOt: { ar: "المعتمد (د)", en: "Approved (m)" },
  workedDays: { ar: "أيام العمل", en: "Worked" },
  absentDays: { ar: "الغياب", en: "Absent" },
  leaveDays: { ar: "الإجازات", en: "Leave" },
  otHours: { ar: "ساعات إضافية", en: "OT hours" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا سجلات", en: "No records" },
  error: { ar: "تعذّر التحميل", en: "Failed to load" },
  present: { ar: "حاضر", en: "Present" },
  absent: { ar: "غائب", en: "Absent" },
  partial: { ar: "جزئي", en: "Partial" },
  leave: { ar: "إجازة", en: "Leave" },
  holiday: { ar: "عطلة", en: "Holiday" },
  weekend: { ar: "راحة", en: "Weekend" },
  no_record: { ar: "لا سجل", en: "No record" },
  total: { ar: "الإجمالي", en: "Total" },
  hint: {
    ar: "الإضافي لا يدخل المسير إلا بعد اعتماد صريح",
    en: "Overtime enters payroll only after explicit approval",
  },
};

type DailyRow = {
  employment_id: number;
  employee_no: string;
  name_ar: string;
  department: string;
  status: string;
  status_label: string;
  first_in: string;
  last_out: string;
  late_minutes: number;
  worked_minutes: number;
  overtime_minutes: number;
  approved_overtime: number;
  day_id: number | null;
};

type MonthlyRow = {
  employment_id: number;
  employee_no: string;
  name_ar: string;
  department: string;
  worked_days: string;
  absent_days: string;
  leave_days: string;
  late_minutes: number;
  overtime_hours: string;
};

const TONE: Record<string, string> = {
  present: "badge-ok",
  partial: "badge-warn",
  absent: "badge-danger",
  leave: "badge-teal",
  holiday: "badge",
  weekend: "badge",
  no_record: "badge",
};

function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function AttendancePage() {
  const { L, lang } = useT(T);
  const [mode, setMode] = useState<"daily" | "monthly">("daily");
  const [day, setDay] = useState(today());
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);

  const [daily, setDaily] = useState<{ rows: DailyRow[]; counts: Record<string, number> } | null>(null);
  const [monthly, setMonthly] = useState<MonthlyRow[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setBusy(true);
    setError("");

    const url =
      mode === "daily"
        ? `/attendance/daily/${qs({ date: day })}`
        : `/attendance/monthly/${qs({ year, month })}`;

    apiGet<{ rows: DailyRow[] | MonthlyRow[]; counts?: Record<string, number> }>(url)
      .then((res) => {
        if (!alive) return;
        if (mode === "daily") {
          setDaily({ rows: (res.rows as DailyRow[]) || [], counts: res.counts || {} });
        } else {
          setMonthly((res.rows as MonthlyRow[]) || []);
        }
        setBusy(false);
      })
      .catch((e: ApiError) => {
        if (!alive) return;
        setError(e.message || L("error"));
        setBusy(false);
      });

    return () => { alive = false; };
    // L مستثناة: تتغيّر مرجعيًا في كل رسم فتعيد إطلاق الطلب
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, day, year, month]);

  const counts = daily?.counts ?? {};
  const cards = useMemo(
    () => Object.entries(counts).map(([k, v]) => ({ key: k, value: v })),
    [counts],
  );

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("hint")}
          </div>
        </div>
        <div className="row" style={{ gap: 6 }}>
          <button
            className={`btn btn-sm ${mode === "daily" ? "btn-primary" : ""}`}
            onClick={() => setMode("daily")}
          >
            <IcClock size={16} />
            {L("daily")}
          </button>
          <button
            className={`btn btn-sm ${mode === "monthly" ? "btn-primary" : ""}`}
            onClick={() => setMode("monthly")}
          >
            {L("monthly")}
          </button>
        </div>
      </div>

      {/* الفلاتر */}
      <div className="row" style={{ flexWrap: "wrap" }}>
        {mode === "daily" ? (
          <div className="field" style={{ maxWidth: 200 }}>
            <label className="label">{L("date")}</label>
            <input type="date" className="input" value={day}
              onChange={(e) => setDay(e.target.value)} />
          </div>
        ) : (
          <>
            <div className="field" style={{ maxWidth: 130 }}>
              <label className="label">{L("year")}</label>
              <input type="number" className="input" value={year}
                onChange={(e) => setYear(Number(e.target.value))} />
            </div>
            <div className="field" style={{ maxWidth: 130 }}>
              <label className="label">{L("month")}</label>
              <select className="select" value={month}
                onChange={(e) => setMonth(Number(e.target.value))}>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </>
        )}
      </div>

      {/* بطاقات الحالات — يومي فقط */}
      {mode === "daily" && cards.length > 0 && (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: 12,
        }}>
          {cards.map((c) => (
            <div key={c.key} className="card" style={{ padding: "14px 16px" }}>
              <div className="muted" style={{ fontSize: ".82rem", marginBottom: 4 }}>
                {L(c.key, c.key)}
              </div>
              <div style={{ fontSize: "1.45rem", fontWeight: 600 }}>
                <span className="num">{c.value}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* الجدول */}
      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : error ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--danger)" }}>
            <IcAlert size={22} />
            <div style={{ marginTop: 6 }}>{error}</div>
          </div>
        ) : mode === "daily" ? (
          <DailyTable rows={daily?.rows ?? []} L={L} lang={lang} />
        ) : (
          <MonthlyTable rows={monthly} L={L} />
        )}
      </div>
    </div>
  );
}


/* ══ الجدولان: خارج المكوّن الرئيسي — لا يُعرَّف مكوّن داخل مكوّن ══ */

type TableProps<R> = {
  rows: R[];
  L: (key: string, fallback?: string) => string;
  lang?: string;
};

function DailyTable({ rows, L }: TableProps<DailyRow>) {
  if (rows.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("empty")}
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="table">
        <colgroup>
          <col style={{ width: "110px" }} />
          <col style={{ width: "220px" }} />
          <col style={{ width: "150px" }} />
          <col style={{ width: "120px" }} />
          <col style={{ width: "90px" }} />
          <col style={{ width: "90px" }} />
          <col style={{ width: "100px" }} />
          <col style={{ width: "100px" }} />
          <col style={{ width: "110px" }} />
        </colgroup>
        <thead>
          <tr>
            <th style={{ textAlign: "end" }}>#</th>
            <th>{L("employee")}</th>
            <th>{L("department")}</th>
            <th>{L("status")}</th>
            <th style={{ textAlign: "end" }}>{L("checkIn")}</th>
            <th style={{ textAlign: "end" }}>{L("checkOut")}</th>
            <th style={{ textAlign: "end" }}>{L("late")}</th>
            <th style={{ textAlign: "end" }}>{L("overtime")}</th>
            <th style={{ textAlign: "end" }}>{L("approvedOt")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.employment_id}>
              <td style={{ textAlign: "end" }}>
                <span className="num">{r.employee_no}</span>
              </td>
              <td className="truncate">{r.name_ar}</td>
              <td className="truncate muted">{r.department || "—"}</td>
              <td>
                <span className={`badge ${TONE[r.status] || "badge"}`}>
                  {L(r.status, r.status_label)}
                </span>
              </td>
              <td style={{ textAlign: "end" }}>
                {r.first_in ? <span className="num">{r.first_in}</span> : "—"}
              </td>
              <td style={{ textAlign: "end" }}>
                {r.last_out ? <span className="num">{r.last_out}</span> : "—"}
              </td>
              <td style={{ textAlign: "end" }}>
                {r.late_minutes > 0 ? (
                  <span className="num" style={{ color: "var(--copper)" }}>
                    {r.late_minutes}
                  </span>
                ) : "—"}
              </td>
              <td style={{ textAlign: "end" }}>
                {r.overtime_minutes > 0
                  ? <span className="num">{r.overtime_minutes}</span> : "—"}
              </td>
              <td style={{ textAlign: "end" }}>
                {r.approved_overtime > 0 ? (
                  <span className="num" style={{ color: "var(--ok)" }}>
                    {r.approved_overtime}
                  </span>
                ) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MonthlyTable({ rows, L }: TableProps<MonthlyRow>) {
  if (rows.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("empty")}
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="table">
        <colgroup>
          <col style={{ width: "110px" }} />
          <col style={{ width: "230px" }} />
          <col style={{ width: "160px" }} />
          <col style={{ width: "110px" }} />
          <col style={{ width: "100px" }} />
          <col style={{ width: "110px" }} />
          <col style={{ width: "110px" }} />
          <col style={{ width: "130px" }} />
        </colgroup>
        <thead>
          <tr>
            <th style={{ textAlign: "end" }}>#</th>
            <th>{L("employee")}</th>
            <th>{L("department")}</th>
            <th style={{ textAlign: "end" }}>{L("workedDays")}</th>
            <th style={{ textAlign: "end" }}>{L("absentDays")}</th>
            <th style={{ textAlign: "end" }}>{L("leaveDays")}</th>
            <th style={{ textAlign: "end" }}>{L("late")}</th>
            <th style={{ textAlign: "end" }}>{L("otHours")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.employment_id}>
              <td style={{ textAlign: "end" }}>
                <span className="num">{r.employee_no}</span>
              </td>
              <td className="truncate">{r.name_ar}</td>
              <td className="truncate muted">{r.department || "—"}</td>
              <td style={{ textAlign: "end" }}>
                <span className="num">{r.worked_days}</span>
              </td>
              <td style={{ textAlign: "end" }}>
                {Number(r.absent_days) > 0 ? (
                  <span className="num" style={{ color: "var(--danger)" }}>
                    {r.absent_days}
                  </span>
                ) : <span className="num">0</span>}
              </td>
              <td style={{ textAlign: "end" }}>
                <span className="num">{r.leave_days}</span>
              </td>
              <td style={{ textAlign: "end" }}>
                {r.late_minutes > 0 ? (
                  <span className="num" style={{ color: "var(--copper)" }}>
                    {r.late_minutes}
                  </span>
                ) : "—"}
              </td>
              <td style={{ textAlign: "end" }}>
                <span className="num">{r.overtime_hours}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
