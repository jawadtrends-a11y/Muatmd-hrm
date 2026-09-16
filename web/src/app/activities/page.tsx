"use client";
/**
 * إدارة أنشطة العمل (ق-143).
 *
 * ⚠️ **والمراجعة هي الضابط** — فمالٌ يُصرف أو يُحسم بقول صاحبه
 * بلا مراجعة.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "أنشطة العمل", en: "Work activities" },
  sub: {
    ar: "أسنِد نشاطًا يوميًّا لمدًى — وراجع ما أُقرّ",
    en: "Assign daily activities over a range — review reports",
  },
  add: { ar: "إسناد نشاط", en: "Assign" },
  pendingReview: { ar: "بانتظار المراجعة", en: "To review" },
  all: { ar: "الكل", en: "All" },
  day: { ar: "اليوم", en: "Day" },
  employee: { ar: "الموظف", en: "Employee" },
  activity: { ar: "النشاط", en: "Activity" },
  done: { ar: "المنجَز", en: "Done" },
  state: { ar: "الحالة", en: "Status" },
  effect: { ar: "الأثر", en: "Effect" },
  review: { ar: "مراجعة", en: "Review" },
  empty: { ar: "لا أنشطة", en: "No activities" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "أنشطة العمل غير متاحة في باقتكم",
              en: "Not in your plan" },
  assignTitle: { ar: "إسناد نشاط", en: "Assign activity" },
  who: { ar: "الموظف", en: "Employee" },
  what: { ar: "النشاط", en: "Activity" },
  details: { ar: "التفاصيل", en: "Details" },
  from: { ar: "من", en: "From" },
  to: { ar: "إلى", en: "To" },
  target: { ar: "العدد المستهدَف", en: "Target" },
  targetHint: {
    ar: "اتركه فارغًا لنشاطٍ موصوف لا يُقاس برقم",
    en: "Leave empty for a descriptive activity",
  },
  unit: { ar: "الوحدة", en: "Unit" },
  payEffect: { ar: "الأثر الماليّ", en: "Pay effect" },
  payBasis: { ar: "أساس الاحتساب", en: "Basis" },
  bonus: { ar: "مبلغ المكافأة", en: "Bonus" },
  deduction: { ar: "مبلغ الحسم", en: "Deduction" },
  skipRest: { ar: "تخطّي أيام الراحة", en: "Skip rest days" },
  save: { ar: "إسناد", en: "Assign" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  reviewTitle: { ar: "مراجعة النشاط", en: "Review" },
  computed: { ar: "المحتسَب", en: "Computed" },
  override: { ar: "تعديل المبلغ", en: "Override" },
  note: { ar: "ملاحظة", en: "Note" },
  confirm: { ar: "اعتماد المراجعة", en: "Confirm review" },
  assignedOk: { ar: "أُسند النشاط", en: "Assigned" },
  reviewedOk: { ar: "رُوجع", en: "Reviewed" },
  reviewNote: {
    ar: "⚠️ وبالمراجعة وحدها يقع الأثر الماليّ",
    en: "The pay effect only applies on review",
  },
};

type Activity = {
  id: number; work_date: string; employment_id: number;
  employee: string; title: string; description: string;
  target_count: number | null; unit: string;
  status: string; status_label: string;
  done_count: number | null; done_note: string; pending_note: string;
  achievement: number | null;
  pay_effect: string; pay_basis: string;
  bonus_amount: string | null; deduction_amount: string | null;
  is_reviewed: boolean; settled_amount: string | null;
  is_paid: boolean;
};
type Opt = { value: string; label: string };
type Peer = { employment_id: number; name: string };

const TONE: Record<string, string> = {
  pending: "badge-warn", done: "badge-ok",
  partial: "badge", not_done: "badge-danger",
};

export default function ActivitiesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Activity[]>([]);
  const [effects, setEffects] = useState<Opt[]>([]);
  const [bases, setBases] = useState<Opt[]>([]);
  const [warning, setWarning] = useState("");
  const [peers, setPeers] = useState<Peer[]>([]);
  const [onlyReview, setOnlyReview] = useState(true);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [adding, setAdding] = useState(false);
  const [reviewing, setReviewing] = useState<Activity | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [d, dir] = await Promise.all([
        apiGet<{ activities: Activity[]; effects: Opt[]; bases: Opt[];
                 deduction_warning: string }>(
          `/activities/${onlyReview ? "?pending_review=1" : ""}`),
        apiGet<{ rows: Peer[] }>("/directory/").catch(() => ({ rows: [] })),
      ]);
      setRows(d.activities);
      setEffects(d.effects);
      setBases(d.bases);
      setWarning(d.deduction_warning);
      setPeers(dir.rows);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [onlyReview]);

  useEffect(() => { load(); }, [load]);

  if (busy) return (
    <div className="card" style={{ padding: 40, textAlign: "center",
                                   color: "var(--ink-3)" }}>{L("loading")}</div>
  );

  if (denied) return (
    <div className="card" style={{ padding: 36, textAlign: "center",
                                   color: "var(--ink-3)" }}>
      <IcAlert size={22} />
      <div style={{ marginTop: 8 }}>{L("noAccess")}</div>
    </div>
  );

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1 style={{ margin: 0 }}>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("sub")}
          </div>
        </div>
        <button className="btn btn-primary btn-sm"
                onClick={() => setAdding(true)}>{L("add")}</button>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="row" style={{ gap: 6 }}>
        <button className={`btn btn-sm ${onlyReview ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyReview(true)}>
          {L("pendingReview")}
        </button>
        <button className={`btn btn-sm ${!onlyReview ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyReview(false)}>{L("all")}</button>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>
            <IcDoc size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 110 }}>{L("day")}</th>
                  <th style={{ width: 150 }}>{L("employee")}</th>
                  <th>{L("activity")}</th>
                  <th style={{ width: 110 }}>{L("done")}</th>
                  <th style={{ width: 120 }}>{L("state")}</th>
                  <th style={{ width: 110 }}>{L("effect")}</th>
                  <th style={{ width: 90 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id}>
                    <td><span className="num">{a.work_date}</span></td>
                    <td className="muted">{a.employee}</td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{a.title}</div>
                      {a.pending_note && (
                        <div style={{ fontSize: ".76rem",
                                      color: "var(--copper)" }}>
                          {a.pending_note}
                        </div>
                      )}
                    </td>
                    <td>
                      {a.target_count ? (
                        <span className="num">
                          {a.done_count ?? "—"}/{a.target_count}
                        </span>
                      ) : <span className="muted">—</span>}
                    </td>
                    <td>
                      <span className={`badge ${TONE[a.status] || "badge"}`}>
                        {a.status_label}
                      </span>
                    </td>
                    <td>
                      {a.settled_amount && a.settled_amount !== "0.00" ? (
                        <span className="num" style={{
                          color: Number(a.settled_amount) < 0
                            ? "var(--danger)" : "var(--ok)" }}>
                          {a.settled_amount}
                        </span>
                      ) : a.pay_effect !== "none" ? (
                        <span className="muted"
                              style={{ fontSize: ".78rem" }}>—</span>
                      ) : null}
                    </td>
                    <td>
                      {!a.is_reviewed && a.status !== "pending" && (
                        <button className="btn btn-sm btn-primary"
                                onClick={() => setReviewing(a)}>
                          {L("review")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {adding && (
        <AssignDialog peers={peers} effects={effects} bases={bases}
                      warning={warning} L={L}
                      onClose={() => setAdding(false)}
                      onSaved={async (n) => {
                        setAdding(false);
                        setMsg(`${L("assignedOk")} — ${n}`);
                        setTimeout(() => setMsg(""), 4000);
                        await load();
                      }} />
      )}

      {reviewing && (
        <ReviewDialog a={reviewing} L={L}
                      onClose={() => setReviewing(null)}
                      onSaved={async () => {
                        setReviewing(null);
                        setMsg(L("reviewedOk"));
                        setTimeout(() => setMsg(""), 3000);
                        await load();
                      }} />
      )}
    </div>
  );
}


function AssignDialog({ peers, effects, bases, warning, L,
                        onClose, onSaved }: {
  peers: Peer[];
  effects: Opt[];
  bases: Opt[];
  warning: string;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: (n: number) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [f, setF] = useState({
    employment_id: "", title: "", description: "",
    start_date: today, end_date: today,
    target_count: "", unit: "",
    pay_effect: "none", pay_basis: "per_activity",
    bonus_amount: "", deduction_amount: "",
    skip_weekends: true,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const hasBonus = f.pay_effect === "bonus" || f.pay_effect === "both";
  const hasDeduct = f.pay_effect === "deduction" || f.pay_effect === "both";

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const out = await apiPost<{ created: number }>("/activities/", {
        ...f,
        employment_id: Number(f.employment_id),
        target_count: f.target_count ? Number(f.target_count) : undefined,
        bonus_amount: f.bonus_amount || undefined,
        deduction_amount: f.deduction_amount || undefined,
      });
      onSaved(out.created);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose();
    }} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 520,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("assignTitle")}</h3>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="stack" style={{ gap: 12, marginTop: 16 }}>
          <label className="field">
            <span className="label">{L("who")}</span>
            <select className="select" value={f.employment_id}
                    onChange={(e) => setF({ ...f,
                      employment_id: e.target.value })}>
              <option value="">—</option>
              {peers.map((p) => (
                <option key={p.employment_id} value={p.employment_id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="label">{L("what")}</span>
            <input className="input" value={f.title}
                   onChange={(e) => setF({ ...f, title: e.target.value })} />
          </label>

          <label className="field">
            <span className="label">{L("details")}</span>
            <textarea className="input" rows={2} value={f.description}
                      onChange={(e) => setF({ ...f,
                        description: e.target.value })} />
          </label>

          <div className="row" style={{ gap: 12 }}>
            <div className="field" style={{ flex: 1 }}>
              <label className="label">{L("from")}</label>
              <DateField value={f.start_date}
                         onChange={(v) => setF({ ...f, start_date: v })} />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label className="label">{L("to")}</label>
              <DateField value={f.end_date}
                         onChange={(v) => setF({ ...f, end_date: v })} />
            </div>
          </div>

          <div className="row" style={{ gap: 12 }}>
            <label className="field" style={{ width: 150 }}>
              <span className="label">{L("target")}</span>
              <input className="input num" type="number" min={1}
                     value={f.target_count} placeholder="—"
                     onChange={(e) => setF({ ...f,
                       target_count: e.target.value })} />
            </label>
            <label className="field" style={{ width: 130 }}>
              <span className="label">{L("unit")}</span>
              <input className="input" value={f.unit}
                     placeholder="معاملة"
                     onChange={(e) => setF({ ...f,
                       unit: e.target.value })} />
            </label>
          </div>
          <div className="muted" style={{ fontSize: ".78rem",
                                          marginTop: -6 }}>
            {L("targetHint")}
          </div>

          <label className="row" style={{ gap: 8, cursor: "pointer" }}>
            <input type="checkbox" checked={f.skip_weekends}
                   onChange={(e) => setF({ ...f,
                     skip_weekends: e.target.checked })} />
            <span>{L("skipRest")}</span>
          </label>

          <div className="row" style={{ gap: 12 }}>
            <label className="field" style={{ flex: 1 }}>
              <span className="label">{L("payEffect")}</span>
              <select className="select" value={f.pay_effect}
                      onChange={(e) => setF({ ...f,
                        pay_effect: e.target.value })}>
                {effects.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </label>
            {f.pay_effect !== "none" && (
              <label className="field" style={{ flex: 1 }}>
                <span className="label">{L("payBasis")}</span>
                <select className="select" value={f.pay_basis}
                        onChange={(e) => setF({ ...f,
                          pay_basis: e.target.value })}>
                  {bases.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </label>
            )}
          </div>

          {(hasBonus || hasDeduct) && (
            <div className="row" style={{ gap: 12 }}>
              {hasBonus && (
                <label className="field" style={{ flex: 1 }}>
                  <span className="label">{L("bonus")}</span>
                  <input className="input num" type="number" min={0}
                         step="0.01" value={f.bonus_amount}
                         onChange={(e) => setF({ ...f,
                           bonus_amount: e.target.value })} />
                </label>
              )}
              {hasDeduct && (
                <label className="field" style={{ flex: 1 }}>
                  <span className="label">{L("deduction")}</span>
                  <input className="input num" type="number" min={0}
                         step="0.01" value={f.deduction_amount}
                         onChange={(e) => setF({ ...f,
                           deduction_amount: e.target.value })} />
                </label>
              )}
            </div>
          )}

          {hasDeduct && warning && (
            <div style={{ background: "var(--copper-soft)",
                          color: "var(--copper)", padding: "10px 13px",
                          borderRadius: "var(--radius-sm)",
                          fontSize: ".8rem", lineHeight: 1.8 }}>
              {warning}
            </div>
          )}
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.employment_id || !f.title.trim()}
                  onClick={submit}>{busy ? "…" : L("save")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}


function ReviewDialog({ a, L, onClose, onSaved }: {
  a: Activity;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [override, setOverride] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost(`/activities/${a.id}/review/`, {
        note, override: override || undefined,
      });
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose();
    }} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 440,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("reviewTitle")}</h3>
        <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
          {a.employee} — {a.title} —{" "}
          <span className="num">{a.work_date}</span>
        </div>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div style={{ marginTop: 14, padding: "12px 14px",
                      background: "var(--paper-2)",
                      borderRadius: "var(--radius-sm)",
                      fontSize: ".88rem" }}>
          <div className="spread">
            <span className="muted">{L("state")}</span>
            <span>{a.status_label}</span>
          </div>
          {a.target_count && (
            <div className="spread" style={{ marginTop: 5 }}>
              <span className="muted">{L("done")}</span>
              <span className="num">
                {a.done_count}/{a.target_count} {a.unit}
              </span>
            </div>
          )}
          {a.done_note && (
            <div style={{ marginTop: 8, fontSize: ".84rem" }}>
              {a.done_note}
            </div>
          )}
          {a.pending_note && (
            <div style={{ marginTop: 6, fontSize: ".84rem",
                          color: "var(--copper)" }}>
              {a.pending_note}
            </div>
          )}
        </div>

        {a.pay_effect !== "none" && (
          <label className="field" style={{ marginTop: 14, width: 180 }}>
            <span className="label">{L("override")}</span>
            <input className="input num" type="number" step="0.01"
                   value={override} placeholder={L("computed")}
                   onChange={(e) => setOverride(e.target.value)} />
          </label>
        )}

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("note")}</span>
          <input className="input" value={note}
                 onChange={(e) => setNote(e.target.value)} />
        </label>

        <div className="muted" style={{ fontSize: ".78rem",
                                        marginTop: 10 }}>
          {L("reviewNote")}
        </div>

        <div className="row" style={{ gap: 8, marginTop: 16 }}>
          <button className="btn btn-primary" disabled={busy}
                  onClick={submit}>{busy ? "…" : L("confirm")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}
