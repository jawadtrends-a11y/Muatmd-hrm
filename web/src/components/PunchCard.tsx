"use client";

/**
 * بطاقة البصمة (ق-62).
 *
 * زرّان في أعلى الشاشة الرئيسية: أخضر للدخول وأحمر للخروج.
 * الموقع يُقرأ من الجوال ويُتحقق منه في الخادم رياضيًا.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcClock } from "@/components/Icons";

const T: Dict = {
  checkIn: { ar: "تسجيل الدخول", en: "Check in" },
  checkOut: { ar: "تسجيل الخروج", en: "Check out" },
  locating: { ar: "جارٍ تحديد موقعك…", en: "Locating…" },
  sending: { ar: "جارٍ التسجيل…", en: "Recording…" },
  today: { ar: "بصماتك اليوم", en: "Today" },
  noPunches: { ar: "لم تسجّل بصمة بعد", en: "No punches yet" },
  firstIn: { ar: "أول دخول", en: "First in" },
  lastOut: { ar: "آخر خروج", en: "Last out" },
  recorded: { ar: "سُجّلت بصمتك", en: "Recorded" },
  at: { ar: "الساعة", en: "at" },
  site: { ar: "الموقع", en: "Site" },
  distance: { ar: "على بُعد", en: "Distance" },
  meters: { ar: "متر", en: "m" },
  noLocation: {
    ar: "تعذّر تحديد موقعك — فعّل خدمة الموقع في المتصفح",
    en: "Could not get your location — enable location services",
  },
  denied: {
    ar: "رفضت إذن الموقع — فعّله من إعدادات المتصفح لتسجيل البصمة",
    en: "Location permission denied",
  },
  outside: { ar: "خارج نطاق العمل", en: "Outside work area" },
  fixRequest: { ar: "طلب تصحيح بصمة", en: "Request a fix" },
  noSites: {
    ar: "لا موقع عمل مُسند إليك — راجع مدير الموارد البشرية",
    en: "No work site assigned",
  },
  loading: { ar: "…", en: "…" },
};

type Punch = { at: string; source: string; site: string };
type Site = { id: number; name_ar: string; enforced: boolean };
type Data = { punches: Punch[]; sites: Site[] };

export default function PunchCard() {
  const { L } = useT(T);
  const [data, setData] = useState<Data | null>(null);
  const [busy, setBusy] = useState(true);
  const [acting, setActing] = useState<"in" | "out" | null>(null);
  const [phase, setPhase] = useState<"" | "locating" | "sending">("");
  const [ok, setOk] = useState("");
  const [error, setError] = useState("");
  const [outside, setOutside] = useState(false);
  const [hidden, setHidden] = useState(false);

  const load = useCallback(() => {
    apiGet<Data>("/me/punch/")
      .then((d) => { setData(d); setBusy(false); })
      .catch((e: ApiError) => {
        // لا ملف موظف — البطاقة تختفي بلا ضجيج
        if (e.status === 404) setHidden(true);
        setBusy(false);
      });
  }, []);

  useEffect(load, [load]);

  function getPosition(): Promise<GeolocationPosition> {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error(L("noLocation")));
        return;
      }
      navigator.geolocation.getCurrentPosition(resolve, (err) => {
        reject(new Error(
          err.code === err.PERMISSION_DENIED ? L("denied") : L("noLocation")));
      }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
    });
  }

  async function punch(kind: "in" | "out") {
    setActing(kind);
    setError("");
    setOk("");
    setOutside(false);
    setPhase("locating");

    try {
      const pos = await getPosition();
      setPhase("sending");

      const res = await apiPost<{
        at: string; site: string; distance_m: number | null;
      }>("/me/punch/", {
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        accuracy: Math.round(pos.coords.accuracy),
      });

      setOk(
        `${L("recorded")} ${L("at")} ${res.at}` +
        (res.site ? ` — ${res.site}` : "") +
        (res.distance_m != null
          ? ` (${L("distance")} ${res.distance_m} ${L("meters")})` : ""));
      load();
      setTimeout(() => setOk(""), 8000);
    } catch (e) {
      const err = e as ApiError;
      setOutside(err.code === "outside_geofence");
      setError(err.message || String(e));
    } finally {
      setActing(null);
      setPhase("");
    }
  }

  if (hidden) return null;

  const punches = data?.punches ?? [];
  const firstIn = punches[0]?.at;
  const lastOut = punches.length > 1 ? punches[punches.length - 1].at : "";
  const noSites = !busy && (data?.sites?.length ?? 0) === 0;

  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="row" style={{
        gap: 12, flexWrap: "wrap", alignItems: "center",
      }}>
        <button
          className="btn"
          disabled={!!acting || busy || noSites}
          onClick={() => punch("in")}
          style={{
            background: "var(--ok)", color: "#fff", border: "none",
            height: 52, minWidth: 190, fontSize: "1.02rem", fontWeight: 600,
            opacity: (acting || noSites) ? .7 : 1,
          }}
        >
          <IcCheck size={20} />
          {acting === "in"
            ? (phase === "locating" ? L("locating") : L("sending"))
            : L("checkIn")}
        </button>

        <button
          className="btn"
          disabled={!!acting || busy || noSites}
          onClick={() => punch("out")}
          style={{
            background: "var(--danger)", color: "#fff", border: "none",
            height: 52, minWidth: 190, fontSize: "1.02rem", fontWeight: 600,
            opacity: (acting || noSites) ? .7 : 1,
          }}
        >
          <IcClock size={20} />
          {acting === "out"
            ? (phase === "locating" ? L("locating") : L("sending"))
            : L("checkOut")}
        </button>

        <div className="grow" />

        {/* ملخص اليوم */}
        {!busy && punches.length > 0 && (
          <div className="row" style={{ gap: 18 }}>
            <div>
              <div className="muted" style={{ fontSize: ".78rem" }}>
                {L("firstIn")}
              </div>
              <div style={{ fontWeight: 600, color: "var(--ok)" }}>
                <span className="num">{firstIn}</span>
              </div>
            </div>
            {lastOut && (
              <div>
                <div className="muted" style={{ fontSize: ".78rem" }}>
                  {L("lastOut")}
                </div>
                <div style={{ fontWeight: 600 }}>
                  <span className="num">{lastOut}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* الرسائل */}
      {ok && (
        <div style={{
          marginTop: 12, background: "var(--ok-soft)", color: "var(--ok)",
          padding: "10px 13px", borderRadius: "var(--radius-sm)",
          fontWeight: 500, fontSize: ".9rem",
        }}>
          <IcCheck size={16} /> {ok}
        </div>
      )}

      {error && (
        <div style={{
          marginTop: 12, background: "var(--danger-soft)",
          color: "var(--danger)", padding: "11px 14px",
          borderRadius: "var(--radius-sm)", fontSize: ".9rem",
        }}>
          <div className="row" style={{ alignItems: "flex-start" }}>
            <IcAlert size={17} />
            <span className="grow">{error}</span>
          </div>
          {outside && (
            <Link href="/me/requests?type=attendance_fix"
              className="btn btn-sm" style={{ marginTop: 10 }}>
              {L("fixRequest")}
            </Link>
          )}
        </div>
      )}

      {noSites && (
        <div className="muted" style={{ marginTop: 10, fontSize: ".87rem" }}>
          {L("noSites")}
        </div>
      )}

      {!busy && punches.length === 0 && !noSites && !error && !ok && (
        <div className="muted" style={{ marginTop: 10, fontSize: ".87rem" }}>
          {L("noPunches")}
        </div>
      )}
    </div>
  );
}
