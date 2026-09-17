"use client";
/**
 * سياسة السلف (ق-218).
 *
 * ⚠️ **وحدودُ السلفة قرارٌ ماليّ**: **من يُقرض موظفًا بلا سقفٍ
 * يُقرض شركته** — فالسقف يُضبط هنا لا في كل طلب.
 */
import { useEffect, useState } from "react";

import { apiGet, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import SettingRow from "@/components/SettingRow";
import { IcAlert, IcCheck } from "@/components/Icons";

const T: Dict = {
  title: { ar: "سياسة السلف", en: "Advances policy" },
  sub: { ar: "الحدود والأقساط وشروط المنح",
         en: "Limits, instalments and conditions" },
  enabled: { ar: "السلف مفعّلة", en: "Advances enabled" },
  enabledHint: { ar: "تعطيلها يُخفي الطلب ولا يمسّ القائم",
                 en: "Disabling hides the request only" },
  maxAmount: { ar: "الحدّ الأقصى للمبلغ", en: "Max amount" },
  maxAmountHint: { ar: "صفرٌ يعني: بلا حدٍّ بالمبلغ",
                   en: "Zero means no cap" },
  maxMonths: { ar: "الحدّ الأقصى (أشهر راتب)", en: "Max salary months" },
  maxMonthsHint: {
    ar: "⚠️ والأقلّ من الحدّين هو المعتمد — فالراتب يختلف بين موظف وآخر",
    en: "The lower of the two caps applies",
  },
  maxInstallments: { ar: "أقصى عدد أقساط", en: "Max instalments" },
  maxInstallmentsHint: {
    ar: "والسداد يمتدّ عليها — فلا يُثقل الراتب",
    en: "Repayment spreads over these",
  },
  blockOutstanding: { ar: "منع سلفةٍ جديدة مع سلفةٍ قائمة",
                      en: "Block if outstanding" },
  blockHint: {
    ar: "⚠️ فسلفتان على راتبٍ واحد تُرهقانه — والمنع يحمي الموظف قبل الشركة",
    en: "Two advances on one salary strain it",
  },
  on: { ar: "مفعّل", en: "On" },
  off: { ar: "معطّل", en: "Off" },
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
  advances_enabled: boolean;
  advance_max_amount: string | number;
  advance_max_months_of_salary: string | number;
  advance_max_installments: number;
  advance_block_if_outstanding: boolean;
};

export default function AdvancesPolicyPage() {
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
          <SettingRow label={L("enabled")} hint={L("enabledHint")}>
            <select className="select"
                    value={data.advances_enabled ? "1" : "0"}
                    onChange={(e) => set("advances_enabled",
                                         e.target.value === "1")}>
              <option value="1">{L("on")}</option>
              <option value="0">{L("off")}</option>
            </select>
          </SettingRow>

          {/* ⚠️ **ولا حدودَ لما هو معطَّل** */}
          {data.advances_enabled && (
            <>
              <SettingRow label={L("maxAmount")}
                          hint={L("maxAmountHint")}>
                <input className="input num" type="number" min={0}
                       style={{ maxWidth: 150 }}
                       value={String(data.advance_max_amount ?? 0)}
                       onChange={(e) => set("advance_max_amount",
                                            e.target.value)} />
              </SettingRow>

              <SettingRow label={L("maxMonths")}
                          hint={L("maxMonthsHint")}>
                <input className="input num" type="number" min={0}
                       step="0.5" style={{ maxWidth: 150 }}
                       value={String(
                         data.advance_max_months_of_salary ?? 0)}
                       onChange={(e) => set(
                         "advance_max_months_of_salary",
                         e.target.value)} />
              </SettingRow>

              <SettingRow label={L("maxInstallments")}
                          hint={L("maxInstallmentsHint")}>
                <input className="input num" type="number" min={1}
                       style={{ maxWidth: 150 }}
                       value={String(
                         data.advance_max_installments ?? 12)}
                       onChange={(e) => set(
                         "advance_max_installments",
                         Number(e.target.value))} />
              </SettingRow>

              <SettingRow label={L("blockOutstanding")}
                          hint={L("blockHint")}>
                <select className="select"
                        value={data.advance_block_if_outstanding
                          ? "1" : "0"}
                        onChange={(e) => set(
                          "advance_block_if_outstanding",
                          e.target.value === "1")}>
                  <option value="1">{L("yes")}</option>
                  <option value="0">{L("no")}</option>
                </select>
              </SettingRow>
            </>
          )}

          <button className="btn btn-primary" style={{ marginTop: 18 }}
                  disabled={saving} onClick={save}>
            {saving ? L("saving") : L("save")}
          </button>
        </div>
      )}
    </div>
  );
}
