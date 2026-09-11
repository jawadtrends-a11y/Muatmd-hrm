"use client";
/**
 * سياساتي (ق-129).
 *
 * ⚠️ **وما لم أُقرّ به أوّلًا** — فالترتيب تنبيهٌ لا عرض.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "السياسات", en: "Policies" },
  sub: {
    ar: "سياسات المنشأة — اقرأها وأقرّ بعلمك بها",
    en: "Company policies — read and acknowledge",
  },
  needsAck: { ar: "بانتظار إقرارك", en: "Needs your acknowledgement" },
  acked: { ar: "أقررت بها", en: "Acknowledged" },
  read: { ar: "قراءة", en: "Read" },
  ack: { ar: "أقرّ بعلمي", en: "I acknowledge" },
  acking: { ar: "جارٍ…", en: "Working…" },
  close: { ar: "إغلاق", en: "Close" },
  version: { ar: "النسخة", en: "Version" },
  effective: { ar: "سريان من", en: "Effective from" },
  ackHint: {
    ar: "بالضغط تُقرّ بأنك قرأت السياسة وعلمت بمحتواها",
    en: "You confirm you have read and understood this policy",
  },
  done: { ar: "سُجّل إقرارك", en: "Acknowledged" },
  empty: { ar: "لا سياسات منشورة", en: "No policies published" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "السياسات غير متاحة في باقتكم", en: "Not in your plan" },
  viewOnly: { ar: "للاطّلاع", en: "For information" },
};

type Row = {
  id: number; code: string; title_ar: string; version: number;
  effective_from: string; requires_ack: boolean;
  acknowledged: boolean; needs_ack: boolean;
};

export default function MyPoliciesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [shown, setShown] = useState<Record<string, unknown> | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setRows(await apiGet<Row[]>("/me/policies/"));
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const open = async (r: Row) => {
    setErr("");
    try {
      const list = await apiGet<{ policies: Record<string, unknown>[] }>(
        "/policies/").catch(() => null);
      const full = list?.policies?.find((p) => p.id === r.id);
      setShown(full || { ...r, body_ar: "" });
    } catch {
      setShown({ ...r, body_ar: "" });
    }
  };

  const ack = async (id: number) => {
    setActing(true); setErr("");
    try {
      await apiPost(`/policies/${id}/acknowledge/`, {});
      setMsg(L("done"));
      setTimeout(() => setMsg(""), 4000);
      setShown(null);
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

  const pending = rows.filter((r) => r.needs_ack).length;

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

      {pending > 0 && (
        <div className="card" style={{ padding: 14,
                                       borderColor: "var(--copper)",
                                       background: "var(--copper-soft)",
                                       color: "var(--copper)" }}>
          <IcAlert size={15} /> {L("needsAck")} —{" "}
          <span className="num">{pending}</span>
        </div>
      )}

      <div className="card" style={{ overflow: "hidden" }}>
        {rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>
            <IcDoc size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{L("title")}</th>
                <th style={{ width: 90 }}>{L("version")}</th>
                <th style={{ width: 120 }}>{L("effective")}</th>
                <th style={{ width: 150 }}>{L("acked")}</th>
                <th style={{ width: 100 }} />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td style={{ fontWeight: 500 }}>{r.title_ar}</td>
                  <td><span className="num">{r.version}</span></td>
                  <td><span className="num">{r.effective_from}</span></td>
                  <td>
                    {!r.requires_ack ? (
                      <span className="muted"
                            style={{ fontSize: ".8rem" }}>
                        {L("viewOnly")}
                      </span>
                    ) : r.acknowledged ? (
                      <span className="badge badge-ok">{L("acked")}</span>
                    ) : (
                      <span className="badge badge-warn">
                        {L("needsAck")}
                      </span>
                    )}
                  </td>
                  <td>
                    <button className="btn btn-sm"
                            onClick={() => open(r)}>{L("read")}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {shown && (
        <div onClick={() => setShown(null)} style={{
          position: "fixed", inset: 0, background: "rgba(16,28,38,.5)",
          display: "grid", placeItems: "center", padding: 20, zIndex: 80,
          overflowY: "auto",
        }}>
          <div className="card" style={{ padding: 26, maxWidth: 640,
                                         width: "100%", maxHeight: "88vh",
                                         overflowY: "auto" }}
               onClick={(e) => e.stopPropagation()}>
            <h2 style={{ margin: 0, fontSize: "1.1rem" }}>
              {String(shown.title_ar || "")}
            </h2>
            <div className="muted" style={{ fontSize: ".8rem",
                                            marginTop: 4 }}>
              {L("version")} <span className="num">
                {String(shown.version ?? "")}
              </span>
              {" · "}{L("effective")}{" "}
              {String(shown.effective_from ?? "")}
            </div>

            <div style={{ whiteSpace: "pre-wrap", lineHeight: 2,
                          marginTop: 18, fontSize: ".94rem" }}>
              {String(shown.body_ar || "")}
            </div>

            <div className="row" style={{ gap: 8, marginTop: 22,
                                          alignItems: "center" }}>
              {Boolean(shown.requires_ack) && !shown.acknowledged && (
                <>
                  <button className="btn btn-primary" disabled={acting}
                          onClick={() => ack(Number(shown.id))}>
                    {acting ? L("acking") : L("ack")}
                  </button>
                  <span className="muted" style={{ fontSize: ".78rem" }}>
                    {L("ackHint")}
                  </span>
                </>
              )}
              <button className="btn"
                      onClick={() => setShown(null)}>{L("close")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
