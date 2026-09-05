"use client";

/**
 * الورديات — أوقات الدوام وأيامه وفترات السماح.
 *
 * والوردية المُسندة تُعطَّل لا تُحذف: حذفها يترك موظفين بلا دوام
 * محدَّد فتُقاس بصماتهم بلا مرجع.
 */
import { useCallback, useEffect, useState } from "react";

import { apiDelete, apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import { IcAlert, IcCheck, IcClock, IcPlus, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الورديات", en: "Shifts" },
  subtitle: {
    ar: "أوقات الدوام وأيامه وفترات السماح",
    en: "Working hours, days and grace periods",
  },
  add: { ar: "وردية جديدة", en: "New shift" },
  code: { ar: "الرمز", en: "Code" },
  name: { ar: "الاسم", en: "Name" },
  from: { ar: "من", en: "From" },
  to: { ar: "إلى", en: "To" },
  breakM: { ar: "الاستراحة (د)", en: "Break (min)" },
  graceIn: { ar: "سماح الدخول (د)", en: "Grace in (min)" },
  graceOut: { ar: "سماح الخروج (د)", en: "Grace out (min)" },
  days: { ar: "أيام الدوام", en: "Working days" },
  crosses: { ar: "تعبر منتصف الليل", en: "Crosses midnight" },
  flexible: { ar: "مرنة", en: "Flexible" },
  active: { ar: "نشطة", en: "Active" },
  inactive: { ar: "معطّلة", en: "Inactive" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا ورديات", en: "No shifts" },
  noAccess: {
    ar: "لا تملك صلاحية إدارة الورديات",
    en: "You cannot manage shifts",
  },
  confirmDelete: {
    ar: "حذف الوردية؟ إن كانت مُسندة لموظفين فستُعطَّل بدل حذفها.",
    en: "Delete? If assigned to employees it is deactivated instead.",
  },
  codeHint: {
    ar: "الرمز لا يُعدَّل — الإسنادات تشير إليه",
    en: "The code cannot change — assignments reference it",
  },
  sun: { ar: "أحد", en: "Sun" },
  mon: { ar: "إثنين", en: "Mon" },
  tue: { ar: "ثلاثاء", en: "Tue" },
  wed: { ar: "أربعاء", en: "Wed" },
  thu: { ar: "خميس", en: "Thu" },
  fri: { ar: "جمعة", en: "Fri" },
  sat: { ar: "سبت", en: "Sat" },
};

const DAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

type Shift = {
  id: number;
  code: string;
  name_ar: string;
  start_time: string;
  end_time: string;
  break_minutes: number;
  grace_in_minutes: number;
  grace_out_minutes: number;
  working_days: number[];
  crosses_midnight: boolean;
  is_flexible: boolean;
  is_active: boolean;
};

export default function ShiftsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Shift[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [askDel, setAskDel] = useState<number | null>(null);

  const load = useCallback(() => {
    apiGet<Shift[]>("/attendance/shifts/")
      .then((d) => { setRows(d); setBusy(false); })
      .catch((e: ApiError) => {
        setDenied(e.status === 403);
        setBusy(false);
      });
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((d) =>
        setCanEdit((d.permissions || []).includes("attendance.shifts")))
      .catch(() => setCanEdit(false));
  }, []);

  function startNew() {
    setDraft({
      code: "", name_ar: "", start_time: "08:00", end_time: "16:00",
      break_minutes: 60, grace_in_minutes: 0, grace_out_minutes: 0,
      working_days: [0, 1, 2, 3, 4], crosses_midnight: false,
      is_flexible: false, is_active: true,
    });
    setEditing("new");
    setErr("");
  }

  async function save() {
    setSaving(true);
    setErr("");
    try {
      if (editing === "new") {
        await apiPost("/attendance/shifts/", draft);
      } else {
        await apiPut(`/attendance/shifts/${editing}/`, draft);
      }
      setEditing(null);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    try {
      const r = await apiDelete<{ deactivated?: boolean; detail?: string }>(
        `/attendance/shifts/${id}/`);
      if (r?.deactivated && r.detail) {
        setMsg(r.detail);
        setTimeout(() => setMsg(""), 6000);
      }
      load();
    } catch (e) {
      setErr((e as ApiError).message);
      setTimeout(() => setErr(""), 6000);
    }
  }

  const days: number[] = (draft.working_days as number[]) || [];
  const toggleDay = (d: number) =>
    setDraft((v) => ({
      ...v,
      working_days: days.includes(d)
        ? days.filter((x) => x !== d) : [...days, d].sort(),
    }));

  const f = (k: string) => String(draft[k] ?? "");
  const set = (k: string, v: unknown) =>
    setDraft((d) => ({ ...d, [k]: v }));

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
      <ConfirmDialog
        open={askDel !== null}
        tone="danger"
        confirmLabel={L("del")}
        message={L("confirmDelete")}
        onCancel={() => setAskDel(null)}
        onConfirm={() => {
          const id = askDel;
          setAskDel(null);
          if (id !== null) remove(id);
        }}
      />

      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        {canEdit && editing === null && (
          <button className="btn btn-primary" onClick={startNew}>
            <IcPlus size={17} />
            {L("add")}
          </button>
        )}
      </div>

      {err && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
          fontSize: ".9rem",
        }}>
          {err}
        </div>
      )}
      {msg && (
        <div style={{
          background: "var(--copper-soft)", color: "var(--copper)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
          fontSize: ".9rem",
        }}>
          {msg}
        </div>
      )}

      {editing !== null && (
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <div className="field" style={{ minWidth: 140 }}>
              <label className="label">{L("code")}</label>
              <input className="input" value={f("code")}
                disabled={editing !== "new"}
                onChange={(e) => set("code", e.target.value.toUpperCase())} />
              {editing !== "new" && (
                <div className="muted" style={{ fontSize: ".76rem" }}>
                  {L("codeHint")}
                </div>
              )}
            </div>

            <div className="field" style={{ minWidth: 190 }}>
              <label className="label">{L("name")}</label>
              <input className="input" value={f("name_ar")}
                onChange={(e) => set("name_ar", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 120 }}>
              <label className="label">{L("from")}</label>
              <input type="time" className="input" value={f("start_time")}
                onChange={(e) => set("start_time", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 120 }}>
              <label className="label">{L("to")}</label>
              <input type="time" className="input" value={f("end_time")}
                onChange={(e) => set("end_time", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 120 }}>
              <label className="label">{L("breakM")}</label>
              <input className="input num" value={f("break_minutes")}
                onChange={(e) =>
                  set("break_minutes", Number(e.target.value) || 0)} />
            </div>

            <div className="field" style={{ minWidth: 130 }}>
              <label className="label">{L("graceIn")}</label>
              <input className="input num" value={f("grace_in_minutes")}
                onChange={(e) =>
                  set("grace_in_minutes", Number(e.target.value) || 0)} />
            </div>

            <div className="field" style={{ minWidth: 130 }}>
              <label className="label">{L("graceOut")}</label>
              <input className="input num" value={f("grace_out_minutes")}
                onChange={(e) =>
                  set("grace_out_minutes", Number(e.target.value) || 0)} />
            </div>
          </div>

          <div style={{ marginTop: 14 }}>
            <label className="label">{L("days")}</label>
            <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
              {DAY_KEYS.map((k, i) => (
                <button key={k} type="button"
                  className={`btn btn-sm ${
                    days.includes(i) ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => toggleDay(i)}>
                  {L(k)}
                </button>
              ))}
            </div>
          </div>

          <div className="row" style={{ gap: 18, marginTop: 14 }}>
            <label className="row" style={{ gap: 7, cursor: "pointer" }}>
              <input type="checkbox"
                checked={!!draft.crosses_midnight}
                onChange={(e) =>
                  set("crosses_midnight", e.target.checked)}
                style={{ width: 17, height: 17,
                         accentColor: "var(--teal)" }} />
              <span style={{ fontSize: ".9rem" }}>{L("crosses")}</span>
            </label>
            <label className="row" style={{ gap: 7, cursor: "pointer" }}>
              <input type="checkbox" checked={!!draft.is_flexible}
                onChange={(e) => set("is_flexible", e.target.checked)}
                style={{ width: 17, height: 17,
                         accentColor: "var(--teal)" }} />
              <span style={{ fontSize: ".9rem" }}>{L("flexible")}</span>
            </label>
          </div>

          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn btn-primary btn-sm" disabled={saving}
              onClick={save}>
              <IcCheck size={16} />
              {L("save")}
            </button>
            <button className="btn btn-ghost btn-sm"
              onClick={() => { setEditing(null); setErr(""); }}>
              <IcX size={16} />
              {L("cancel")}
            </button>
          </div>
        </div>
      )}

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <IcClock size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("code")}</th>
                  <th>{L("name")}</th>
                  <th>{L("from")} — {L("to")}</th>
                  <th>{L("days")}</th>
                  <th style={{ textAlign: "end" }}>{L("graceIn")}</th>
                  <th>{L("active")}</th>
                  <th style={{ width: 140 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id}>
                    <td><span className="num">{s.code}</span></td>
                    <td>
                      {s.name_ar}
                      {s.is_flexible && (
                        <span className="badge" style={{
                          marginInlineStart: 6, fontSize: ".72rem",
                        }}>
                          {L("flexible")}
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="num">
                        {String(s.start_time).slice(0, 5)} —{" "}
                        {String(s.end_time).slice(0, 5)}
                      </span>
                      {s.crosses_midnight && (
                        <span className="muted" style={{
                          fontSize: ".74rem", marginInlineStart: 6,
                        }}>
                          +1
                        </span>
                      )}
                    </td>
                    <td className="muted" style={{ fontSize: ".84rem" }}>
                      {(s.working_days || [])
                        .map((d) => L(DAY_KEYS[d])).join("، ")}
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{s.grace_in_minutes}</span>
                    </td>
                    <td>
                      <span className={s.is_active
                        ? "badge badge-ok" : "badge"}>
                        {s.is_active ? L("active") : L("inactive")}
                      </span>
                    </td>
                    <td>
                      {canEdit && (
                        <div className="row" style={{ gap: 6 }}>
                          <button className="btn btn-sm btn-ghost"
                            onClick={() => {
                              setDraft({ ...s });
                              setEditing(s.id);
                              setErr("");
                            }}>
                            {L("edit")}
                          </button>
                          <button className="btn btn-sm btn-ghost"
                            style={{ color: "var(--danger)" }}
                            onClick={() => setAskDel(s.id)}>
                            {L("del")}
                          </button>
                        </div>
                      )}
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
