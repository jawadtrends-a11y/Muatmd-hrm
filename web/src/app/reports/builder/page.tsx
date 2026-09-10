"use client";
/**
 * باني التقارير المخصّصة (ق-126).
 *
 * **العميل يختار حقوله ويبني تقريره** — لا ينتظر تقريرًا جديدًا
 * لكل حاجة. ويعاين قبل أن يحفظ، ويصدّر إكسل أو PDF.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "باني التقارير", en: "Report builder" },
  sub: {
    ar: "اختر مصدرك وحقولك — وعاين قبل أن تحفظ",
    en: "Pick a source and fields — preview before saving",
  },
  saved: { ar: "تقاريري", en: "My reports" },
  build: { ar: "تقرير جديد", en: "New report" },
  source: { ar: "المصدر", en: "Source" },
  fields: { ar: "الحقول", en: "Fields" },
  fieldsHint: {
    ar: "اضغط الحقل لإضافته — والترتيب كترتيب اختيارك",
    en: "Click to add — order follows your picks",
  },
  chosen: { ar: "المختارة", en: "Chosen" },
  name: { ar: "اسم التقرير", en: "Report name" },
  shared: { ar: "مشترك مع الفريق", en: "Share with team" },
  sharedHint: {
    ar: "مطفأ = تراه أنت وحدك",
    en: "Off = only you see it",
  },
  from: { ar: "من", en: "From" },
  to: { ar: "إلى", en: "To" },
  preview: { ar: "معاينة", en: "Preview" },
  previewing: { ar: "جارٍ…", en: "Working…" },
  save: { ar: "حفظ", en: "Save" },
  run: { ar: "تشغيل", en: "Run" },
  del: { ar: "حذف", en: "Delete" },
  back: { ar: "رجوع", en: "Back" },
  exportX: { ar: "إكسل", en: "Excel" },
  exportP: { ar: "PDF", en: "PDF" },
  rows: { ar: "صفوف", en: "rows" },
  empty: { ar: "لا نتائج", en: "No results" },
  emptySaved: {
    ar: "لم تبنِ تقريرًا بعد — ابدأ بواحد",
    en: "No reports yet — build one",
  },
  pickFields: { ar: "اختر حقلًا واحدًا على الأقلّ", en: "Pick a field" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: {
    ar: "باني التقارير غير متاح في باقتكم",
    en: "Report builder not in your plan",
  },
  truncated: {
    ar: "عُرضت أول ٥٠٠٠ صفّ — ضيّق المدى أو التصفية",
    en: "First 5000 rows shown — narrow your filters",
  },
  savedOk: { ar: "حُفظ التقرير", en: "Report saved" },
};

type Field = { key: string; label_ar: string; kind: string };
type Source = { value: string; label: string; fields: Field[] };
type Saved = {
  id: number; name_ar: string; source: string; source_label: string;
  fields: string[]; is_shared: boolean;
};
type Result = {
  title_ar: string;
  columns: { key: string; label_ar: string; kind: string }[];
  rows: Record<string, unknown>[];
  count: number;
  truncated: boolean;
};

export default function BuilderPage() {
  const { L } = useT(T);
  const [tab, setTab] = useState<"saved" | "build">("saved");
  const [sources, setSources] = useState<Source[]>([]);
  const [saved, setSaved] = useState<Saved[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  // بناء
  const [src, setSrc] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [shared, setShared] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [s, r] = await Promise.all([
        apiGet<{ sources: Source[] }>("/reports/builder/sources/"),
        apiGet<Saved[]>("/reports/custom/").catch(() => []),
      ]);
      setSources(s.sources);
      setSaved(r);
      if (s.sources.length && !src) setSrc(s.sources[0].value);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [src]);

  useEffect(() => { load(); }, [load]);

  const fields = sources.find((s) => s.value === src)?.fields || [];

  const toggle = (k: string) =>
    setPicked(picked.includes(k)
      ? picked.filter((x) => x !== k)
      : [...picked, k]);

  const preview = async () => {
    if (!picked.length) { setErr(L("pickFields")); return; }
    setActing(true); setErr("");
    try {
      setResult(await apiPost<Result>("/reports/custom/preview/", {
        source: src, fields: picked,
        date_from: from || undefined, date_to: to || undefined,
      }));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  const save = async () => {
    if (!name.trim()) { setErr(L("name")); return; }
    setActing(true); setErr("");
    try {
      await apiPost("/reports/custom/", {
        name_ar: name, source: src, fields: picked, is_shared: shared,
      });
      setMsg(L("savedOk"));
      setTimeout(() => setMsg(""), 4000);
      setName(""); setTab("saved");
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  const runSaved = async (r: Saved) => {
    setActing(true); setErr("");
    try {
      const out = await apiPost<Result>(`/reports/custom/${r.id}/run/`, {
        date_from: from || undefined, date_to: to || undefined,
      });
      setResult(out);
      setSrc(r.source);
      setPicked(r.fields);
      setTab("build");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  const remove = async (r: Saved) => {
    setActing(true);
    try {
      await apiDelete(`/reports/custom/${r.id}/`);
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  const exportCsv = () => {
    if (!result) return;
    const head = result.columns.map((c) => c.label_ar).join(",");
    const body = result.rows.map((row) =>
      result.columns.map((c) => {
        const v = row[c.key];
        const s = v === null || v === undefined ? "" : String(v);
        return s.includes(",") ? `"${s.replace(/"/g, '""')}"` : s;
      }).join(",")).join("\n");
    // BOM ليقرأ إكسل العربية صحيحةً
    const blob = new Blob(["\uFEFF" + head + "\n" + body],
                          { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${result.title_ar}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (busy) return (
    <div className="card" style={{ padding: 40, textAlign: "center",
                                   color: "var(--ink-3)" }}>
      {L("loading")}
    </div>
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
      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("sub")}
        </div>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="row" style={{ gap: 6 }}>
        <button className={`btn btn-sm ${tab === "saved" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setTab("saved")}>{L("saved")}</button>
        <button className={`btn btn-sm ${tab === "build" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setTab("build")}>{L("build")}</button>
      </div>

      {tab === "saved" ? (
        <div className="card" style={{ overflow: "hidden" }}>
          {saved.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center",
                          color: "var(--ink-3)" }}>
              <IcDoc size={22} />
              <div style={{ marginTop: 8 }}>{L("emptySaved")}</div>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>{L("name")}</th>
                  <th style={{ width: 130 }}>{L("source")}</th>
                  <th style={{ width: 90 }}>{L("fields")}</th>
                  <th style={{ width: 180 }} />
                </tr>
              </thead>
              <tbody>
                {saved.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{r.name_ar}</div>
                      {r.is_shared && (
                        <span className="badge"
                              style={{ fontSize: ".7rem" }}>
                          {L("shared")}
                        </span>
                      )}
                    </td>
                    <td className="muted">{r.source_label}</td>
                    <td><span className="num">{r.fields.length}</span></td>
                    <td>
                      <div className="row" style={{ gap: 5 }}>
                        <button className="btn btn-sm" disabled={acting}
                                onClick={() => runSaved(r)}>
                          {L("run")}
                        </button>
                        <button className="btn btn-sm btn-danger"
                                disabled={acting}
                                onClick={() => remove(r)}>
                          {L("del")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        <>
          <div className="card" style={{ padding: 18 }}>
            <div className="row" style={{ gap: 14, flexWrap: "wrap",
                                          alignItems: "flex-end" }}>
              <label className="field" style={{ minWidth: 180 }}>
                <span className="label">{L("source")}</span>
                <select className="select" value={src}
                        onChange={(e) => {
                          setSrc(e.target.value);
                          setPicked([]);
                          setResult(null);
                        }}>
                  {sources.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </label>
              <div className="field" style={{ minWidth: 150 }}>
                <label className="label">{L("from")}</label>
                <DateField value={from} onChange={setFrom} />
              </div>
              <div className="field" style={{ minWidth: 150 }}>
                <label className="label">{L("to")}</label>
                <DateField value={to} onChange={setTo} />
              </div>
            </div>

            <div style={{ marginTop: 18 }}>
              <div className="spread">
                <span className="label">{L("fields")}</span>
                <span className="muted" style={{ fontSize: ".78rem" }}>
                  {L("fieldsHint")}
                </span>
              </div>
              <div className="row" style={{ gap: 6, flexWrap: "wrap",
                                            marginTop: 8 }}>
                {fields.map((f) => {
                  const on = picked.includes(f.key);
                  return (
                    <button key={f.key} type="button"
                            className={`btn btn-sm ${on ? "btn-primary" : "btn-ghost"}`}
                            onClick={() => toggle(f.key)}>
                      {f.label_ar}
                    </button>
                  );
                })}
              </div>
            </div>

            {picked.length > 0 && (
              <div style={{ marginTop: 14, fontSize: ".85rem" }}>
                <span className="muted">{L("chosen")}: </span>
                {picked.map((k) => (
                  <span key={k} className="badge"
                        style={{ marginInlineEnd: 4 }}>
                    {fields.find((f) => f.key === k)?.label_ar || k}
                  </span>
                ))}
              </div>
            )}

            <div className="row" style={{ gap: 10, marginTop: 18,
                                          flexWrap: "wrap",
                                          alignItems: "flex-end" }}>
              <button className="btn btn-primary" disabled={acting}
                      onClick={preview}>
                {acting ? L("previewing") : L("preview")}
              </button>
              <label className="field" style={{ minWidth: 200 }}>
                <span className="label">{L("name")}</span>
                <input className="input" value={name}
                       onChange={(e) => setName(e.target.value)} />
              </label>
              <label className="row" style={{ gap: 8, cursor: "pointer",
                                              paddingBottom: 8 }}>
                <input type="checkbox" checked={shared}
                       onChange={(e) => setShared(e.target.checked)} />
                <span style={{ fontSize: ".86rem" }}>{L("shared")}</span>
              </label>
              <button className="btn" disabled={acting || !name.trim()
                                                || !picked.length}
                      onClick={save} style={{ marginBottom: 8 }}>
                {L("save")}
              </button>
            </div>
          </div>

          {result && (
            <div className="card" style={{ overflow: "hidden" }}>
              <div className="spread" style={{ padding: "14px 18px" }}>
                <div>
                  <strong>{result.title_ar}</strong>
                  <span className="muted" style={{ marginInlineStart: 8,
                                                   fontSize: ".85rem" }}>
                    <span className="num">{result.count}</span> {L("rows")}
                  </span>
                </div>
                <button className="btn btn-sm" onClick={exportCsv}>
                  {L("exportX")}
                </button>
              </div>

              {result.truncated && (
                <div style={{ padding: "8px 18px", fontSize: ".82rem",
                              background: "var(--copper-soft)",
                              color: "var(--copper)" }}>
                  {L("truncated")}
                </div>
              )}

              {result.rows.length === 0 ? (
                <div style={{ padding: 30, textAlign: "center",
                              color: "var(--ink-3)" }}>{L("empty")}</div>
              ) : (
                <div style={{ overflowX: "auto", maxHeight: "60vh" }}>
                  <table className="table">
                    <thead>
                      <tr>
                        {result.columns.map((c) => (
                          <th key={c.key}>{c.label_ar}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.rows.slice(0, 300).map((row, i) => (
                        <tr key={i}>
                          {result.columns.map((c) => (
                            <td key={c.key}
                                className={["number", "money"].includes(c.kind)
                                  ? "num" : ""}>
                              {row[c.key] === null
                                || row[c.key] === undefined
                                ? "—" : String(row[c.key])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
