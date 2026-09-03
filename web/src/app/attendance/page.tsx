"use client";

/**
 * لوحة الحضور — ما يفتحه مدير الموارد كل صباح.
 *
 * وضعان: يومي (من حضر ومن تأخر) وشهري (الأساس الذي يقرؤه المسير).
 */
import { useEffect, useMemo, useState } from "react";

import { apiGet, qs, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
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
  record: { ar: "سجل الحضور", en: "Attendance record" },
  joined: { ar: "تاريخ الالتحاق", en: "Joined" },
  from: { ar: "من", en: "From" },
  to: { ar: "إلى", en: "To" },
  thisMonth: { ar: "هذا الشهر", en: "This month" },
  lastMonth: { ar: "الشهر السابق", en: "Last month" },
  last3: { ar: "آخر 3 أشهر", en: "Last 3 months" },
  thisYear: { ar: "هذه السنة", en: "This year" },
  allTime: { ar: "منذ الالتحاق", en: "Since joining" },
  close: { ar: "إغلاق", en: "Close" },
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
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setBusy(true);
    setError("");

    const url =
      mode === "daily"
        ? `/attendance/daily/${qs({ date: day, page })}`
        : `/attendance/monthly/${qs({ year, month, page })}`;

    apiGet<{
      rows: DailyRow[] | MonthlyRow[];
      counts?: Record<string, number>;
      total?: number; pages?: number; page?: number;
    }>(url)
      .then((res) => {
        if (!alive) return;
        if (mode === "daily") {
          setDaily({ rows: (res.rows as DailyRow[]) || [], counts: res.counts || {} });
        } else {
          setMonthly((res.rows as MonthlyRow[]) || []);
        }
        setTotal(res.total ?? 0);
        setPages(res.pages ?? 1);
        if (res.page && res.page !== page) setPage(res.page);
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
  }, [mode, day, year, month, page]);

  // تغيير الفلتر يعيدنا للصفحة الأولى — وإلا بقينا على صفحة 7
  // لتاريخ فيه ثلاث صفحات فقط
  useEffect(() => { setPage(1); }, [mode, day, year, month]);

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
            <DateField value={day} onChange={setDay} />
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
          <>
            <DailyTable rows={daily?.rows ?? []} L={L} lang={lang}
              onPick={setPicked} />
            <div style={{ borderTop: "1px solid var(--line)" }}>
              <Pager page={page} pages={pages} total={total}
                onGo={setPage} L={L} />
            </div>
          </>
        ) : (
          <>
            <MonthlyTable rows={monthly} L={L} onPick={setPicked} />
            <div style={{ borderTop: "1px solid var(--line)" }}>
              <Pager page={page} pages={pages} total={total}
                onGo={setPage} L={L} />
            </div>
          </>
        )}
      </div>

      {/* سجل الموظف — يفتح بالنقر على اسمه في أي من الجدولين */}
      {picked !== null && (
        <EmployeeRecord
          employmentId={picked}
          initialFrom={mode === "daily"
            ? day.slice(0, 8) + "01"
            : `${year}-${String(month).padStart(2, "0")}-01`}
          initialTo={mode === "daily" ? day : ""}
          onClose={() => setPicked(null)}
          L={L}
        />
      )}
    </div>
  );
}


/* ══ الجدولان: خارج المكوّن الرئيسي — لا يُعرَّف مكوّن داخل مكوّن ══ */

type TableProps<R> = {
  rows: R[];
  L: (key: string, fallback?: string) => string;
  lang?: string;
  /** فتح سجل الموظف الكامل — الاسم قابل للنقر */
  onPick?: (employmentId: number) => void;
};

/* ══ سجل حضور موظف واحد (لوحة جانبية) ══ */

type DayRow = {
  id: number;
  work_date: string;
  status: string;
  status_label: string;
  first_in: string | null;
  last_out: string | null;
  late_minutes: number;
  overtime_minutes: number;
  approved_overtime_minutes: number;
};

function hhmm(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function EmployeeRecord({
  employmentId, initialFrom, initialTo, onClose, L,
}: {
  employmentId: number;
  initialFrom: string;
  initialTo: string;
  onClose: () => void;
  L: (k: string, f?: string) => string;
}) {
  const [from, setFrom] = useState(initialFrom);
  const [to, setTo] = useState(initialTo);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{
    name_ar: string; employee_no: string; join_date: string;
    rows: DayRow[]; total: number; pages: number;
  } | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setBusy(true);
    setError("");
    apiGet<{
      name_ar: string; employee_no: string; join_date: string;
      rows: DayRow[]; total: number; pages: number; page: number;
    }>(`/attendance/${employmentId}/days/${qs({ from, to, page })}`)
      .then((res) => {
        if (!alive) return;
        setData(res);
        if (res.page && res.page !== page) setPage(res.page);
        setBusy(false);
      })
      .catch((e: ApiError) => {
        if (!alive) return;
        setError(e.message || L("error"));
        setBusy(false);
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employmentId, from, to, page]);

  // تغيير الفترة يعيدنا للصفحة الأولى
  useEffect(() => { setPage(1); }, [from, to]);

  /** الأزرار السريعة تملأ الحقلين — ويبقيان قابلين للتعديل يدويًا */
  function quick(kind: string) {
    const n = new Date();
    const y = n.getFullYear();
    const m = n.getMonth();
    if (kind === "thisMonth") {
      setFrom(iso(new Date(y, m, 1)));
      setTo(iso(new Date(y, m + 1, 0)));
    } else if (kind === "lastMonth") {
      setFrom(iso(new Date(y, m - 1, 1)));
      setTo(iso(new Date(y, m, 0)));
    } else if (kind === "last3") {
      setFrom(iso(new Date(y, m - 2, 1)));
      setTo(iso(new Date(y, m + 1, 0)));
    } else if (kind === "thisYear") {
      setFrom(iso(new Date(y, 0, 1)));
      setTo(iso(new Date(y, 11, 31)));
    } else {
      setFrom(data?.join_date ?? "");
      setTo(iso(n));
    }
  }

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
        zIndex: 60, display: "flex", justifyContent: "flex-start",
      }}
      onClick={onClose}
    >
      <div
        className="card"
        style={{
          width: "100%", maxWidth: 760, height: "100%", borderRadius: 0,
          overflowY: "auto", padding: 0,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* الرأس */}
        <div className="spread" style={{
          padding: "16px 20px", borderBottom: "1px solid var(--line)",
          position: "sticky", top: 0, background: "var(--paper)", zIndex: 1,
        }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: "1.05rem" }}>
              {data?.name_ar ?? "…"}
            </div>
            <div className="muted" style={{ fontSize: ".85rem", marginTop: 2 }}>
              <span className="num">{data?.employee_no}</span>
              {data?.join_date && (
                <> · {L("joined")}: <span className="num">{data.join_date}</span></>
              )}
            </div>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={onClose}>
            {L("close")}
          </button>
        </div>

        {/* الفلتر */}
        <div className="stack" style={{
          padding: "14px 20px", gap: 10,
          borderBottom: "1px solid var(--line)",
        }}>
          <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
            {["thisMonth", "lastMonth", "last3", "thisYear", "allTime"].map((k) => (
              <button key={k} className="btn btn-sm" onClick={() => quick(k)}>
                {L(k)}
              </button>
            ))}
          </div>
          <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
            <div className="field" style={{ minWidth: 150 }}>
              <label className="label">{L("from")}</label>
              <DateField value={from} onChange={setFrom} />
            </div>
            <div className="field" style={{ minWidth: 150 }}>
              <label className="label">{L("to")}</label>
              <DateField value={to} onChange={setTo} />
            </div>
          </div>
        </div>

        {/* الجدول */}
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : error ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--danger)" }}>
            {error}
          </div>
        ) : (data?.rows.length ?? 0) === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("empty")}
          </div>
        ) : (
          <>
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ textAlign: "end" }}>{L("date")}</th>
                    <th>{L("status")}</th>
                    <th style={{ textAlign: "end" }}>{L("checkIn")}</th>
                    <th style={{ textAlign: "end" }}>{L("checkOut")}</th>
                    <th style={{ textAlign: "end" }}>{L("late")}</th>
                    <th style={{ textAlign: "end" }}>{L("approvedOt")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data!.rows.map((d) => (
                    <tr key={d.id}>
                      <td style={{ textAlign: "end" }}>
                        <span className="num">{d.work_date}</span>
                      </td>
                      <td>
                        <span className={`badge ${TONE[d.status] || "badge"}`}>
                          {d.status_label}
                        </span>
                      </td>
                      <td style={{ textAlign: "end" }}>
                        <span className="num">{hhmm(d.first_in)}</span>
                      </td>
                      <td style={{ textAlign: "end" }}>
                        <span className="num">{hhmm(d.last_out)}</span>
                      </td>
                      <td style={{ textAlign: "end" }}>
                        <span className="num" style={
                          d.late_minutes > 0 ? { color: "var(--copper)" } : undefined
                        }>
                          {d.late_minutes || "—"}
                        </span>
                      </td>
                      <td style={{ textAlign: "end" }}>
                        <span className="num">
                          {d.approved_overtime_minutes || "—"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ borderTop: "1px solid var(--line)" }}>
              <Pager page={page} pages={data!.pages} total={data!.total}
                onGo={setPage} L={L} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}


/* ══ مرقّم الصفحات ══ */

function Pager({
  page, pages, total, onGo, L,
}: {
  page: number; pages: number; total: number;
  onGo: (p: number) => void;
  L: (k: string, f?: string) => string;
}) {
  if (pages <= 1) return null;

  // نافذة من خمس صفحات حول الحالية، مع الأولى والأخيرة دائمًا
  const nums: number[] = [];
  const from = Math.max(1, Math.min(page - 2, pages - 4));
  const to = Math.min(pages, from + 4);
  for (let i = from; i <= to; i++) nums.push(i);

  const btn = (p: number, label?: string, active = false) => (
    <button
      key={label ?? p}
      className={`btn btn-sm ${active ? "btn-primary" : ""}`}
      disabled={active}
      onClick={() => onGo(p)}
      style={{ minWidth: 36 }}
    >
      <span className="num">{label ?? p}</span>
    </button>
  );

  return (
    <div className="spread" style={{ padding: "12px 14px", flexWrap: "wrap", gap: 8 }}>
      <div className="muted" style={{ fontSize: ".85rem" }}>
        {L("total")}: <span className="num">{total}</span>
      </div>
      <div className="row" style={{ gap: 5, flexWrap: "wrap" }}>
        {page > 1 && btn(page - 1, "‹")}
        {from > 1 && btn(1)}
        {from > 2 && <span className="muted" style={{ padding: "0 4px" }}>…</span>}
        {nums.map((p) => btn(p, undefined, p === page))}
        {to < pages - 1 && <span className="muted" style={{ padding: "0 4px" }}>…</span>}
        {to < pages && btn(pages)}
        {page < pages && btn(page + 1, "›")}
      </div>
    </div>
  );
}


function DailyTable({ rows, L, onPick }: TableProps<DailyRow>) {
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
              <td className="truncate">
                {onPick ? (
                  <button
                    onClick={() => onPick(r.employment_id)}
                    style={{
                      background: "none", border: "none", padding: 0,
                      color: "var(--teal)", fontWeight: 500,
                      cursor: "pointer", font: "inherit",
                    }}
                  >
                    {r.name_ar}
                  </button>
                ) : r.name_ar}
              </td>
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

function MonthlyTable({ rows, L, onPick }: TableProps<MonthlyRow>) {
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
              <td className="truncate">
                {onPick ? (
                  <button
                    onClick={() => onPick(r.employment_id)}
                    style={{
                      background: "none", border: "none", padding: 0,
                      color: "var(--teal)", fontWeight: 500,
                      cursor: "pointer", font: "inherit",
                    }}
                  >
                    {r.name_ar}
                  </button>
                ) : r.name_ar}
              </td>
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
