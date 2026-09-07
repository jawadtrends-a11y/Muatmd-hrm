"use client";

/**
 * قوالب ملفات البنوك.
 *
 * كل بنك له صيغة ملف رواتب خاصة — والشركة قد تتعامل مع بنك لم
 * نبنِ قالبه، فتبنيه بنفسها أو تنسخ قالبًا وتعدّله.
 */
import { useCallback, useEffect, useState } from "react";

import { apiDelete, apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import { IcAlert, IcCheck, IcPlus, IcWallet, IcX } from "@/components/Icons";

const T: Dict = {
  nameEn: { ar: "الاسم بالإنجليزية", en: "Name (English)" },
  title: { ar: "قوالب البنوك", en: "Bank templates" },
  subtitle: {
    ar: "صيغة ملف الرواتب لكل بنك",
    en: "Payroll file format for each bank",
  },
  add: { ar: "قالب جديد", en: "New template" },
  code: { ar: "الرمز", en: "Code" },
  name: { ar: "اسم القالب", en: "Template name" },
  bank: { ar: "البنك", en: "Bank" },
  swift: { ar: "بادئة السويفت", en: "SWIFT prefix" },
  delimiter: { ar: "الفاصل", en: "Delimiter" },
  header: { ar: "سطر ترويسة", en: "Header row" },
  columns: { ar: "الأعمدة", en: "Columns" },
  colHeader: { ar: "عنوان العمود", en: "Column header" },
  constValue: { ar: "القيمة الثابتة", en: "Constant value" },
  source: { ar: "المصدر", en: "Source" },
  builtin: { ar: "مدمج", en: "Built-in" },
  active: { ar: "نشط", en: "Active" },
  inactive: { ar: "معطّل", en: "Inactive" },
  show: { ar: "عرض الأعمدة", en: "Show columns" },
  hide: { ar: "إخفاء", en: "Hide" },
  clone: { ar: "نسخ", en: "Clone" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  addCol: { ar: "أضف عمودًا", en: "Add column" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا قوالب", en: "No templates" },
  noAccess: { ar: "لا تملك هذه الصلاحية", en: "Not permitted" },
  builtinHint: {
    ar: "قالب مدمج — تعديله يجعله قالب شركتك فلا يُستبدل بتحديثاتنا",
    en: "Built-in — editing makes it yours, safe from our updates",
  },
  confirmDel: {
    ar: "حذف القالب؟ لن يظهر في تصدير الرواتب بعدها.",
    en: "Delete? It will no longer appear in payroll export.",
  },
  confirmDelCol: { ar: "حذف هذا العمود؟", en: "Delete this column?" },
};

/** مصادر الأعمدة كما في الخادم (BankColumnSource) */
const SOURCES: { value: string; ar: string; en: string }[] = [
  { value: "employee_bank_swift", ar: "رمز بنك الموظف", en: "Bank SWIFT" },
  { value: "iban", ar: "الآيبان", en: "IBAN" },
  { value: "account_number", ar: "رقم الحساب", en: "Account number" },
  { value: "net_pay", ar: "صافي المستحق", en: "Net pay" },
  { value: "gross", ar: "إجمالي الاستحقاقات", en: "Gross" },
  { value: "basic", ar: "الراتب الأساسي", en: "Basic" },
  { value: "housing", ar: "بدل السكن", en: "Housing" },
  { value: "other_earnings", ar: "باقي الاستحقاقات", en: "Other earnings" },
  { value: "deductions", ar: "إجمالي الاستقطاعات", en: "Deductions" },
  { value: "employee_no", ar: "الرقم الوظيفي", en: "Employee no." },
  { value: "name_ar", ar: "الاسم بالعربية", en: "Name (AR)" },
  { value: "name_en", ar: "الاسم بالإنجليزية", en: "Name (EN)" },
  { value: "id_number", ar: "رقم الهوية", en: "ID number" },
  { value: "department", ar: "القسم", en: "Department" },
  { value: "branch", ar: "الفرع", en: "Branch" },
  { value: "job_title", ar: "المسمى الوظيفي", en: "Job title" },
  { value: "constant", ar: "قيمة ثابتة", en: "Constant" },
  { value: "sequence", ar: "رقم تسلسلي", en: "Sequence" },
];


type Column = {
  id: number;
  position: number;
  header: string;
  source: string;
  source_label: string;
  constant_value: string;
};

type Template = {
  id: number;
  code: string;
  name_ar: string;
  name_en?: string;
  bank_name_ar: string;
  swift_prefix: string;
  delimiter: string;
  include_header: boolean;
  is_builtin: boolean;
  is_active: boolean;
  columns: Column[];
};

export default function BankTemplatesPage() {
  const { L, lang } = useT(T);
  const [rows, setRows] = useState<Template[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [open, setOpen] = useState<number | null>(null);
  const [colDraft, setColDraft] = useState<Record<string, unknown>>({});
  const [err, setErr] = useState("");
  const [askDel, setAskDel] = useState<number | null>(null);
  const [askCol, setAskCol] = useState<{ t: number; c: number } | null>(null);

  const load = useCallback(() => {
    apiGet<Template[]>("/payroll/bank-templates/")
      .then((d) => { setRows(d); setBusy(false); })
      .catch((e: ApiError) => {
        setDenied(e.status === 403);
        setBusy(false);
      });
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((d) =>
        setCanEdit((d.permissions || []).includes("payroll.structures")))
      .catch(() => setCanEdit(false));
  }, []);

  async function run(fn: () => Promise<unknown>) {
    setErr("");
    try {
      await fn();
      load();
    } catch (e) {
      setErr((e as ApiError).message);
      setTimeout(() => setErr(""), 6000);
    }
  }

  const f = (k: string) => String(draft[k] ?? "");
  const set = (k: string, v: unknown) =>
    setDraft((d) => ({ ...d, [k]: v }));

  if (denied) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{L("noAccess")}</div>
      </div>
    );
  }

  return (
    <div className="stack">
      <ConfirmDialog
        open={askDel !== null} tone="danger" confirmLabel={L("del")}
        message={L("confirmDel")}
        onCancel={() => setAskDel(null)}
        onConfirm={() => {
          const id = askDel;
          setAskDel(null);
          if (id !== null) run(() =>
            apiDelete(`/payroll/bank-templates/${id}/`));
        }}
      />
      <ConfirmDialog
        open={askCol !== null} tone="danger" confirmLabel={L("del")}
        message={L("confirmDelCol")}
        onCancel={() => setAskCol(null)}
        onConfirm={() => {
          const a = askCol;
          setAskCol(null);
          if (a) run(() => apiDelete(
            `/payroll/bank-templates/${a.t}/columns/?column_id=${a.c}`));
        }}
      />

      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        {canEdit && !adding && editing === null && (
          <button className="btn btn-primary" onClick={() => {
            setDraft({ code: "", name_ar: "", delimiter: "," });
            setAdding(true);
          }}>
            <IcPlus size={17} />
            {L("add")}
          </button>
        )}
      </div>

      {err && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
          fontSize: ".9rem",
        }}>
          {err}
        </div>
      )}

      {adding && (
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <div className="field" style={{ minWidth: 130 }}>
              <label className="label">{L("code")}</label>
              <input className="input" value={f("code")} disabled={!adding}
                onChange={(e) => set("code", e.target.value.toUpperCase())} />
            </div>
            <div className="field" style={{ minWidth: 190 }}>
              <label className="label">{L("name")}</label>
              <input className="input" value={f("name_ar")}
                onChange={(e) => set("name_ar", e.target.value)} />
            </div>
            <div className="field" style={{ minWidth: 190 }}>
              <label className="label">{L("nameEn")}</label>
              <input className="input" value={f("name_en")}
                onChange={(e) => set("name_en", e.target.value)} />
            </div>
            <div className="field" style={{ minWidth: 170 }}>
              <label className="label">{L("bank")}</label>
              <input className="input" value={f("bank_name_ar")}
                onChange={(e) => set("bank_name_ar", e.target.value)} />
            </div>
            <div className="field" style={{ minWidth: 130 }}>
              <label className="label">{L("swift")}</label>
              <input className="input num" value={f("swift_prefix")}
                onChange={(e) => set("swift_prefix", e.target.value)} />
            </div>
            <div className="field" style={{ minWidth: 90 }}>
              <label className="label">{L("delimiter")}</label>
              <input className="input num" value={f("delimiter")}
                onChange={(e) => set("delimiter", e.target.value)} />
            </div>
          </div>

          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn btn-primary btn-sm" onClick={() => run(
              async () => {
                if (adding) await apiPost(
                  "/payroll/bank-templates/new/", draft);
                else await apiPut(
                  `/payroll/bank-templates/${editing}/`, draft);
                setAdding(false);
                setEditing(null);
              })}>
              <IcCheck size={16} />
              {L("save")}
            </button>
            <button className="btn btn-ghost btn-sm"
              onClick={() => {
                setAdding(false); setEditing(null); setErr("");
              }}>
              <IcX size={16} />
              {L("cancel")}
            </button>
          </div>
        </div>
      )}

      {busy ? (
        <div className="card" style={{
          padding: 40, textAlign: "center", color: "var(--ink-3)",
        }}>
          {L("loading")}
        </div>
      ) : rows.length === 0 ? (
        <div className="card" style={{
          padding: 40, textAlign: "center", color: "var(--ink-3)",
        }}>
          <IcWallet size={22} />
          <div style={{ marginTop: 8 }}>{L("empty")}</div>
        </div>
      ) : (
        <div className="stack" style={{ gap: 10 }}>
          {rows.map((t) => (
            <div key={t.id} className="card"
              style={{ opacity: t.is_active ? 1 : .6 }}>
              <div className="spread" style={{ padding: "14px 18px" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {(lang === "en" ? t.name_en : t.name_ar) || t.name_ar}
                    {t.is_builtin && (
                      <span className="badge" style={{
                        marginInlineStart: 6, fontSize: ".72rem",
                      }}>
                        {L("builtin")}
                      </span>
                    )}
                  </div>
                  <div className="muted" style={{
                    fontSize: ".8rem", marginTop: 3,
                  }}>
                    <span className="num">{t.code}</span>
                    {t.bank_name_ar && ` · ${t.bank_name_ar}`}
                    {" · "}{t.columns.length} {L("columns")}
                  </div>
                </div>

                <div className="row" style={{ gap: 8 }}>
                  <button className="btn btn-sm btn-ghost"
                    onClick={() => setOpen(open === t.id ? null : t.id)}>
                    {open === t.id ? L("hide") : L("show")}
                  </button>
                  {canEdit && (
                    <>
                      <button className="btn btn-sm btn-ghost"
                        onClick={() => run(() => apiPost(
                          `/payroll/bank-templates/${t.id}/clone/`, {}))}>
                        {L("clone")}
                      </button>
                      <button className="btn btn-sm btn-ghost"
                        onClick={() => {
                          setDraft({ ...t });
                          setEditing(editing === t.id ? null : t.id);
                          setOpen(t.id);
                          setAdding(false);
                        }}>
                        {L("edit")}
                      </button>
                      <button className="btn btn-sm btn-ghost"
                        style={{ color: "var(--danger)" }}
                        onClick={() => setAskDel(t.id)}>
                        {L("del")}
                      </button>
                    </>
                  )}
                </div>
              </div>

              {open === t.id && (
                <div style={{
                  borderTop: "1px solid var(--line)",
                  padding: "12px 18px",
                }}>
                  {t.is_builtin && (
                    <div className="muted" style={{
                      fontSize: ".82rem", marginBottom: 10,
                    }}>
                      {L("builtinHint")}
                    </div>
                  )}

                  {editing === t.id && (
                    <div style={{
                      background: "var(--paper-2)", padding: 14,
                      borderRadius: "var(--radius-sm)", marginBottom: 14,
                    }}>
                      <div className="row" style={{
                        flexWrap: "wrap", gap: 10,
                      }}>
                        <div className="field" style={{ minWidth: 180 }}>
                          <label className="label">{L("name")}</label>
                          <input className="input" value={f("name_ar")}
                            onChange={(e) =>
                              set("name_ar", e.target.value)} />
                        </div>
                        <div className="field" style={{ minWidth: 170 }}>
                          <label className="label">{L("bank")}</label>
                          <input className="input" value={f("bank_name_ar")}
                            onChange={(e) =>
                              set("bank_name_ar", e.target.value)} />
                        </div>
                        <div className="field" style={{ minWidth: 120 }}>
                          <label className="label">{L("swift")}</label>
                          <input className="input num"
                            value={f("swift_prefix")}
                            onChange={(e) =>
                              set("swift_prefix", e.target.value)} />
                        </div>
                        <div className="field" style={{ minWidth: 80 }}>
                          <label className="label">{L("delimiter")}</label>
                          <input className="input num" value={f("delimiter")}
                            onChange={(e) =>
                              set("delimiter", e.target.value)} />
                        </div>
                      </div>

                      <div className="row" style={{ marginTop: 12 }}>
                        <button className="btn btn-sm btn-primary"
                          onClick={() => run(async () => {
                            await apiPut(
                              `/payroll/bank-templates/${t.id}/`, draft);
                            setEditing(null);
                          })}>
                          <IcCheck size={15} />
                          {L("save")}
                        </button>
                        <button className="btn btn-sm btn-ghost"
                          onClick={() => setEditing(null)}>
                          <IcX size={15} />
                        </button>
                      </div>
                    </div>
                  )}
                  {t.columns.map((col) => (
                    <div key={col.id} className="spread" style={{
                      padding: "7px 0",
                      borderBottom: "1px solid var(--line)",
                    }}>
                      <div style={{ fontSize: ".88rem" }}>
                        <span className="num muted">{col.position}</span>
                        {" · "}{col.header}
                        <span className="muted" style={{
                          fontSize: ".78rem", marginInlineStart: 8,
                        }}>
                          {col.source_label}
                          {col.constant_value && `: ${col.constant_value}`}
                        </span>
                      </div>
                      {canEdit && (
                        <div className="row" style={{ gap: 3 }}>
                          <button className="btn btn-sm btn-ghost"
                            disabled={col.position === 1}
                            onClick={() => run(() => apiPut(
                              `/payroll/bank-templates/${t.id}/columns/`,
                              { column_id: col.id, move: "up" }))}>
                            ↑
                          </button>
                          <button className="btn btn-sm btn-ghost"
                            disabled={col.position === t.columns.length}
                            onClick={() => run(() => apiPut(
                              `/payroll/bank-templates/${t.id}/columns/`,
                              { column_id: col.id, move: "down" }))}>
                            ↓
                          </button>
                          <button className="btn btn-sm btn-ghost"
                            style={{ color: "var(--danger)" }}
                            onClick={() => setAskCol({ t: t.id, c: col.id })}>
                            {L("del")}
                          </button>
                        </div>
                      )}
                    </div>
                  ))}

                  {canEdit && (
                    <div className="row" style={{
                      gap: 8, paddingTop: 12, flexWrap: "wrap",
                    }}>
                      <input className="input"
                        placeholder={L("colHeader")}
                        style={{ maxWidth: 200 }}
                        value={String(colDraft.header ?? "")}
                        onChange={(e) => setColDraft((d) => ({
                          ...d, header: e.target.value,
                        }))} />
                      <select className="select"
                        style={{ maxWidth: 200 }}
                        value={String(colDraft.source ?? "")}
                        onChange={(e) => setColDraft((d) => ({
                          ...d, source: e.target.value,
                        }))}>
                        <option value="">— {L("source")} —</option>
                        {SOURCES.map((src) => (
                          <option key={src.value} value={src.value}>
                            {lang === "en" ? src.en : src.ar}
                          </option>
                        ))}
                      </select>

                      {colDraft.source === "constant" && (
                        <input className="input"
                          placeholder={L("constValue")}
                          style={{ maxWidth: 150 }}
                          value={String(colDraft.constant_value ?? "")}
                          onChange={(e) => setColDraft((d) => ({
                            ...d, constant_value: e.target.value,
                          }))} />
                      )}
                      <button className="btn btn-sm btn-primary"
                        onClick={() => run(async () => {
                          await apiPost(
                            `/payroll/bank-templates/${t.id}/columns/`,
                            colDraft);
                          setColDraft({});
                        })}>
                        {L("addCol")}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
