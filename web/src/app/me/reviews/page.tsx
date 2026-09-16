"use client";
/**
 * تقييماتي (ق-146).
 *
 * ⚠️⚠️ **وتقييم المدير مجهول** — لا يُحفظ اسمك، ولا يُعرض إلا
 * مجمَّعًا.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "تقييماتي", en: "My reviews" },
  sub: {
    ar: "قيّم نفسك، وقيّم مديرك — وتقييم المدير مجهول",
    en: "Rate yourself and your manager — the latter is anonymous",
  },
  cycle: { ar: "الدورة", en: "Cycle" },
  selfReview: { ar: "تقييم ذاتيّ", en: "Self review" },
  upward: { ar: "تقييم مديري", en: "Rate my manager" },
  done: { ar: "تمّ", en: "Done" },
  myScores: { ar: "درجاتي المعتمدة", en: "My approved scores" },
  kpi: { ar: "المؤشّر", en: "KPI" },
  target: { ar: "المستهدَف", en: "Target" },
  actual: { ar: "الفعليّ", en: "Actual" },
  score: { ar: "الدرجة", en: "Score" },
  weight: { ar: "الوزن", en: "Weight" },
  empty: { ar: "لا درجات معتمدة بعد", en: "No approved scores yet" },
  noCycles: { ar: "لا دورات مفتوحة", en: "No open cycles" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "تقييم الأداء غير متاح", en: "Not available" },
  rate: { ar: "التقدير من ٥", en: "Rating out of 5" },
  strengths: { ar: "نقاط القوّة", en: "Strengths" },
  improvements: { ar: "ما يُحسَّن", en: "To improve" },
  comment: { ar: "ملاحظات", en: "Comments" },
  anonNote: {
    ar: "⚠️ لا يُحفظ اسمك مع هذا التقييم، ولا يُعرض لمديرك إلا مجمَّعًا مع ثلاثة تقييمات فأكثر. ⚠️ لكن احذر أن تكشف نفسك بتفاصيل لا يعرفها غيرك.",
    en: "Your name is never stored; shown only in aggregate. Avoid identifying details.",
  },
  selfNote: {
    ar: "هذا تقييمك لنفسك — منسوبٌ إليك ويراه مديرك",
    en: "Your self review — attributed to you",
  },
  send: { ar: "إرسال", en: "Submit" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  sentOk: { ar: "سُجّل تقييمك", en: "Submitted" },
  noManager: { ar: "لا مدير مسجَّل لك", en: "No manager on record" },
};

type Cycle = {
  id: number; name_ar: string;
  self_enabled: boolean; upward_enabled: boolean; self_done: boolean;
};
type Score = {
  id: number; kpi: string; target: string; actual: string | null;
  score: number | null; weight: number;
};

export default function MyReviewsPage() {
  const { L } = useT(T);
  const [data, setData] = useState<{
    cycles: Cycle[]; manager: string; manager_id: number | null;
    my_scores: Score[] } | null>(null);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [dialog, setDialog] = useState<{
    cycle: Cycle; kind: "self" | "upward" } | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setData(await apiGet("/me/reviews/"));
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

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

      {!data?.cycles.length ? (
        <div className="card" style={{ padding: 36, textAlign: "center",
                                       color: "var(--ink-3)" }}>
          {L("noCycles")}
        </div>
      ) : (
        <div className="stack" style={{ gap: 12 }}>
          {data.cycles.map((c) => (
            <div key={c.id} className="card" style={{ padding: 18 }}>
              <div style={{ fontWeight: 600 }}>{c.name_ar}</div>
              <div className="row" style={{ gap: 8, marginTop: 12,
                                            flexWrap: "wrap" }}>
                {c.self_enabled && (
                  c.self_done ? (
                    <span className="badge badge-ok">
                      {L("selfReview")} — {L("done")}
                    </span>
                  ) : (
                    <button className="btn btn-sm btn-primary"
                            onClick={() => setDialog({ cycle: c,
                                                       kind: "self" })}>
                      {L("selfReview")}
                    </button>
                  )
                )}
                {c.upward_enabled && (
                  data.manager_id ? (
                    <button className="btn btn-sm"
                            onClick={() => setDialog({ cycle: c,
                                                       kind: "upward" })}>
                      {L("upward")} — {data.manager}
                    </button>
                  ) : (
                    <span className="muted" style={{ fontSize: ".82rem" }}>
                      {L("noManager")}
                    </span>
                  )
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <h3 style={{ fontSize: "1rem", marginTop: 8 }}>{L("myScores")}</h3>
      <div className="card" style={{ overflow: "hidden" }}>
        {!data?.my_scores.length ? (
          <div style={{ padding: 36, textAlign: "center",
                        color: "var(--ink-3)" }}>
            <IcDoc size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{L("kpi")}</th>
                <th style={{ width: 100 }}>{L("target")}</th>
                <th style={{ width: 100 }}>{L("actual")}</th>
                <th style={{ width: 90 }}>{L("weight")}</th>
                <th style={{ width: 90 }}>{L("score")}</th>
              </tr>
            </thead>
            <tbody>
              {data.my_scores.map((s) => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 500 }}>{s.kpi}</td>
                  <td><span className="num">{s.target}</span></td>
                  <td><span className="num">{s.actual ?? "—"}</span></td>
                  <td><span className="num">{s.weight}%</span></td>
                  <td>
                    {s.score !== null ? (
                      <span className="num" style={{
                        color: s.score >= 100 ? "var(--ok)"
                          : s.score >= 70 ? undefined
                          : "var(--danger)" }}>
                        {s.score}
                      </span>
                    ) : <span className="muted">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {dialog && (
        <ReviewDialog d={dialog} managerId={data?.manager_id ?? null}
                      L={L} onClose={() => setDialog(null)}
                      onSaved={async () => {
                        setDialog(null);
                        setMsg(L("sentOk"));
                        setTimeout(() => setMsg(""), 3500);
                        await load();
                      }} />
      )}
    </div>
  );
}


function ReviewDialog({ d, managerId, L, onClose, onSaved }: {
  d: { cycle: Cycle; kind: "self" | "upward" };
  managerId: number | null;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [score, setScore] = useState(4);
  const [strengths, setStrengths] = useState("");
  const [improvements, setImprovements] = useState("");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/me/reviews/", {
        cycle_id: d.cycle.id, kind: d.kind,
        manager_id: d.kind === "upward" ? managerId : undefined,
        score, strengths, improvements, comment,
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
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 470,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>
          {d.kind === "self" ? L("selfReview") : L("upward")}
        </h3>
        <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
          {d.cycle.name_ar}
        </div>

        {/* ⚠️ التنبيه أوّلًا — فمن يكتب يكتب على بصيرة */}
        <div style={{
          background: d.kind === "upward" ? "var(--copper-soft)"
            : "var(--teal-soft)",
          color: d.kind === "upward" ? "var(--copper)" : "var(--teal)",
          padding: "11px 14px", borderRadius: "var(--radius-sm)",
          fontSize: ".82rem", lineHeight: 1.9, marginTop: 14 }}>
          {d.kind === "upward" ? L("anonNote") : L("selfNote")}
        </div>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 12 }}>
            {err}
          </div>
        )}

        <div className="field" style={{ marginTop: 16 }}>
          <span className="label">{L("rate")}</span>
          <div className="row" style={{ gap: 6, marginTop: 4 }}>
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} type="button"
                      className={`btn btn-sm ${score === n ? "btn-primary" : "btn-ghost"}`}
                      style={{ minWidth: 44 }}
                      onClick={() => setScore(n)}>
                {n}
              </button>
            ))}
          </div>
        </div>

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("strengths")}</span>
          <textarea className="input" rows={2} value={strengths}
                    onChange={(e) => setStrengths(e.target.value)} />
        </label>

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("improvements")}</span>
          <textarea className="input" rows={2} value={improvements}
                    onChange={(e) => setImprovements(e.target.value)} />
        </label>

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("comment")}</span>
          <textarea className="input" rows={2} value={comment}
                    onChange={(e) => setComment(e.target.value)} />
        </label>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary" disabled={busy}
                  onClick={submit}>{busy ? "…" : L("send")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}
