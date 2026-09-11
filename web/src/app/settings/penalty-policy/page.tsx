"use client";
/**
 * لائحة الجزاءات ونسخها (ق-119، ق-130).
 *
 * ⚠️ **التنقيح ينسخ ولا يدوس**: مخالفةُ يناير تُقاس بلائحة يناير
 * — وهو ما يصمد أمام هيئة تسوية الخلافات.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "لائحة الجزاءات", en: "Penalty policy" },
  sub: {
    ar: "مخالفاتك ودرجاتها — والتنقيح يسري من تاريخ تحدّده",
    en: "Violations and degrees — revisions take effect on a date",
  },
  tabList: { ar: "البنود", en: "Violations" },
  tabVersions: { ar: "النسخ", en: "Versions" },
  add: { ar: "بند جديد", en: "New violation" },
  seed: { ar: "بذر اللائحة الاسترشادية", en: "Seed default policy" },
  revise: { ar: "تنقيح جديد", en: "New revision" },
  code: { ar: "الرمز", en: "Code" },
  name: { ar: "المخالفة", en: "Violation" },
  category: { ar: "التصنيف", en: "Category" },
  degrees: { ar: "الدرجات", en: "Degrees" },
  reset: { ar: "سقوط التكرار", en: "Repeat reset" },
  days: { ar: "يومًا", en: "days" },
  financial: { ar: "أثر ماليّ", en: "Financial" },
  noFinancial: { ar: "توثيق فقط", en: "Log only" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  close: { ar: "إغلاق", en: "Close" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "الجزاءات غير متاحة في باقتكم", en: "Not in your plan" },
  empty: { ar: "لا بنود — ابذر اللائحة الاسترشادية", en: "No violations" },
  version: { ar: "النسخة", en: "Version" },
  effective: { ar: "سريان من", en: "Effective from" },
  note: { ar: "سبب التنقيح", en: "Reason" },
  current: { ar: "السارية", en: "Current" },
  future: { ar: "قادمة", en: "Upcoming" },
  past: { ar: "سابقة", en: "Past" },
  occurrence: { ar: "التكرار", en: "Occurrence" },
  kind: { ar: "الجزاء", en: "Penalty" },
  amount: { ar: "الأيام", en: "Days" },
  addDegree: { ar: "درجة", en: "Degree" },
  newTitle: { ar: "بند جديد", en: "New violation" },
  reviseTitle: { ar: "تنقيح اللائحة", en: "Revise policy" },
  reviseHint: {
    ar: "تُنسخ البنود كلّها للنسخة الجديدة — والقديمة تبقى للماضي",
    en: "All violations are copied — the old version stays for the past",
  },
  versionsHint: {
    ar: "مخالفةُ يناير تُقاس بلائحة يناير — لا بما صارت عليه",
    en: "A January violation is judged by January's policy",
  },
  savedOk: { ar: "حُفظ", en: "Saved" },
  revisedOk: { ar: "أُنشئت النسخة — نُسخ {n} بندًا", en: "{n} copied" },
  noVersions: { ar: "نسخ اللائحة غير متاحة في باقتكم", en: "Not in plan" },
};

type Degree = {
  id?: number; occurrence: number; kind: string;
  kind_label?: string; days: string; note?: string;
};
type Violation = {
  id: number; code: string; name_ar: string;
  category: string; category_label: string;
  reset_days: number; financial_effect: boolean; is_active: boolean;
  degrees: Degree[];
};
type Version = {
  id: number; number: number; effective_from: string; note: string;
  is_active: boolean; is_current: boolean; violations: number;
};
type Opt = { value: string; label: string };

export default function PenaltyPolicyPage() {
  const { L } = useT(T);
  const [tab, setTab] = useState<"list" | "versions">("list");
  const [rows, setRows] = useState<Violation[]>([]);
  const [kinds, setKinds] = useState<Opt[]>([]);
  const [cats, setCats] = useState<Opt[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [noVersions, setNoVersions] = useState(false);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState<Violation | null>(null);
  const [adding, setAdding] = useState(false);
  const [revising, setRevising] = useState(false);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ violations: Violation[]; kinds: Opt[];
                               categories: Opt[] }>(
        "/penalties/violations/");
      setRows(d.violations);
      setKinds(d.kinds);
      setCats(d.categories);

      const v = await apiGet<{ versions: Version[] }>(
        "/penalties/versions/").catch((e) => {
          if ((e as ApiError).status === 402) setNoVersions(true);
          return { versions: [] };
        });
      setVersions(v.versions);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>, ok?: string) => {
    setActing(true); setErr("");
    try {
      const out = await fn();
      if (ok) {
        setMsg(ok.replace("{n}",
          String((out as { copied?: number })?.copied ?? "")));
        setTimeout(() => setMsg(""), 5000);
      }
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
        <div className="row" style={{ gap: 8 }}>
          {rows.length === 0 && (
            <button className="btn btn-sm" disabled={acting}
                    onClick={() => act(
                      () => apiPost("/penalties/violations/seed/", {}),
                      L("savedOk"))}>
              {L("seed")}
            </button>
          )}
          {!noVersions && (
            <button className="btn btn-sm" onClick={() => setRevising(true)}>
              {L("revise")}
            </button>
          )}
          <button className="btn btn-primary btn-sm"
                  onClick={() => setAdding(true)}>{L("add")}</button>
        </div>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="row" style={{ gap: 6 }}>
        <button className={`btn btn-sm ${tab === "list" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setTab("list")}>{L("tabList")}</button>
        {!noVersions && (
          <button className={`btn btn-sm ${tab === "versions" ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setTab("versions")}>
            {L("tabVersions")}
          </button>
        )}
      </div>

      {tab === "list" ? (
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
                    <th>{L("name")}</th>
                    <th style={{ width: 150 }}>{L("category")}</th>
                    <th style={{ width: 230 }}>{L("degrees")}</th>
                    <th style={{ width: 120 }}>{L("reset")}</th>
                    <th style={{ width: 150 }} />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((v) => (
                    <tr key={v.id} style={{ opacity: v.is_active ? 1 : .55 }}>
                      <td>
                        <div style={{ fontWeight: 500 }}>{v.name_ar}</div>
                        <div className="muted num"
                             style={{ fontSize: ".74rem" }}>
                          {v.code}
                          {!v.financial_effect && ` · ${L("noFinancial")}`}
                        </div>
                      </td>
                      <td className="muted">{v.category_label}</td>
                      <td>
                        <div className="row" style={{ gap: 4,
                                                      flexWrap: "wrap" }}>
                          {v.degrees.map((d) => (
                            <span key={d.occurrence} className="badge"
                                  style={{ fontSize: ".7rem" }}
                                  title={d.kind_label}>
                              {d.occurrence}: {Number(d.days) > 0
                                ? `${d.days}` : d.kind_label}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td>
                        <span className="num">{v.reset_days}</span>{" "}
                        {L("days")}
                      </td>
                      <td>
                        <div className="row" style={{ gap: 5 }}>
                          <button className="btn btn-sm"
                                  onClick={() => { setEditing(v);
                                                   setErr(""); }}>
                            {L("edit")}
                          </button>
                          <button className="btn btn-sm btn-danger"
                                  disabled={acting}
                                  onClick={() => act(() => apiDelete(
                                    `/penalties/violations/${v.id}/`))}>
                            {L("del")}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="muted" style={{ fontSize: ".85rem" }}>
            {L("versionsHint")}
          </div>
          <div className="card" style={{ overflow: "hidden" }}>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 90 }}>{L("version")}</th>
                  <th style={{ width: 130 }}>{L("effective")}</th>
                  <th style={{ width: 100 }}>{L("degrees")}</th>
                  <th>{L("note")}</th>
                  <th style={{ width: 110 }} />
                </tr>
              </thead>
              <tbody>
                {versions.map((v) => (
                  <tr key={v.id}>
                    <td><span className="num">{v.number}</span></td>
                    <td><span className="num">{v.effective_from}</span></td>
                    <td><span className="num">{v.violations}</span></td>
                    <td className="muted">{v.note || "—"}</td>
                    <td>
                      {v.is_current ? (
                        <span className="badge badge-ok">{L("current")}</span>
                      ) : v.effective_from > new Date()
                        .toISOString().slice(0, 10) ? (
                        <span className="badge badge-warn">{L("future")}</span>
                      ) : (
                        <span className="badge">{L("past")}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {(editing || adding) && (
        <ViolationDialog v={editing} kinds={kinds} cats={cats} L={L}
                         onClose={() => { setEditing(null);
                                          setAdding(false); }}
                         onSaved={async () => {
                           setEditing(null); setAdding(false);
                           setMsg(L("savedOk"));
                           setTimeout(() => setMsg(""), 3000);
                           await load();
                         }} />
      )}

      {revising && (
        <ReviseDialog L={L} onClose={() => setRevising(false)}
                      onSaved={async (copied) => {
                        setRevising(false);
                        setMsg(L("revisedOk").replace("{n}",
                                                      String(copied)));
                        setTimeout(() => setMsg(""), 6000);
                        await load();
                      }} />
      )}
    </div>
  );
}


/* ══ نافذة البند ══ */

function ViolationDialog({ v, kinds, cats, L, onClose, onSaved }: {
  v: Violation | null;
  kinds: Opt[];
  cats: Opt[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({
    code: v?.code || "",
    name_ar: v?.name_ar || "",
    category: v?.category || (cats[0]?.value || "other"),
    reset_days: String(v?.reset_days ?? 365),
    financial_effect: v?.financial_effect ?? true,
    is_active: v?.is_active ?? true,
  });
  const [degrees, setDegrees] = useState<Degree[]>(
    v?.degrees?.length ? v.degrees.map((d) => ({ ...d })) : [
      { occurrence: 1, kind: "warning", days: "0" },
    ]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const setDeg = (i: number, patch: Partial<Degree>) =>
    setDegrees(degrees.map((d, j) => (j === i ? { ...d, ...patch } : d)));

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const body = {
        ...f, reset_days: Number(f.reset_days) || 365,
        degrees: degrees.map((d) => ({
          occurrence: Number(d.occurrence) || 1,
          kind: d.kind, days: d.days || "0",
        })),
      };
      if (v) await apiPut(`/penalties/violations/${v.id}/`, body);
      else await apiPost("/penalties/violations/", body);
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
      <div className="card" style={{ padding: 24, maxWidth: 620,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{v ? v.name_ar : L("newTitle")}</h3>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="row" style={{ gap: 12, marginTop: 16,
                                      flexWrap: "wrap" }}>
          {!v && (
            <label className="field" style={{ width: 140 }}>
              <span className="label">{L("code")}</span>
              <input className="input" dir="ltr" value={f.code}
                     onChange={(e) => setF({ ...f,
                       code: e.target.value.trim().toUpperCase() })} />
            </label>
          )}
          <label className="field" style={{ flex: 1, minWidth: 200 }}>
            <span className="label">{L("name")}</span>
            <input className="input" value={f.name_ar}
                   onChange={(e) => setF({ ...f,
                     name_ar: e.target.value })} />
          </label>
        </div>

        <div className="row" style={{ gap: 12, marginTop: 12,
                                      flexWrap: "wrap" }}>
          <label className="field" style={{ minWidth: 190 }}>
            <span className="label">{L("category")}</span>
            <select className="select" value={f.category}
                    onChange={(e) => setF({ ...f,
                      category: e.target.value })}>
              {cats.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </label>
          <label className="field" style={{ width: 150 }}>
            <span className="label">{L("reset")}</span>
            <input className="input num" type="number" min={0}
                   value={f.reset_days}
                   onChange={(e) => setF({ ...f,
                     reset_days: e.target.value })} />
          </label>
        </div>

        <div style={{ marginTop: 18 }}>
          <div className="spread">
            <span className="label">{L("degrees")}</span>
            <button className="btn btn-sm btn-ghost"
                    onClick={() => setDegrees([...degrees, {
                      occurrence: degrees.length + 1,
                      kind: "wage_deduction", days: "1",
                    }])}>
              + {L("addDegree")}
            </button>
          </div>

          <div className="stack" style={{ gap: 8, marginTop: 8 }}>
            {degrees.map((d, i) => (
              <div key={i} className="row" style={{ gap: 8,
                                                    alignItems: "center" }}>
                <input className="input num" type="number" min={1}
                       style={{ width: 70 }} value={d.occurrence}
                       onChange={(e) => setDeg(i, {
                         occurrence: Number(e.target.value) || 1 })} />
                <select className="select" style={{ flex: 1 }}
                        value={d.kind}
                        onChange={(e) => setDeg(i, {
                          kind: e.target.value })}>
                  {kinds.map((k) => (
                    <option key={k.value} value={k.value}>{k.label}</option>
                  ))}
                </select>
                <input className="input num" style={{ width: 90 }}
                       value={d.days}
                       onChange={(e) => setDeg(i, {
                         days: e.target.value })} />
                <button className="btn btn-sm btn-ghost"
                        onClick={() => setDegrees(
                          degrees.filter((_, j) => j !== i))}>×</button>
              </div>
            ))}
          </div>
        </div>

        <label className="row" style={{ gap: 8, marginTop: 14,
                                        cursor: "pointer" }}>
          <input type="checkbox" checked={f.financial_effect}
                 onChange={(e) => setF({ ...f,
                   financial_effect: e.target.checked })} />
          <span>{L("financial")}</span>
        </label>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.name_ar.trim() || (!v && !f.code)}
                  onClick={submit}>
            {busy ? "…" : L("save")}
          </button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}


/* ══ نافذة التنقيح ══ */

function ReviseDialog({ L, onClose, onSaved }: {
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: (copied: number) => void;
}) {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const [eff, setEff] = useState(tomorrow.toISOString().slice(0, 10));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const out = await apiPost<{ copied: number }>(
        "/penalties/versions/", { effective_from: eff, note });
      onSaved(out.copied);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 440,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("reviseTitle")}</h3>
        <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
          {L("reviseHint")}
        </div>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="field" style={{ marginTop: 16 }}>
          <label className="label">{L("effective")}</label>
          <DateField value={eff} onChange={setEff} />
        </div>

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("note")}</span>
          <input className="input" value={note}
                 onChange={(e) => setNote(e.target.value)} />
        </label>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary" disabled={busy || !eff}
                  onClick={submit}>{busy ? "…" : L("save")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}
