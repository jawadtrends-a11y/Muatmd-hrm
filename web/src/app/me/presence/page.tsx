"use client";
/**
 * تواجدي في الموقع (ق-144).
 *
 * ⚠️ **والتتبّع بعلمي لا خفية** — فالشاشة تقول ما يُسجَّل ومتى.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "تواجدي في الموقع", en: "My presence" },
  notice: {
    ar: "يُسجَّل تواجدك داخل موقع العمل أو خارجه أثناء فترتك فقط — ولا يُحفظ موقعك الفعليّ.",
    en: "Only inside/outside is recorded during your shift — your actual location is never stored.",
  },
  notTracked: {
    ar: "لا تتبّع لك — فلا موقعَ محروسٌ مُسنَدٌ إليك",
    en: "You're not tracked — no geofenced site assigned",
  },
  site: { ar: "موقعك", en: "Your site" },
  inShift: { ar: "ضمن فترتك الآن", en: "Within your shift" },
  outShift: { ar: "خارج وقت فترتك", en: "Outside your shift" },
  day: { ar: "اليوم", en: "Day" },
  inside: { ar: "داخل", en: "Inside" },
  outside: { ar: "خارج", en: "Outside" },
  noSignal: { ar: "بلا إشارة", en: "No signal" },
  min: { ar: "د", en: "m" },
  state: { ar: "الحالة", en: "Status" },
  reviewed: { ar: "رُوجع", en: "Reviewed" },
  deducted: { ar: "خُصم", en: "Deducted" },
  none: { ar: "بلا خصم", en: "No deduction" },
  empty: { ar: "لا سجلّ بعد", en: "Nothing recorded yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "التتبّع غير متاح", en: "Not available" },
  sendNow: { ar: "تسجيل تواجدي", en: "Record now" },
  sent: { ar: "سُجّل", en: "Recorded" },
};

type Day = {
  id: number; work_date: string;
  inside_minutes: number; outside_minutes: number;
  no_signal_minutes: number; deductible_minutes: number;
  is_reviewed: boolean; approved_amount: string | null;
};

export default function MyPresencePage() {
  const { L } = useT(T);
  const [info, setInfo] = useState<{
    tracked: boolean; site: string; within_shift: boolean;
    days: Day[] } | null>(null);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      setInfo(await apiGet("/me/presence/"));
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  const send = useCallback(async (silent = false) => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          await apiPost("/presence/ping/", {
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
          });
          if (!silent) {
            setMsg(L("sent"));
            setTimeout(() => setMsg(""), 2500);
          }
          await load();
        } catch (e) {
          if (!silent) {
            setErr(e instanceof ApiError ? e.message : String(e));
          }
        }
      },
      async () => {
        // ⚠️ **ولا إشارة حالةٌ تُسجَّل** — فصمتُ الجهاز ليس غيابًا
        try {
          await apiPost("/presence/ping/", {});
          await load();
        } catch { /* تُتجاهل */ }
      },
      { enableHighAccuracy: false, timeout: 10000 });
  }, [L, load]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!info?.tracked || !info.within_shift) return;
    // كل ١٥ دقيقة — فأقلّ يستنزف البطارية
    timer.current = setInterval(() => send(true), 15 * 60 * 1000);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [info?.tracked, info?.within_shift, send]);

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
      <h1 style={{ margin: 0 }}>{L("title")}</h1>

      {/* ⚠️ الإشعار أوّلًا — فالتتبّع بعلمه */}
      <div style={{ background: "var(--teal-soft)", color: "var(--teal)",
                    padding: "12px 15px",
                    borderRadius: "var(--radius-sm)",
                    fontSize: ".86rem", lineHeight: 1.9 }}>
        {L("notice")}
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      {!info?.tracked ? (
        <div className="card" style={{ padding: 36, textAlign: "center",
                                       color: "var(--ink-3)" }}>
          {L("notTracked")}
        </div>
      ) : (
        <>
          <div className="card" style={{ padding: 18 }}>
            <div className="spread">
              <div>
                <div className="muted" style={{ fontSize: ".8rem" }}>
                  {L("site")}
                </div>
                <div style={{ fontWeight: 600 }}>{info.site}</div>
              </div>
              <span className={`badge ${info.within_shift ? "badge-ok" : ""}`}>
                {info.within_shift ? L("inShift") : L("outShift")}
              </span>
            </div>
            {info.within_shift && (
              <button className="btn btn-sm" style={{ marginTop: 12 }}
                      onClick={() => send(false)}>
                {L("sendNow")}
              </button>
            )}
          </div>

          <div className="card" style={{ overflow: "hidden" }}>
            {info.days.length === 0 ? (
              <div style={{ padding: 36, textAlign: "center",
                            color: "var(--ink-3)" }}>
                <IcDoc size={22} />
                <div style={{ marginTop: 8 }}>{L("empty")}</div>
              </div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: 120 }}>{L("day")}</th>
                    <th style={{ width: 100 }}>{L("inside")}</th>
                    <th style={{ width: 100 }}>{L("outside")}</th>
                    <th>{L("state")}</th>
                  </tr>
                </thead>
                <tbody>
                  {info.days.map((d) => (
                    <tr key={d.id}>
                      <td><span className="num">{d.work_date}</span></td>
                      <td>
                        <span className="num">{d.inside_minutes}</span>
                        <span className="muted"> {L("min")}</span>
                      </td>
                      <td>
                        <span className="num">{d.outside_minutes}</span>
                        <span className="muted"> {L("min")}</span>
                      </td>
                      <td>
                        {d.is_reviewed ? (
                          Number(d.approved_amount || 0) > 0 ? (
                            <span className="badge badge-warn">
                              {L("deducted")} — {d.approved_amount}
                            </span>
                          ) : (
                            <span className="badge badge-ok">
                              {L("none")}
                            </span>
                          )
                        ) : (
                          <span className="muted"
                                style={{ fontSize: ".82rem" }}>—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
