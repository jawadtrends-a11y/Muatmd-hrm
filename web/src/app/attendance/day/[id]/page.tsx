"use client";
/**
 * تفصيل يوم حضور (ق-185).
 *
 * ⚠️⚠️ **وثلاثة مساراتٍ كانت مبنيّةً بلا شاشة**: البصمات الخام،
 * والملخّص الشهريّ، **والتعديل اليدويّ** — كشفها الجرد.
 *
 * ⚠️ **والبصمات لا تُعدَّل ولا تُحذف**: **هي مصدر الحقيقة** —
 * والتعديل يقع على اليوم المحتسب، **يُعلَّم ويُنسب لفاعله**.
 */
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { apiGet, apiPut, qs, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcClock } from "@/components/Icons";

const T: Dict = {
  back: { ar: "← رجوع", en: "← Back" },
  title: { ar: "تفصيل اليوم", en: "Day details" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  punches: { ar: "البصمات الخام", en: "Raw punches" },
  punchHint: {
    ar: "⚠️ لا تُعدَّل ولا تُحذف — هي مصدر الحقيقة",
    en: "Read only — the source of truth",
  },
  time: { ar: "الوقت", en: "Time" },
  direction: { ar: "الاتجاه", en: "Direction" },
  source: { ar: "المصدر", en: "Source" },
  noPunches: { ar: "لا بصمات لهذا اليوم", en: "No punches" },
  computed: { ar: "المحتسب", en: "Computed" },
  firstIn: { ar: "أول دخول", en: "First in" },
  lastOut: { ar: "آخر خروج", en: "Last out" },
  late: { ar: "تأخير", en: "Late" },
  overtime: { ar: "إضافيّ محتسب", en: "Overtime" },
  approvedOt: { ar: "إضافيّ معتمد", en: "Approved OT" },
  minutes: { ar: "دقيقة", en: "min" },
  adjust: { ar: "تعديل يدويّ", en: "Manual adjustment" },
  adjustHint: {
    ar: "⚠️ يُعلَّم ويُنسب لفاعله — ولا تمحوه إعادة المعالجة",
    en: "Marked and attributed — survives reprocessing",
  },
  status: { ar: "الحالة", en: "Status" },
  note: { ar: "سبب التعديل", en: "Reason" },
  noteRequired: { ar: "اكتب سبب التعديل", en: "Reason required" },
  save: { ar: "حفظ التعديل", en: "Save" },
  saved: { ar: "حُفظ", en: "Saved" },
  adjustedBy: { ar: "عُدّل يدويًّا", en: "Manually adjusted" },
  noPermission: {
    ar: "التعديل يحتاج صلاحية «تعديل سجلات الحضور»",
    en: "Needs attendance.edit",
  },
};

const STATUSES = [
  ["present", "حاضر"], ["absent", "غائب"], ["leave", "إجازة"],
  ["holiday", "عطلة"], ["weekend", "راحة"],
];

type Punch = {
  id: number; punched_at: string; direction?: string;
  direction_label?: string; source?: string; source_label?: string;
};
type Day = {
  id: number; work_date: string; status: string; status_label: string;
  first_in: string | null; last_out: string | null;
  late_minutes: number; overtime_minutes: number;
  approved_overtime_minutes: number;
  is_manually_adjusted?: boolean; adjustment_note?: string;
};

function hhmm(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${
    String(d.getMinutes()).padStart(2, "0")}`;
}

export default function AttendanceDayPage() {
  const { L } = useT(T);
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const sp = useSearchParams();
  const dayId = params?.id;
  const empId = sp?.get("emp");
  const workDate = sp?.get("date");

  const [day, setDay] = useState<Day | null>(null);
  const [punches, setPunches] = useState<Punch[]>([]);
  const [perms, setPerms] = useState<Set<string>>(new Set());
  const [status, setStatus] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    if (!empId || !workDate) { setBusy(false); return; }
    setBusy(true);
    setErr("");
    try {
      const [w, days, p] = await Promise.all([
        apiGet<{ permissions: string[] }>("/me/workspace/")
          .catch(() => ({ permissions: [] })),
        apiGet<{ rows: Day[] }>(
          `/attendance/${empId}/days/${qs({ from: workDate,
                                            to: workDate })}`),
        apiGet<Punch[] | { rows: Punch[] }>(
          `/attendance/${empId}/punches/${qs({ from: workDate,
                                               to: workDate })}`)
          .catch(() => []),
      ]);
      setPerms(new Set(w.permissions || []));
      const d = days.rows?.[0] || null;
      setDay(d);
      setStatus(d?.status || "");
      setNote(d?.adjustment_note || "");
      setPunches(Array.isArray(p) ? p : (p.rows || []));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [empId, workDate]);

  useEffect(() => { load(); }, [load]);

  const canEdit = perms.has("attendance.edit");

  const save = async () => {
    // ⚠️ **ولا تعديلَ بلا سبب**: فمن يراجع بعد سنة **يحتاج معرفة
    // لماذا** (ق-80).
    if (!note.trim()) { setErr(L("noteRequired")); return; }
    setSaving(true);
    setErr("");
    setMsg("");
    try {
      await apiPut(`/attendance/days/${dayId}/adjust/`, {
        status, note: note.trim(),
      });
      setMsg(L("saved"));
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setSaving(false); }
  };

  if (busy) return (
    <div className="card" style={{ padding: 40, textAlign: "center",
                                   color: "var(--ink-3)" }}>
      {L("loading")}
    </div>
  );

  return (
    <div className="stack">
      <button className="btn btn-sm btn-ghost"
              onClick={() => router.back()}>
        {L("back")}
      </button>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && (
        <div className="card" style={{ borderColor: "var(--danger)",
                                       color: "var(--danger)" }}>
          <IcAlert size={17} /> {err}
        </div>
      )}

      {day && (
        <>
          <div className="card" style={{ padding: 20 }}>
            <div className="spread" style={{ marginBottom: 14 }}>
              <div className="row" style={{ gap: 10,
                                            alignItems: "center" }}>
                <IcClock size={20} />
                <h1 style={{ margin: 0, fontSize: "1.15rem" }}>
                  <span className="num">{day.work_date}</span>
                </h1>
              </div>
              <div className="row" style={{ gap: 8 }}>
                <span className="badge">{day.status_label}</span>
                {day.is_manually_adjusted && (
                  <span className="badge badge-warn">
                    {L("adjustedBy")}
                  </span>
                )}
              </div>
            </div>

            <div style={{
              display: "grid", gap: 14,
              gridTemplateColumns:
                "repeat(auto-fit, minmax(140px, 1fr))",
            }}>
              <Cell label={L("firstIn")} value={hhmm(day.first_in)} />
              <Cell label={L("lastOut")} value={hhmm(day.last_out)} />
              <Cell label={L("late")}
                    value={`${day.late_minutes} ${L("minutes")}`} />
              <Cell label={L("overtime")}
                    value={`${day.overtime_minutes} ${L("minutes")}`} />
              <Cell label={L("approvedOt")}
                    value={`${day.approved_overtime_minutes} ${
                      L("minutes")}`} />
            </div>
          </div>

          {/* ── البصمات الخام ── */}
          <div className="card" style={{ overflow: "hidden" }}>
            <div style={{ padding: "14px 18px 0" }}>
              <h3 style={{ margin: 0, fontSize: "1rem" }}>
                {L("punches")}
              </h3>
              <div className="muted" style={{ fontSize: ".78rem",
                                              marginTop: 4 }}>
                {L("punchHint")}
              </div>
            </div>

            {punches.length === 0 ? (
              <div style={{ padding: 28, textAlign: "center",
                            color: "var(--ink-3)" }}>
                {L("noPunches")}
              </div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: 110 }}>{L("time")}</th>
                    <th style={{ width: 120 }}>{L("direction")}</th>
                    <th>{L("source")}</th>
                  </tr>
                </thead>
                <tbody>
                  {punches.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <span className="num">{hhmm(p.punched_at)}</span>
                      </td>
                      <td>{p.direction_label || p.direction || "—"}</td>
                      <td className="muted">
                        {p.source_label || p.source || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* ── التعديل اليدويّ ── */}
          <div className="card" style={{ padding: 20 }}>
            <h3 style={{ margin: "0 0 4px", fontSize: "1rem" }}>
              {L("adjust")}
            </h3>
            <div className="muted" style={{ fontSize: ".78rem",
                                            marginBottom: 14 }}>
              {L("adjustHint")}
            </div>

            {!canEdit ? (
              <div className="muted" style={{ fontSize: ".85rem" }}>
                {L("noPermission")}
              </div>
            ) : (
              <>
                <div className="row" style={{ gap: 14,
                                              flexWrap: "wrap",
                                              alignItems: "flex-end" }}>
                  <label className="field" style={{ minWidth: 170 }}>
                    <span className="label">{L("status")}</span>
                    <select className="select" value={status}
                            onChange={(e) => setStatus(e.target.value)}>
                      {STATUSES.map(([v, l]) => (
                        <option key={v} value={v}>{l}</option>
                      ))}
                    </select>
                  </label>

                  <label className="field" style={{ flex: "1 1 280px" }}>
                    <span className="label">{L("note")}</span>
                    <input className="input" value={note}
                           onChange={(e) => setNote(e.target.value)} />
                  </label>
                </div>

                <button className="btn btn-primary"
                        style={{ marginTop: 16 }}
                        disabled={saving || !note.trim()}
                        onClick={save}>
                  {saving ? "…" : L("save")}
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}


function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="muted" style={{ fontSize: ".76rem",
                                      marginBottom: 3 }}>
        {label}
      </div>
      <div className="num">{value}</div>
    </div>
  );
}
