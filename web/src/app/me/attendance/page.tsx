"use client";

/** حضوري — سجل الموظف عن نفسه (ق-58). */
import { useEffect, useState } from "react";

import { apiGet, qs } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcClock } from "@/components/Icons";

const T: Dict = {
  title: { ar: "حضوري", en: "My attendance" },
  month: { ar: "الشهر", en: "Month" },
  year: { ar: "السنة", en: "Year" },
  date: { ar: "التاريخ", en: "Date" },
  status: { ar: "الحالة", en: "Status" },
  checkIn: { ar: "الحضور", en: "In" },
  checkOut: { ar: "الانصراف", en: "Out" },
  late: { ar: "التأخير (د)", en: "Late (m)" },
  overtime: { ar: "الإضافي (د)", en: "OT (m)" },
  approved: { ar: "المعتمد (د)", en: "Approved" },
  note: { ar: "ملاحظة", en: "Note" },
  present: { ar: "حاضر", en: "Present" },
  absent: { ar: "غائب", en: "Absent" },
  leave: { ar: "إجازة", en: "Leave" },
  weekend: { ar: "راحة", en: "Weekend" },
  holiday: { ar: "عطلة", en: "Holiday" },
  partial: { ar: "جزئي", en: "Partial" },
  not_scheduled: { ar: "غير مجدول", en: "Not scheduled" },
  workedHours: { ar: "ساعات العمل", en: "Worked hours" },
  otHours: { ar: "الإضافي المعتمد", en: "Approved OT" },
  totalLate: { ar: "إجمالي التأخير", en: "Total late" },
  minutes: { ar: "دقيقة", en: "min" },
  days: { ar: "يوم", en: "days" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا سجلات لهذا الشهر", en: "No records" },
  adjusted: { ar: "معدّل", en: "Adjusted" },
  fixHint: {
    ar: "لتصحيح بصمة، قدّم طلبًا من «خدماتي»",
    en: "To fix a punch, submit a request",
  },
};

type Day = {
  date: string; status: string; status_label: string;
  first_in: string; last_out: string;
  late_minutes: number; worked_minutes: number;
  overtime_minutes: number; approved_overtime: number;
  adjusted: boolean; note: string;
};

type Data = {
  employee_no: string;
  totals: Record<string, number | string>;
  days: Day[];
};

const TONE: Record<string, string> = {
  present: "badge-ok", partial: "badge-warn", absent: "badge-danger",
  leave: "badge-teal", weekend: "badge", holiday: "badge",
  not_scheduled: "badge",
};

export default function MyAttendancePage() {
  const { L } = useT(T);
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [data, setData] = useState<Data | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setBusy(true);
    apiGet<Data>(`/me/attendance/${qs({ year, month })}`)
      .then((d) => { if (alive) { setData(d); setBusy(false); } })
      .catch((e) => {
        if (alive) { setError((e as Error).message); setBusy(false); }
      });
    return () => { alive = false; };
  }, [year, month]);

  const t = data?.totals ?? {};

  return (
    <div className="stack">
      <div>
        <h1>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("fixHint")}
        </div>
      </div>

      <div className="row" style={{ flexWrap: "wrap" }}>
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
      </div>

      {data && (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 12,
        }}>
          {[
            { key: "present", label: L("present"), tone: "var(--ok)" },
            { key: "absent", label: L("absent"), tone: "var(--danger)" },
            { key: "workedHours", label: L("workedHours"),
              value: t.worked_hours },
            { key: "totalLate", label: L("totalLate"),
              value: t.late_minutes, suffix: L("minutes"),
              tone: Number(t.late_minutes) > 0 ? "var(--copper)" : undefined },
            { key: "otHours", label: L("otHours"), value: t.overtime_hours },
          ].map((c) => (
            <div key={c.key} className="card" style={{ padding: "14px 16px" }}>
              <div className="muted" style={{ fontSize: ".82rem", marginBottom: 4 }}>
                {c.label}
              </div>
              <div style={{
                fontSize: "1.35rem", fontWeight: 600,
                color: c.tone || "var(--ink)",
              }}>
                <span className="num">
                  {c.value ?? t[c.key] ?? 0}
                </span>
                {c.suffix && (
                  <span className="muted" style={{ fontSize: ".8rem" }}>
                    {" "}{c.suffix}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : error ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--danger)" }}>
            <IcAlert size={20} />
            <div style={{ marginTop: 6 }}>{error}</div>
          </div>
        ) : !data || data.days.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <IcClock size={24} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <colgroup>
                <col style={{ width: "130px" }} />
                <col style={{ width: "120px" }} />
                <col style={{ width: "100px" }} />
                <col style={{ width: "100px" }} />
                <col style={{ width: "100px" }} />
                <col style={{ width: "100px" }} />
                <col style={{ width: "110px" }} />
                <col />
              </colgroup>
              <thead>
                <tr>
                  <th style={{ textAlign: "end" }}>{L("date")}</th>
                  <th>{L("status")}</th>
                  <th style={{ textAlign: "end" }}>{L("checkIn")}</th>
                  <th style={{ textAlign: "end" }}>{L("checkOut")}</th>
                  <th style={{ textAlign: "end" }}>{L("late")}</th>
                  <th style={{ textAlign: "end" }}>{L("overtime")}</th>
                  <th style={{ textAlign: "end" }}>{L("approved")}</th>
                  <th>{L("note")}</th>
                </tr>
              </thead>
              <tbody>
                {data.days.map((d) => (
                  <tr key={d.date}>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{d.date}</span>
                    </td>
                    <td>
                      <span className={`badge ${TONE[d.status] || "badge"}`}>
                        {L(d.status, d.status_label)}
                      </span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      {d.first_in ? <span className="num">{d.first_in}</span> : "—"}
                    </td>
                    <td style={{ textAlign: "end" }}>
                      {d.last_out ? <span className="num">{d.last_out}</span> : "—"}
                    </td>
                    <td style={{ textAlign: "end" }}>
                      {d.late_minutes > 0 ? (
                        <span className="num" style={{ color: "var(--copper)" }}>
                          {d.late_minutes}
                        </span>
                      ) : "—"}
                    </td>
                    <td style={{ textAlign: "end" }}>
                      {d.overtime_minutes > 0
                        ? <span className="num">{d.overtime_minutes}</span> : "—"}
                    </td>
                    <td style={{ textAlign: "end" }}>
                      {d.approved_overtime > 0 ? (
                        <span className="num" style={{ color: "var(--ok)" }}>
                          {d.approved_overtime}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="muted truncate" style={{ fontSize: ".85rem" }}>
                      {d.adjusted && (
                        <span className="badge badge-warn"
                          style={{ marginInlineEnd: 6, fontSize: ".72rem" }}>
                          {L("adjusted")}
                        </span>
                      )}
                      {d.note}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
