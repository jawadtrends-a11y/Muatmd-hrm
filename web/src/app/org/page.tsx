"use client";

/**
 * الهيكل التنظيمي — الفروع والأقسام والمسميات والعطل.
 *
 * أول ما يعرّفه العميل قبل إضافة موظف واحد.
 */
import { useCallback, useEffect, useState } from "react";

import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcOrg, IcPlus, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الهيكل التنظيمي", en: "Organization" },
  subtitle: {
    ar: "الفروع والأقسام والمسميات — تُعرَّف قبل إضافة الموظفين",
    en: "Branches, departments and job titles",
  },
  branches: { ar: "الفروع", en: "Branches" },
  departments: { ar: "الأقسام", en: "Departments" },
  jobTitles: { ar: "المسميات الوظيفية", en: "Job Titles" },
  holidays: { ar: "العطل الرسمية", en: "Holidays" },
  code: { ar: "الرمز", en: "Code" },
  nameAr: { ar: "الاسم", en: "Name" },
  city: { ar: "المدينة", en: "City" },
  molNo: { ar: "رقم منشأة قوى", en: "MOL No." },
  gosiNo: { ar: "رقم منشأة التأمينات", en: "GOSI No." },
  branch: { ar: "الفرع", en: "Branch" },
  parent: { ar: "القسم الأعلى", en: "Parent" },
  none: { ar: "بلا", en: "None" },
  molCode: { ar: "رمز المهنة في قوى", en: "MOL occupation code" },
  saudiOnly: { ar: "محجوز للسعوديين", en: "Saudization reserved" },
  date: { ar: "التاريخ", en: "Date" },
  days: { ar: "الأيام", en: "Days" },
  add: { ar: "إضافة", en: "Add" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا سجلات — أضف الأول", en: "No records — add the first" },
  active: { ar: "نشط", en: "Active" },
  inactive: { ar: "معطّل", en: "Inactive" },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
  required: { ar: "الرمز والاسم مطلوبان", en: "Code and name required" },
  planLimit: {
    ar: "بلغت حد باقتك — رقّها لإضافة المزيد",
    en: "Plan limit reached — upgrade to add more",
  },
  noAccess: { ar: "لا صلاحية لهذا القسم", en: "No access" },
  hintBranch: {
    ar: "كل فرع يحتاج رقم منشأة مستقلًا في قوى والتأمينات",
    en: "Each branch needs its own MOL and GOSI establishment number",
  },
  hintDept: {
    ar: "الأقسام شجرة — يمكن أن يتبع القسم قسمًا أعلى",
    en: "Departments form a tree",
  },
};

const TABS = ["branches", "departments", "jobTitles", "holidays"] as const;
type Tab = (typeof TABS)[number];

type Branch = {
  id: number; code: string; name_ar: string; city: string;
  is_active: boolean;
  mol_establishment_no: string; gosi_establishment_no: string;
};

type Department = {
  id: number; code: string; name_ar: string;
  branch_id: number | null; parent_id: number | null;
  depth: number; is_active: boolean;
};

type JobTitle = {
  id: number; name_ar: string; mol_occupation_code: string;
  is_saudization_reserved: boolean; is_active: boolean;
};

type Holiday = {
  id: number; name_ar: string; start_date: string; days: number;
};


/* ══ حقل نموذج — خارج المكوّن الرئيسي ══ */

type FieldDef = {
  key: string;
  label: string;
  kind?: "text" | "number" | "date" | "select" | "bool";
  options?: { value: string; label: string }[];
  required?: boolean;
  hint?: string;
};

function AddForm({
  fields, L, onSave, onCancel, busy, error,
}: {
  fields: FieldDef[];
  L: (k: string, f?: string) => string;
  onSave: (data: Record<string, string>) => void;
  onCancel: () => void;
  busy: boolean;
  error: string;
}) {
  const [v, setV] = useState<Record<string, string>>({});

  const missing = fields.filter((f) => f.required && !v[f.key]?.trim());

  return (
    <div className="card" style={{ padding: 18, marginBottom: 14 }}>
      <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
        {fields.map((f) => (
          <div key={f.key} className="field"
            style={{ minWidth: 160, maxWidth: 220 }}>
            <label className="label">
              {f.label}
              {f.required && (
                <span style={{ color: "var(--danger)", marginInlineStart: 3 }}>
                  *
                </span>
              )}
            </label>

            {f.kind === "select" ? (
              <select className="select" value={v[f.key] ?? ""}
                onChange={(e) => setV({ ...v, [f.key]: e.target.value })}>
                {(f.options ?? []).map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            ) : f.kind === "bool" ? (
              <select className="select" value={v[f.key] ?? "0"}
                onChange={(e) => setV({ ...v, [f.key]: e.target.value })}>
                <option value="0">{L("no")}</option>
                <option value="1">{L("yes")}</option>
              </select>
            ) : (
              <input
                className="input"
                type={f.kind === "number" ? "number"
                      : f.kind === "date" ? "date" : "text"}
                value={v[f.key] ?? ""}
                dir={f.kind === "number" ? "ltr" : undefined}
                onChange={(e) => setV({ ...v, [f.key]: e.target.value })}
              />
            )}

            {f.hint && <div className="hint">{f.hint}</div>}
          </div>
        ))}

        <button className="btn btn-primary" disabled={busy || missing.length > 0}
          onClick={() => onSave(v)}>
          {busy ? L("saving") : L("save")}
        </button>
        <button className="btn btn-ghost" onClick={onCancel}>
          {L("cancel")}
        </button>
      </div>

      {error && (
        <div style={{
          marginTop: 12, background: "var(--danger-soft)",
          color: "var(--danger)", padding: "9px 12px",
          borderRadius: "var(--radius-sm)", fontSize: ".88rem",
        }}>
          {error}
        </div>
      )}
    </div>
  );
}

/* ══ جدول بسيط ══ */

function SimpleTable({
  rows, cols, L,
}: {
  rows: Record<string, unknown>[];
  cols: { key: string; label: string; width?: number;
          render?: (r: Record<string, unknown>) => React.ReactNode }[];
  L: (k: string, f?: string) => string;
}) {
  if (rows.length === 0) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("empty")}
      </div>
    );
  }

  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <div style={{ overflowX: "auto" }}>
        <table className="table">
          <colgroup>
            {cols.map((c) => (
              <col key={c.key}
                style={{ width: c.width ? `${c.width}px` : undefined }} />
            ))}
          </colgroup>
          <thead>
            <tr>{cols.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c.key}>
                    {c.render ? c.render(r)
                      : ((r[c.key] as React.ReactNode) ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


/* ══ الشاشة ══ */

export default function OrgPage() {
  const { L } = useT(T);
  /**
   * الزر الذي يظهر ثم يُرفض عند الضغط خلل: يوهم المستخدم بقدرة
   * لا يملكها. فمن لا يملك إدارة الهيكل لا يرى زر الإضافة —
   * ومدير الإدارة يطّلع ولا يعدّل (ق-68).
   */
  const [canManage, setCanManage] = useState(false);
  const [tab, setTab] = useState<Tab>("branches");

  const [branches, setBranches] = useState<Branch[]>([]);
  const [depts, setDepts] = useState<Department[]>([]);
  const [titles, setTitles] = useState<JobTitle[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);

  const [busy, setBusy] = useState(true);
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [denied, setDenied] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    const [b, d, j, h] = await Promise.all([
      apiGet<Branch[]>("/org/branches/").catch((e: ApiError) => {
        if (e.isForbidden) setDenied(true);
        return [] as Branch[];
      }),
      apiGet<Department[]>("/org/departments/").catch(() => [] as Department[]),
      apiGet<JobTitle[]>("/org/job-titles/").catch(() => [] as JobTitle[]),
      apiGet<Holiday[]>("/org/holidays/").catch(() => [] as Holiday[]),
    ]);
    setBranches(b);
    setDepts(d);
    setTitles(j);
    setHolidays(h);
    setBusy(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((d) => setCanManage((d.permissions || []).includes("org.manage")))
      .catch(() => setCanManage(false));
  }, []);

  const ENDPOINTS: Record<Tab, string> = {
    branches: "/org/branches/",
    departments: "/org/departments/",
    jobTitles: "/org/job-titles/",
    holidays: "/org/holidays/",
  };

  async function save(data: Record<string, string>) {
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(data)) {
        if (v === "") continue;
        payload[k] = v === "1" ? true : v === "0" ? false : v;
      }
      await apiPost(ENDPOINTS[tab], payload);
      setAdding(false);
      await load();
    } catch (e) {
      const err = e as ApiError;
      setError(err.status === 402 ? L("planLimit") : err.message);
    } finally {
      setSaving(false);
    }
  }

  const FORMS: Record<Tab, FieldDef[]> = {
    branches: [
      { key: "code", label: L("code"), required: true },
      { key: "name_ar", label: L("nameAr"), required: true },
      { key: "city", label: L("city") },
      { key: "mol_establishment_no", label: L("molNo") },
      { key: "gosi_establishment_no", label: L("gosiNo") },
    ],
    departments: [
      { key: "code", label: L("code"), required: true },
      { key: "name_ar", label: L("nameAr"), required: true },
      { key: "branch_id", label: L("branch"), kind: "select",
        options: [{ value: "", label: L("none") },
                  ...branches.map((b) => ({ value: String(b.id),
                                            label: b.name_ar }))] },
      { key: "parent_id", label: L("parent"), kind: "select",
        options: [{ value: "", label: L("none") },
                  ...depts.map((d) => ({ value: String(d.id),
                                         label: d.name_ar }))] },
    ],
    jobTitles: [
      { key: "name_ar", label: L("nameAr"), required: true },
      { key: "mol_occupation_code", label: L("molCode") },
      { key: "is_saudization_reserved", label: L("saudiOnly"), kind: "bool" },
    ],
    holidays: [
      { key: "name_ar", label: L("nameAr"), required: true },
      { key: "start_date", label: L("date"), kind: "date", required: true },
      { key: "days", label: L("days"), kind: "number", required: true },
    ],
  };

  const badge = (on: boolean) => (
    <span className={on ? "badge badge-ok" : "badge"}>
      {on ? L("active") : L("inactive")}
    </span>
  );

  const COLS: Record<Tab, Parameters<typeof SimpleTable>[0]["cols"]> = {
    branches: [
      { key: "code", label: L("code"), width: 110 },
      { key: "name_ar", label: L("nameAr"), width: 240 },
      { key: "city", label: L("city"), width: 140 },
      { key: "mol_establishment_no", label: L("molNo"), width: 150 },
      { key: "gosi_establishment_no", label: L("gosiNo"), width: 170 },
      { key: "is_active", label: "", width: 100,
        render: (r) => badge(Boolean(r.is_active)) },
    ],
    departments: [
      { key: "code", label: L("code"), width: 110 },
      { key: "name_ar", label: L("nameAr"), width: 280,
        render: (r) => (
          <span style={{
            paddingInlineStart: `${(Number(r.depth) || 0) * 18}px`,
          }}>
            {String(r.name_ar)}
          </span>
        ) },
      { key: "is_active", label: "", width: 100,
        render: (r) => badge(Boolean(r.is_active)) },
    ],
    jobTitles: [
      { key: "name_ar", label: L("nameAr"), width: 280 },
      { key: "mol_occupation_code", label: L("molCode"), width: 180 },
      { key: "is_saudization_reserved", label: L("saudiOnly"), width: 150,
        render: (r) => (
          <span className={r.is_saudization_reserved
            ? "badge badge-teal" : "badge"}>
            {r.is_saudization_reserved ? L("yes") : L("no")}
          </span>
        ) },
    ],
    holidays: [
      { key: "name_ar", label: L("nameAr"), width: 260 },
      { key: "start_date", label: L("date"), width: 140,
        render: (r) => <span className="num">{String(r.start_date)}</span> },
      { key: "days", label: L("days"), width: 100,
        render: (r) => <span className="num">{String(r.days)}</span> },
    ],
  };

  const DATA: Record<Tab, Record<string, unknown>[]> = {
    branches: branches as unknown as Record<string, unknown>[],
    departments: depts as unknown as Record<string, unknown>[],
    jobTitles: titles as unknown as Record<string, unknown>[],
    holidays: holidays as unknown as Record<string, unknown>[],
  };

  const HINTS: Partial<Record<Tab, string>> = {
    branches: L("hintBranch"),
    departments: L("hintDept"),
  };

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
      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        {!adding && canManage && (
          <button className="btn btn-primary" onClick={() => {
            setAdding(true);
            setError("");
          }}>
            <IcPlus size={17} />
            {L("add")}
          </button>
        )}
      </div>

      <div className="row" style={{ gap: 4, flexWrap: "wrap" }}>
        {TABS.map((t) => (
          <button key={t}
            className={`btn btn-sm ${tab === t ? "btn-primary" : "btn-ghost"}`}
            onClick={() => { setTab(t); setAdding(false); setError(""); }}>
            {L(t)}
            <span className="num" style={{ opacity: .7 }}>
              ({DATA[t].length})
            </span>
          </button>
        ))}
      </div>

      {HINTS[tab] && (
        <div className="muted" style={{ fontSize: ".85rem" }}>
          <IcOrg size={15} /> {HINTS[tab]}
        </div>
      )}

      {adding && (
        <AddForm fields={FORMS[tab]} L={L} onSave={save}
          onCancel={() => { setAdding(false); setError(""); }}
          busy={saving} error={error} />
      )}

      {busy ? (
        <div className="card" style={{
          padding: 36, textAlign: "center", color: "var(--ink-3)",
        }}>
          {L("loading")}
        </div>
      ) : (
        <SimpleTable rows={DATA[tab]} cols={COLS[tab]} L={L} />
      )}
    </div>
  );
}
