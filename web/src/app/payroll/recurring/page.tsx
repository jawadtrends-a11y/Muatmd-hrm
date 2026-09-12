"use client";
/**
 * البنود المكرّرة (ق-135).
 *
 * ⚠️ **ولها نهايةٌ دائمًا**: بتاريخٍ أو بعدد مرّات — فبندٌ بلا
 * نهاية يُحسم من الموظف سنين، ومن أدخله نسيه.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "البنود المكرّرة", en: "Recurring adjustments" },
  sub: {
    ar: "إضافاتٌ وحسومٌ تتكرّر شهريًّا بلا إدخال",
    en: "Monthly additions and deductions, entered once",
  },
  add: { ar: "بند جديد", en: "New item" },
  active: { ar: "السارية", en: "Active" },
  all: { ar: "الكل", en: "All" },
  employee: { ar: "الموظف", en: "Employee" },
  component: { ar: "البند", en: "Component" },
  kind: { ar: "النوع", en: "Type" },
  amount: { ar: "المبلغ", en: "Amount" },
  period: { ar: "المدى", en: "Period" },
  progress: { ar: "التقدّم", en: "Progress" },
  stop: { ar: "إيقاف", en: "Stop" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  empty: { ar: "لا بنود مكرّرة", en: "No recurring items" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "البنود المكرّرة غير متاحة في باقتكم",
              en: "Not in your plan" },
  newTitle: { ar: "بند مكرّر", en: "Recurring item" },
  from: { ar: "من", en: "From" },
  to: { ar: "إلى", en: "To" },
  endBy: { ar: "النهاية", en: "Ends by" },
  byDate: { ar: "بتاريخ", en: "By date" },
  byCount: { ar: "بعدد مرّات", en: "By count" },
  count: { ar: "عدد المرّات", en: "Occurrences" },
  endHint: {
    ar: "⚠️ لا بدّ من نهاية — فبندٌ بلا نهاية يُحسم سنين",
    en: "An end is required",
  },
  reason: { ar: "السبب", en: "Reason" },
  remaining: { ar: "متبقٍّ", en: "left" },
  openEnded: { ar: "حتى تاريخه", en: "until date" },
  savedOk: { ar: "حُفظ", en: "Saved" },
  year: { ar: "السنة", en: "Year" },
  month: { ar: "الشهر", en: "Month" },
};

type Row = {
  id: number; employment_id: number; employee_no: string;
  employee: string; component_id: number; component: string;
  kind: string; kind_label: string; amount: string;
  start: string; end: string;
  max_occurrences: number | null; applied_count: number;
  remaining: number | null; reason: string; is_active: boolean;
};
type Opt = { value: string; label: string };
type Component = { id: number; code: string; name_ar: string };
type Peer = { employment_id: number; name: string };

export default function RecurringPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Row[]>([]);
  const [kinds, setKinds] = useState<Opt[]>([]);
  const [components, setComponents] = useState<Component[]>([]);
  const [peers, setPeers] = useState<Peer[]>([]);
  const [onlyActive, setOnlyActive] = useState(true);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [adding, setAdding] = useState(false);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [d, dir] = await Promise.all([
        apiGet<{ rows: Row[]; kinds: Opt[]; components: Component[] }>(
          `/recurring/?active=${onlyActive ? "1" : "0"}`),
        apiGet<{ rows: Peer[] }>("/directory/").catch(() => ({ rows: [] })),
      ]);
      setRows(d.rows);
      setKinds(d.kinds);
      setComponents(d.components);
      setPeers(dir.rows);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [onlyActive]);

  useEffect(() => { load(); }, [load]);

  const stop = async (r: Row) => {
    setActing(true); setErr("");
    try {
      const out = await apiDelete<{ stopped?: boolean; detail?: string }>(
        `/recurring/${r.id}/`);
      if (out?.stopped) setMsg(out.detail || "");
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

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
        <button className={`btn btn-sm ${onlyActive ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyActive(true)}>{L("active")}</button>
        <button className={`btn btn-sm ${!onlyActive ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyActive(false)}>{L("all")}</button>
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
                  <th>{L("employee")}</th>
                  <th style={{ width: 150 }}>{L("component")}</th>
                  <th style={{ width: 90 }}>{L("kind")}</th>
                  <th style={{ width: 110 }}>{L("amount")}</th>
                  <th style={{ width: 160 }}>{L("period")}</th>
                  <th style={{ width: 130 }}>{L("progress")}</th>
                  <th style={{ width: 90 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} style={{ opacity: r.is_active ? 1 : .55 }}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{r.employee}</div>
                      <div className="muted num"
                           style={{ fontSize: ".74rem" }}>
                        {r.employee_no}
                      </div>
                    </td>
                    <td className="muted">
                      {r.component}
                      {r.reason && (
                        <div className="muted"
                             style={{ fontSize: ".74rem" }}>{r.reason}</div>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${r.kind === "deduction" ? "badge-warn" : "badge-ok"}`}>
                        {r.kind_label}
                      </span>
                    </td>
                    <td><span className="num">{r.amount}</span></td>
                    <td>
                      <span className="num" style={{ fontSize: ".82rem" }}>
                        {r.start}
                        {r.end ? ` → ${r.end}` : ""}
                      </span>
                    </td>
                    <td>
                      {r.max_occurrences ? (
                        <span className="num" style={{ fontSize: ".84rem" }}>
                          {r.applied_count}/{r.max_occurrences}
                          {r.remaining ? ` — ${r.remaining} ${L("remaining")}` : ""}
                        </span>
                      ) : (
                        <span className="muted"
                              style={{ fontSize: ".8rem" }}>
                          {L("openEnded")}
                        </span>
                      )}
                    </td>
                    <td>
                      {r.is_active && (
                        <button className="btn btn-sm btn-danger"
                                disabled={acting}
                                onClick={() => stop(r)}>{L("stop")}</button>
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
        <RecurringDialog kinds={kinds} components={components}
                         peers={peers} L={L}
                         onClose={() => setAdding(false)}
                         onSaved={async () => {
                           setAdding(false);
                           setMsg(L("savedOk"));
                           setTimeout(() => setMsg(""), 3000);
                           await load();
                         }} />
      )}
    </div>
  );
}


function RecurringDialog({ kinds, components, peers, L, onClose, onSaved }: {
  kinds: Opt[];
  components: Component[];
  peers: Peer[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const now = new Date();
  const [f, setF] = useState({
    employment_id: "", component_id: "",
    kind: "deduction", amount: "",
    start_year: String(now.getFullYear()),
    start_month: String(now.getMonth() + 1),
    reason: "",
  });
  const [endBy, setEndBy] = useState<"count" | "date">("count");
  const [count, setCount] = useState("6");
  const [endYear, setEndYear] = useState(String(now.getFullYear() + 1));
  const [endMonth, setEndMonth] = useState("12");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/recurring/", {
        ...f,
        employment_id: Number(f.employment_id),
        component_id: Number(f.component_id),
        start_year: Number(f.start_year),
        start_month: Number(f.start_month),
        ...(endBy === "count"
          ? { max_occurrences: Number(count) }
          : { end_year: Number(endYear), end_month: Number(endMonth) }),
      });
      onSaved();
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
      <div className="card" style={{ padding: 24, maxWidth: 520,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("newTitle")}</h3>

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
            <span className="label">{L("employee")}</span>
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

          <div className="row" style={{ gap: 12 }}>
            <label className="field" style={{ flex: 1 }}>
              <span className="label">{L("component")}</span>
              <select className="select" value={f.component_id}
                      onChange={(e) => setF({ ...f,
                        component_id: e.target.value })}>
                <option value="">—</option>
                {components.map((c) => (
                  <option key={c.id} value={c.id}>{c.name_ar}</option>
                ))}
              </select>
            </label>
            <label className="field" style={{ width: 120 }}>
              <span className="label">{L("kind")}</span>
              <select className="select" value={f.kind}
                      onChange={(e) => setF({ ...f, kind: e.target.value })}>
                {kinds.map((k) => (
                  <option key={k.value} value={k.value}>{k.label}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="row" style={{ gap: 12 }}>
            <label className="field" style={{ width: 140 }}>
              <span className="label">{L("amount")}</span>
              <input className="input num" type="number" min={0}
                     step="0.01" value={f.amount}
                     onChange={(e) => setF({ ...f,
                       amount: e.target.value })} />
            </label>
            <label className="field" style={{ width: 110 }}>
              <span className="label">{L("from")} — {L("year")}</span>
              <input className="input num" type="number"
                     value={f.start_year}
                     onChange={(e) => setF({ ...f,
                       start_year: e.target.value })} />
            </label>
            <label className="field" style={{ width: 100 }}>
              <span className="label">{L("month")}</span>
              <input className="input num" type="number" min={1} max={12}
                     value={f.start_month}
                     onChange={(e) => setF({ ...f,
                       start_month: e.target.value })} />
            </label>
          </div>

          <div>
            <div className="spread">
              <span className="label">{L("endBy")}</span>
              <span className="muted" style={{ fontSize: ".78rem" }}>
                {L("endHint")}
              </span>
            </div>
            <div className="row" style={{ gap: 6, marginTop: 6 }}>
              <button type="button"
                      className={`btn btn-sm ${endBy === "count" ? "btn-primary" : "btn-ghost"}`}
                      onClick={() => setEndBy("count")}>
                {L("byCount")}
              </button>
              <button type="button"
                      className={`btn btn-sm ${endBy === "date" ? "btn-primary" : "btn-ghost"}`}
                      onClick={() => setEndBy("date")}>
                {L("byDate")}
              </button>
            </div>

            {endBy === "count" ? (
              <label className="field" style={{ marginTop: 10,
                                                maxWidth: 160 }}>
                <span className="label">{L("count")}</span>
                <input className="input num" type="number" min={1}
                       value={count}
                       onChange={(e) => setCount(e.target.value)} />
              </label>
            ) : (
              <div className="row" style={{ gap: 12, marginTop: 10 }}>
                <label className="field" style={{ width: 120 }}>
                  <span className="label">{L("year")}</span>
                  <input className="input num" type="number"
                         value={endYear}
                         onChange={(e) => setEndYear(e.target.value)} />
                </label>
                <label className="field" style={{ width: 110 }}>
                  <span className="label">{L("month")}</span>
                  <input className="input num" type="number" min={1}
                         max={12} value={endMonth}
                         onChange={(e) => setEndMonth(e.target.value)} />
                </label>
              </div>
            )}
          </div>

          <label className="field">
            <span className="label">{L("reason")}</span>
            <input className="input" value={f.reason}
                   onChange={(e) => setF({ ...f,
                     reason: e.target.value })} />
          </label>
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.employment_id || !f.component_id
                            || !f.amount}
                  onClick={submit}>{busy ? "…" : L("save")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}
