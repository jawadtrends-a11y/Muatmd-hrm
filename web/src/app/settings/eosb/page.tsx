"use client";
/**
 * إعدادات مكافأة نهاية الخدمة (ق-218).
 *
 * ⚠️⚠️ **وشاشةٌ موضوعية لا حقلٌ في نموذجٍ طويل** (قرار جواد):
 * **فالإعدادات كلّها بطاقات** — ومن يريد المكافأة يذهب إليها.
 */
import { useEffect, useState } from "react";

import { apiGet, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import SettingRow from "@/components/SettingRow";
import { IcAlert, IcCheck } from "@/components/Icons";

const T: Dict = {
  title: { ar: "مكافأة نهاية الخدمة", en: "End-of-service" },
  sub: {
    ar: "الأجر الذي تُحتسب عليه المكافأة",
    en: "The wage the award is computed on",
  },
  basis: { ar: "الأجر المحتسب للمكافأة", en: "EOSB wage basis" },
  basisHint: {
    ar: "⚠️ يجب تحديده قبل أول مسير مستحقات — والصمت هنا قرارٌ ماليّ لم يتّخذه أحد",
    en: "Must be set before the first settlement run",
  },
  notSet: { ar: "لم يُحدَّد بعد", en: "Not set" },
  basicOnly: { ar: "الأساسي فقط", en: "Basic only" },
  basicHousing: { ar: "الأساسي + السكن", en: "Basic + housing" },
  basicHousingTransport: {
    ar: "الأساسي + السكن + النقل",
    en: "Basic + housing + transport",
  },
  basicAll: { ar: "الأجر الكامل", en: "Full wage" },
  flagged: { ar: "حسب أعلام البنود", en: "By component flags" },
  unpaid: {
    ar: "استبعاد الإجازة بلا أجر من مدّة الخدمة",
    en: "Exclude unpaid leave from service",
  },
  unpaidHint: {
    ar: "⚠️ الأصل احتسابها — واستبعادها يقلّل المكافأة، فليكن بعلمٍ لا سهوًا",
    en: "Excluding reduces the award",
  },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  saved: { ar: "حُفظ", en: "Saved" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  denied: { ar: "لا تملك صلاحية هذه الإعدادات", en: "Not allowed" },
  back: { ar: "← الإعدادات", en: "← Settings" },
};

type S = {
  eosb_wage_basis: string;
  exclude_unpaid_leave_from_service: boolean;
};

export default function EosbSettingsPage() {
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
                                   color: "var(--ink-3)" }}>
      {L("loading")}
    </div>
  );
  if (denied) return (
    <div className="card" style={{ padding: 30, textAlign: "center" }}>
      {L("denied")}
    </div>
  );

  return (
    <div className="stack">
      <a className="btn btn-sm btn-ghost" href="/settings"
         style={{ alignSelf: "flex-start" }}>{L("back")}</a>

      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".92rem",
                                        marginTop: 3 }}>
          {L("sub")}
        </div>
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
          <SettingRow label={L("basis")} hint={L("basisHint")}>
            <select className="select" value={data.eosb_wage_basis}
                    onChange={(e) => set("eosb_wage_basis",
                                         e.target.value)}>
              {data.eosb_wage_basis === "not_set" && (
                <option value="not_set">{L("notSet")}</option>
              )}
              <option value="basic_only">{L("basicOnly")}</option>
              <option value="basic_housing">{L("basicHousing")}</option>
              <option value="basic_housing_transport">
                {L("basicHousingTransport")}
              </option>
              <option value="basic_all">{L("basicAll")}</option>
              {data.eosb_wage_basis === "flagged" && (
                <option value="flagged">{L("flagged")}</option>
              )}
            </select>
          </SettingRow>

          <SettingRow label={L("unpaid")} hint={L("unpaidHint")}>
            <select className="select"
                    value={data.exclude_unpaid_leave_from_service
                      ? "1" : "0"}
                    onChange={(e) => set(
                      "exclude_unpaid_leave_from_service",
                      e.target.value === "1")}>
              <option value="0">{L("no")}</option>
              <option value="1">{L("yes")}</option>
            </select>
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
