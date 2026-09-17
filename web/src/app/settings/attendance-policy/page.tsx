"use client";
/**
 * إعدادات الحضور والتواجد (ق-218).
 *
 * ⚠️ **وشاشةٌ موضوعية**: فمن يريد البصمة **يذهب إليها** لا يبحث
 * في نموذجٍ طويل.
 */
import { useEffect, useState } from "react";

import { apiGet, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import SettingRow from "@/components/SettingRow";
import { IcAlert, IcCheck } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الحضور والتواجد", en: "Attendance & presence" },
  sub: { ar: "البصمة وتتبّع الموقع وأنشطة العمل",
         en: "Punch, presence and activities" },
  presenceOn: { ar: "تتبّع التواجد في الموقع", en: "Presence tracking" },
  presenceHint: {
    ar: "داخل الموقع أو خارجه أثناء الفترة — ولا يُحفظ موقع الموظف",
    en: "In or out of site — the location itself is not stored",
  },
  tolerance: { ar: "سماح الخروج من الموقع (دقائق)",
               en: "Out-of-site tolerance (min)" },
  toleranceHint: {
    ar: "⚠️ خروجٌ أقلّ من ذلك لا يُحتسب — فالشبكة تتذبذب",
    en: "Shorter gaps are ignored — networks drift",
  },
  activitiesOn: { ar: "أنشطة العمل", en: "Work activities" },
  activitiesHint: {
    ar: "مهامّ يومية يُسندها المديرون — وتفعيلها لا يُلزمهم",
    en: "Daily tasks assigned by managers",
  },
  mobilePunch: { ar: "بصمة الجوال", en: "Mobile punch" },
  mobilePunchHint: {
    ar: "⚠️ والموقع يُفحص عند البصمة — فمن خارج النطاق يُمنع",
    en: "Location is checked at punch time",
  },
  enabled: { ar: "مفعّلة", en: "Enabled" },
  disabled: { ar: "معطّلة", en: "Disabled" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  saved: { ar: "حُفظ", en: "Saved" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  denied: { ar: "لا تملك صلاحية هذه الإعدادات", en: "Not allowed" },
  back: { ar: "← الإعدادات", en: "← Settings" },
};

type S = {
  presence_tracking_enabled: boolean;
  presence_tolerance_minutes: number;
  activities_enabled: boolean;
  allow_mobile_punch: boolean;
};

export default function AttendancePolicyPage() {
  const { L } = useT(T);
  const [data, setData] = useState<S | null>(null);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [denied, setDenied] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    apiGet<S>("/payroll/settings/")
      .then((d) => { setData(d); setBusy(false); })
      .catch((e: ApiError) => { setDenied(e.isForbidden); setBusy(false); });
  }, []);

  const set = (k: keyof S, v: unknown) =>
    setData((s) => (s ? { ...s, [k]: v } : s));

  const save = async () => {
    if (!data) return;
    setSaving(true);
    setMsg("");
    setErr("");
    try {
      await apiPut("/payroll/settings/", data);
      setMsg(L("saved"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setSaving(false); }
  };

  if (busy) return (
    <div className="card" style={{ padding: 40, textAlign: "center",
                                   color: "var(--ink-3)" }}>{L("loading")}</div>
  );
  if (denied) return (
    <div className="card" style={{ padding: 30, textAlign: "center" }}>
      {L("denied")}
    </div>
  );

  const Toggle = ({ k }: { k: keyof S }) => (
    <select className="select" value={data![k] ? "1" : "0"}
            onChange={(e) => set(k, e.target.value === "1")}>
      <option value="1">{L("enabled")}</option>
      <option value="0">{L("disabled")}</option>
    </select>
  );

  return (
    <div className="stack">
      <a className="btn btn-sm btn-ghost" href="/settings"
         style={{ alignSelf: "flex-start" }}>{L("back")}</a>

      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".92rem",
                                        marginTop: 3 }}>{L("sub")}</div>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && (
        <div className="card" style={{ borderColor: "var(--danger)",
                                       color: "var(--danger)" }}>
          <IcAlert size={17} /> {err}
        </div>
      )}

      {data && (
        <div className="card" style={{ padding: 22 }}>
          <SettingRow label={L("mobilePunch")} hint={L("mobilePunchHint")}>
            <Toggle k="allow_mobile_punch" />
          </SettingRow>

          <SettingRow label={L("presenceOn")} hint={L("presenceHint")}>
            <Toggle k="presence_tracking_enabled" />
          </SettingRow>

          {/* ⚠️ **والسماح لا معنى له بلا تتبّع** */}
          {data.presence_tracking_enabled && (
            <SettingRow label={L("tolerance")} hint={L("toleranceHint")}>
              <input className="input num" type="number" min={0}
                     style={{ maxWidth: 130 }}
                     value={String(data.presence_tolerance_minutes ?? 60)}
                     onChange={(e) => set("presence_tolerance_minutes",
                                          Number(e.target.value))} />
            </SettingRow>
          )}

          <SettingRow label={L("activitiesOn")} hint={L("activitiesHint")}>
            <Toggle k="activities_enabled" />
          </SettingRow>

          <button className="btn btn-primary" style={{ marginTop: 18 }}
                  disabled={saving} onClick={save}>
            {saving ? L("saving") : L("save")}
          </button>
        </div>
      )}
    </div>
  );
}
