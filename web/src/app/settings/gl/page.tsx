"use client";
/**
 * القيد المحاسبيّ (ق-152).
 *
 * ⚠️ **وبندٌ بلا ربطٍ يمنع التصدير** — فالشاشة تُظهر ما ينقص.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "القيد المحاسبيّ", en: "GL export" },
  sub: {
    ar: "اربط بنود الأجر بحساباتك، وصدّر قيد المسير لنظامك",
    en: "Map pay components to accounts and export to your GL",
  },
  tabAccounts: { ar: "ربط الحسابات", en: "Accounts" },
  tabTemplates: { ar: "القوالب", en: "Templates" },
  component: { ar: "البند", en: "Component" },
  debit: { ar: "الحساب المدين", en: "Debit account" },
  credit: { ar: "الحساب الدائن", en: "Credit account" },
  excluded: { ar: "مستثنى", en: "Excluded" },
  ready: { ar: "جاهز", en: "Ready" },
  missing: { ar: "ناقص", en: "Missing" },
  save: { ar: "حفظ", en: "Save" },
  saveAll: { ar: "حفظ الربط", en: "Save mapping" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  addTemplate: { ar: "قالب جديد", en: "New template" },
  code: { ar: "الرمز", en: "Code" },
  name: { ar: "القالب", en: "Template" },
  system: { ar: "النظام", en: "System" },
  systemHint: {
    ar: "أودو · SAP · مايكروسوفت — للتذكير لا للمنطق",
    en: "For reference only",
  },
  grouping: { ar: "مستوى التجميع", en: "Grouping" },
  groupHint: {
    ar: "⚠️ بالموظف أدقّ وأثقل — مئة موظفٍ في عشرة بنود = ألف سطر",
    en: "Per employee is precise but heavy",
  },
  columns: { ar: "الأعمدة", en: "Columns" },
  colField: { ar: "الحقل", en: "Field" },
  colHeader: { ar: "العنوان", en: "Header" },
  addCol: { ar: "إضافة عمود", en: "Add column" },
  del: { ar: "حذف", en: "Delete" },
  edit: { ar: "تعديل", en: "Edit" },
  empty: { ar: "لا قوالب بعد", en: "No templates yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "التكامل المحاسبيّ غير متاح في باقتكم",
              en: "Not in your plan" },
  savedOk: { ar: "حُفظ", en: "Saved" },
  notReady: {
    ar: "⚠️ بنودٌ بلا ربط — ولن يُصدَّر القيد حتى تكتمل",
    en: "Unmapped components block export",
  },
  allReady: {
    ar: "✓ كل البنود مربوطة — والقيد جاهزٌ للتصدير",
    en: "All components mapped",
  },
  payableHint: {
    ar: "⚠️ «صافي الرواتب المستحقّة» هو الطرف الدائن — وبلاه لا يتوازن القيد",
    en: "NET_PAYABLE is the credit side — required for balance",
  },
};

type Acc = {
  component_code: string; name_ar: string;
  debit_account: string; credit_account: string;
  is_excluded: boolean; is_ready: boolean;
};
type Tpl = {
  id: number; code: string; name_ar: string; target_system: string;
  grouping: string; grouping_label: string;
  columns: { field: string; header: string }[];
  delimiter: string; include_header: boolean; is_active: boolean;
};
type Opt = { value: string; label: string };

export default function GLPage() {
  const { L } = useT(T);
  const [tab, setTab] = useState<"accounts" | "templates">("accounts");
  const [accs, setAccs] = useState<Acc[]>([]);
  const [tpls, setTpls] = useState<Tpl[]>([]);
  const [groupings, setGroupings] = useState<Opt[]>([]);
  const [fields, setFields] = useState<Opt[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [editing, setEditing] = useState<Tpl | null>(null);
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [a, t] = await Promise.all([
        apiGet<{ accounts: Acc[] }>("/payroll/gl/accounts/"),
        apiGet<{ templates: Tpl[]; groupings: Opt[]; fields: Opt[] }>(
          "/payroll/gl/templates/"),
      ]);
      setAccs(a.accounts);
      setTpls(t.templates);
      setGroupings(t.groupings);
      setFields(t.fields);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const setAcc = (code: string, patch: Partial<Acc>) =>
    setAccs((rows) => rows.map((r) =>
      r.component_code === code ? { ...r, ...patch } : r));

  const saveAccounts = async () => {
    setSaving(true); setErr("");
    try {
      for (const a of accs) {
        await apiPost("/payroll/gl/accounts/", {
          component_code: a.component_code,
          name_ar: a.name_ar,
          debit_account: a.debit_account,
          credit_account: a.credit_account,
          is_excluded: a.is_excluded,
        });
      }
      setMsg(L("savedOk"));
      setTimeout(() => setMsg(""), 3000);
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setSaving(false); }
  };

  const removeTpl = async (t: Tpl) => {
    try {
      await apiDelete(`/payroll/gl/templates/${t.id}/`);
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
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

  const notReady = accs.filter((a) => !a.is_ready && !a.is_excluded);

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1 style={{ margin: 0 }}>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("sub")}
          </div>
        </div>
        {tab === "templates" ? (
          <button className="btn btn-primary btn-sm"
                  onClick={() => setAdding(true)}>{L("addTemplate")}</button>
        ) : (
          <button className="btn btn-primary btn-sm" disabled={saving}
                  onClick={saveAccounts}>
            {saving ? "…" : L("saveAll")}
          </button>
        )}
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="row" style={{ gap: 6 }}>
        {(["accounts", "templates"] as const).map((t) => (
          <button key={t}
                  className={`btn btn-sm ${tab === t ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setTab(t)}>
            {t === "accounts" ? L("tabAccounts") : L("tabTemplates")}
          </button>
        ))}
      </div>

      {tab === "accounts" && (
        <>
          {/* ⚠️ وحال الاكتمال يُعرض أوّلًا — فالناقص يمنع التصدير */}
          <div style={{
            background: notReady.length ? "var(--copper-soft)"
              : "var(--ok-soft)",
            color: notReady.length ? "var(--copper)" : "var(--ok)",
            padding: "11px 14px", borderRadius: "var(--radius-sm)",
            fontSize: ".85rem", lineHeight: 1.8 }}>
            {notReady.length ? L("notReady") : L("allReady")}
          </div>

          <div className="muted" style={{ fontSize: ".8rem",
                                          lineHeight: 1.8 }}>
            {L("payableHint")}
          </div>

          <div className="card" style={{ overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>{L("component")}</th>
                    <th style={{ width: 160 }}>{L("debit")}</th>
                    <th style={{ width: 160 }}>{L("credit")}</th>
                    <th style={{ width: 100 }}>{L("excluded")}</th>
                    <th style={{ width: 90 }}>{L("ready")}</th>
                  </tr>
                </thead>
                <tbody>
                  {accs.map((a) => (
                    <tr key={a.component_code}>
                      <td>
                        <div style={{ fontWeight: 500 }}>{a.name_ar}</div>
                        <div className="muted num"
                             style={{ fontSize: ".74rem" }}>
                          {a.component_code}
                        </div>
                      </td>
                      <td>
                        <input className="input num" dir="ltr"
                               value={a.debit_account}
                               disabled={a.is_excluded}
                               onChange={(e) => setAcc(a.component_code,
                                 { debit_account: e.target.value })} />
                      </td>
                      <td>
                        <input className="input num" dir="ltr"
                               value={a.credit_account}
                               disabled={a.is_excluded}
                               onChange={(e) => setAcc(a.component_code,
                                 { credit_account: e.target.value })} />
                      </td>
                      <td>
                        <input type="checkbox" checked={a.is_excluded}
                               onChange={(e) => setAcc(a.component_code,
                                 { is_excluded: e.target.checked })} />
                      </td>
                      <td>
                        {a.is_excluded ? (
                          <span className="muted"
                                style={{ fontSize: ".8rem" }}>—</span>
                        ) : a.is_ready ? (
                          <span className="badge badge-ok">✓</span>
                        ) : (
                          <span className="badge badge-warn">
                            {L("missing")}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {tab === "templates" && (
        <div className="card" style={{ overflow: "hidden" }}>
          {tpls.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center",
                          color: "var(--ink-3)" }}>
              <IcDoc size={22} />
              <div style={{ marginTop: 8 }}>{L("empty")}</div>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>{L("name")}</th>
                  <th style={{ width: 130 }}>{L("system")}</th>
                  <th style={{ width: 160 }}>{L("grouping")}</th>
                  <th style={{ width: 90 }}>{L("columns")}</th>
                  <th style={{ width: 150 }} />
                </tr>
              </thead>
              <tbody>
                {tpls.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{t.name_ar}</div>
                      <div className="muted num"
                           style={{ fontSize: ".74rem" }}>{t.code}</div>
                    </td>
                    <td className="muted">{t.target_system || "—"}</td>
                    <td className="muted">{t.grouping_label}</td>
                    <td>
                      <span className="num">
                        {(t.columns || []).length}
                      </span>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 5 }}>
                        <button className="btn btn-sm"
                                onClick={() => setEditing(t)}>
                          {L("edit")}
                        </button>
                        <button className="btn btn-sm btn-danger"
                                onClick={() => removeTpl(t)}>
                          {L("del")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {(adding || editing) && (
        <TemplateDialog t={editing} groupings={groupings}
                        fields={fields} L={L}
                        onClose={() => { setAdding(false);
                                         setEditing(null); }}
                        onSaved={async () => {
                          setAdding(false); setEditing(null);
                          setMsg(L("savedOk"));
                          setTimeout(() => setMsg(""), 3000);
                          await load();
                        }} />
      )}
    </div>
  );
}


function TemplateDialog({ t, groupings, fields, L, onClose, onSaved }: {
  t: Tpl | null; groupings: Opt[]; fields: Opt[];
  L: (k: string, f?: string) => string;
  onClose: () => void; onSaved: () => void;
}) {
  const [f, setF] = useState({
    code: t?.code || "", name_ar: t?.name_ar || "",
    target_system: t?.target_system || "",
    grouping: t?.grouping || "company",
    delimiter: t?.delimiter || ",",
    include_header: t?.include_header ?? true,
  });
  const [cols, setCols] = useState<{ field: string; header: string }[]>(
    t?.columns?.length ? t.columns : [
      { field: "entry_date", header: "Date" },
      { field: "account", header: "Account" },
      { field: "debit", header: "Debit" },
      { field: "credit", header: "Credit" },
    ]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const body = { ...f, columns: cols };
      if (t) await apiPut(`/payroll/gl/templates/${t.id}/`, body);
      else await apiPost("/payroll/gl/templates/", body);
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 560,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>
          {t ? t.name_ar : L("addTemplate")}
        </h3>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="row" style={{ gap: 12, marginTop: 16,
                                      flexWrap: "wrap" }}>
          {!t && (
            <label className="field" style={{ width: 130 }}>
              <span className="label">{L("code")}</span>
              <input className="input" dir="ltr" value={f.code}
                     onChange={(e) => setF({ ...f,
                       code: e.target.value.trim().toUpperCase() })} />
            </label>
          )}
          <label className="field" style={{ flex: 1, minWidth: 160 }}>
            <span className="label">{L("name")}</span>
            <input className="input" value={f.name_ar}
                   onChange={(e) => setF({ ...f,
                     name_ar: e.target.value })} />
          </label>
        </div>

        <div className="row" style={{ gap: 12, marginTop: 12 }}>
          <label className="field" style={{ flex: 1 }}>
            <span className="label">{L("system")}</span>
            <input className="input" value={f.target_system}
                   onChange={(e) => setF({ ...f,
                     target_system: e.target.value })} />
            <span className="muted" style={{ fontSize: ".76rem" }}>
              {L("systemHint")}
            </span>
          </label>
          <label className="field" style={{ width: 90 }}>
            <span className="label">CSV</span>
            <input className="input" dir="ltr" maxLength={3}
                   value={f.delimiter}
                   onChange={(e) => setF({ ...f,
                     delimiter: e.target.value })} />
          </label>
        </div>

        <label className="field" style={{ marginTop: 12 }}>
          <span className="label">{L("grouping")}</span>
          <select className="select" value={f.grouping}
                  onChange={(e) => setF({ ...f,
                    grouping: e.target.value })}>
            {groupings.map((g) => (
              <option key={g.value} value={g.value}>{g.label}</option>
            ))}
          </select>
          <span className="muted" style={{ fontSize: ".78rem",
                                           lineHeight: 1.8 }}>
            {L("groupHint")}
          </span>
        </label>

        <div className="field" style={{ marginTop: 14 }}>
          <span className="label">{L("columns")}</span>
          <div className="stack" style={{ gap: 6, marginTop: 4 }}>
            {cols.map((c, i) => (
              <div key={i} className="row" style={{ gap: 6 }}>
                <select className="select" style={{ flex: 1 }}
                        value={c.field}
                        onChange={(e) => setCols(cols.map((x, j) =>
                          j === i ? { ...x, field: e.target.value }
                                  : x))}>
                  {fields.map((fl) => (
                    <option key={fl.value} value={fl.value}>
                      {fl.label}
                    </option>
                  ))}
                </select>
                <input className="input" style={{ width: 150 }}
                       dir="ltr" value={c.header}
                       placeholder={L("colHeader")}
                       onChange={(e) => setCols(cols.map((x, j) =>
                         j === i ? { ...x, header: e.target.value }
                                 : x))} />
                <button className="btn btn-sm btn-ghost"
                        onClick={() => setCols(
                          cols.filter((_, j) => j !== i))}>×</button>
              </div>
            ))}
          </div>
          <button className="btn btn-sm" style={{ marginTop: 8 }}
                  onClick={() => setCols([...cols,
                    { field: "reference", header: "Ref" }])}>
            + {L("addCol")}
          </button>
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.name_ar.trim()
                            || (!t && !f.code) || cols.length === 0}
                  onClick={submit}>{busy ? "…" : L("save")}</button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}
