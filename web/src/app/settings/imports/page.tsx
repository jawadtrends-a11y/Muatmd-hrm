"use client";
/**
 * الاستيراد من نظامٍ سابق (ق-170 و ق-171).
 *
 * **بلاغ جواد:** شركةٌ تنتقل من نظامٍ آخر **لا تُعيد إدخال
 * بياناتها يدويًّا**.
 *
 * ⚠️⚠️ **والخطأ في سطرٍ يوقف الملفّ كلّه**: فاستيرادٌ نصفُه
 * ناقصٌ **أسوأ من لا شيء**.
 */
import { useEffect, useRef, useState } from "react";

import { apiGet, apiUpload, downloadFile, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الاستيراد من نظامٍ سابق", en: "Import" },
  sub: {
    ar: "انقل موظفيك وأرصدتهم وحضورهم بلا إدخالٍ يدويّ",
    en: "Move employees, balances and attendance",
  },
  tabEmp: { ar: "الموظفون", en: "Employees" },
  tabBal: { ar: "أرصدة الإجازات", en: "Leave balances" },
  tabDays: { ar: "الحضور", en: "Attendance" },
  step1: { ar: "١ — نزّل القالب وعبّئه", en: "1 — Download template" },
  step2: { ar: "٢ — ارفع الملفّ وراجع المعاينة", en: "2 — Upload" },
  download: { ar: "تنزيل القالب", en: "Download template" },
  pick: { ar: "اختر الملفّ", en: "Choose file" },
  checking: { ar: "جارٍ الفحص…", en: "Checking…" },
  leaveType: { ar: "نوع الإجازة", en: "Leave type" },
  valid: { ar: "صالح", en: "Valid" },
  invalid: { ar: "به خطأ", en: "With errors" },
  row: { ar: "السطر", en: "Row" },
  blocked: {
    ar: "⚠️ لا يُستورَد الملفّ حتى تُصلَح كل الأخطاء — فاستيرادٌ نصفُه ناقصٌ أسوأ من لا شيء",
    en: "All errors must be fixed first",
  },
  doImport: { ar: "تنفيذ الاستيراد", en: "Import now" },
  importedOk: { ar: "استُورد", en: "Imported" },
  record: { ar: "سجلًّا", en: "records" },
  noticeBal: {
    ar: "⚠️ الرصيد افتتاحيٌّ بتاريخه — والاستحقاق اليوميّ يُضاف إليه من ذلك التاريخ",
    en: "Balance is an opening figure at its date",
  },
  noticeDays: {
    ar: "⚠️ لا يُستورَد يومٌ في مسيرٍ معتمد — فالأجر احتُسب عليه",
    en: "Days inside an approved payroll are locked",
  },
};

type Preview = {
  total: number; valid: number; invalid: number; can_import: boolean;
  errors: { row: number; employee_no: string; errors: string[] }[];
};
type LType = { id: number; code: string; name_ar: string };
type TabKey = "emp" | "bal" | "days";

const PATHS: Record<TabKey, { tpl: string; up: string }> = {
  emp: { tpl: "/employees/import/template/",
         up: "/employees/import/preview/" },
  bal: { tpl: "/leaves/balances/import/template/",
         up: "/leaves/balances/import/" },
  days: { tpl: "/attendance/import/template/",
          up: "/attendance/import/" },
};

export default function ImportsPage() {
  const { L } = useT(T);
  const [tab, setTab] = useState<TabKey>("emp");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [types, setTypes] = useState<LType[]>([]);
  const [typeId, setTypeId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    apiGet<LType[] | { types: LType[] }>("/leaves/types/")
      .then((d) => {
        const list = Array.isArray(d) ? d : (d.types || []);
        setTypes(list);
        if (list.length) setTypeId(String(list[0].id));
      })
      .catch(() => setTypes([]));
  }, []);

  // ⚠️ **وتبديل التبويب يمسح المعاينة** — فمعاينةُ ملفٍّ آخر تُضلّل
  useEffect(() => {
    setFile(null); setPreview(null); setErr(""); setMsg("");
  }, [tab]);

  const send = async (f: File, execute: boolean) => {
    setBusy(true); setErr("");
    try {
      const extra: Record<string, string> = {};
      if (tab === "bal") extra.leave_type_id = typeId;
      if (execute) extra.execute = "1";

      const out = await apiUpload<Preview & { imported?: number;
                                              created?: number }>(
        PATHS[tab].up, f, "file", extra);

      if (execute) {
        const n = out.imported ?? out.created ?? 0;
        setMsg(`${L("importedOk")} ${n} ${L("record")}`);
        setPreview(null);
        setFile(null);
      } else {
        setPreview(out);
      }
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

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
        {(["emp", "bal", "days"] as const).map((t) => (
          <button key={t}
                  className={`btn btn-sm ${tab === t ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setTab(t)}>
            {t === "emp" ? L("tabEmp")
              : t === "bal" ? L("tabBal") : L("tabDays")}
          </button>
        ))}
      </div>

      {tab === "bal" && (
        <div style={{ background: "var(--copper-soft)",
                      color: "var(--copper)", padding: "10px 13px",
                      borderRadius: "var(--radius-sm)",
                      fontSize: ".83rem", lineHeight: 1.9 }}>
          {L("noticeBal")}
        </div>
      )}
      {tab === "days" && (
        <div style={{ background: "var(--copper-soft)",
                      color: "var(--copper)", padding: "10px 13px",
                      borderRadius: "var(--radius-sm)",
                      fontSize: ".83rem", lineHeight: 1.9 }}>
          {L("noticeDays")}
        </div>
      )}

      <div className="card" style={{ padding: 16,
                                     background: "var(--paper-2)" }}>
        <div style={{ fontWeight: 500, fontSize: ".9rem" }}>
          {L("step1")}
        </div>
        <button className="btn btn-sm" style={{ marginTop: 8 }}
                onClick={() => downloadFile(PATHS[tab].tpl)}>
          {L("download")}
        </button>
      </div>

      <div className="card" style={{ padding: 16,
                                     background: "var(--paper-2)" }}>
        <div style={{ fontWeight: 500, fontSize: ".9rem" }}>
          {L("step2")}
        </div>

        {tab === "bal" && (
          <label className="field" style={{ marginTop: 10,
                                            maxWidth: 260 }}>
            <span className="label">{L("leaveType")}</span>
            <select className="select" value={typeId}
                    onChange={(e) => setTypeId(e.target.value)}>
              {types.map((t) => (
                <option key={t.id} value={t.id}>{t.name_ar}</option>
              ))}
            </select>
          </label>
        )}

        <input ref={fileRef} type="file" /* ق-214: ⚠️⚠️ **ولا `accept`**: فنافذة الاختيار
                   **كانت تُخفي ملفّات إكسل** مهما ذُكرت
                   امتداداتها وأنواعها — والخادم يفحص الصيغة
                   بنفسه، **فالتقييد هنا يمنع ولا يحمي**. */
               style={{ display: "none" }}
               onChange={(e) => {
                 const f = e.target.files?.[0];
                 if (f) { setFile(f); send(f, false); }
               }} />
        <button className="btn btn-sm" style={{ marginTop: 10 }}
                disabled={busy}
                onClick={() => fileRef.current?.click()}>
          {busy ? L("checking") : (file?.name || L("pick"))}
        </button>
      </div>

      {preview && (
        <div className="card" style={{ padding: 18 }}>
          <div className="row" style={{ gap: 24 }}>
            <div style={{ textAlign: "center" }}>
              <div className="muted" style={{ fontSize: ".76rem" }}>
                {L("valid")}
              </div>
              <div className="num" style={{ fontSize: "1.5rem",
                                            color: "var(--ok)" }}>
                {preview.valid}
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div className="muted" style={{ fontSize: ".76rem" }}>
                {L("invalid")}
              </div>
              <div className="num" style={{ fontSize: "1.5rem",
                color: preview.invalid ? "var(--danger)" : undefined }}>
                {preview.invalid}
              </div>
            </div>
          </div>

          {/* ⚠️ **والأخطاء كلّها تُعرض** — فلا يُكرَّر الرفع عشرًا */}
          {preview.errors?.length > 0 && (
            <>
              <div style={{ background: "var(--copper-soft)",
                            color: "var(--copper)",
                            padding: "10px 13px",
                            borderRadius: "var(--radius-sm)",
                            fontSize: ".82rem", lineHeight: 1.9,
                            marginTop: 12 }}>
                {L("blocked")}
              </div>
              <div style={{ maxHeight: 280, overflowY: "auto",
                            marginTop: 10 }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th style={{ width: 70 }}>{L("row")}</th>
                      <th style={{ width: 110 }}>#</th>
                      <th>—</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.errors.map((e, i) => (
                      <tr key={i}>
                        <td><span className="num">{e.row}</span></td>
                        <td>
                          <span className="num"
                                style={{ fontSize: ".8rem" }}>
                            {e.employee_no}
                          </span>
                        </td>
                        <td style={{ fontSize: ".82rem",
                                     color: "var(--danger)" }}>
                          {e.errors.join(" · ")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {preview.can_import && file && (
            <button className="btn btn-primary" style={{ marginTop: 16 }}
                    disabled={busy}
                    onClick={() => send(file, true)}>
              {busy ? "…" : `${L("doImport")} (${preview.valid})`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
