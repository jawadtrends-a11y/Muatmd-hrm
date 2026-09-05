"use client";

/**
 * بنود الأجر وأعلامها.
 *
 * والأعلام هي المهمّة: هل يدخل التأمينات؟ المكافأة؟ أساس الإضافي؟
 * حماية الأجور؟ — فبند واحد بعلم خاطئ يغيّر راتب كل موظف.
 */
import { useCallback, useEffect, useState } from "react";

import { apiDelete, apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import { IcAlert, IcCheck, IcPayroll, IcPlus, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "بنود الأجر", en: "Pay components" },
  subtitle: {
    ar: "الاستحقاقات والاستقطاعات وأعلامها النظامية",
    en: "Earnings, deductions and their statutory flags",
  },
  add: { ar: "بند جديد", en: "New component" },
  code: { ar: "الرمز", en: "Code" },
  name: { ar: "الاسم", en: "Name" },
  kind: { ar: "النوع", en: "Type" },
  earning: { ar: "استحقاق", en: "Earning" },
  deduction: { ar: "استقطاع", en: "Deduction" },
  gosi: { ar: "التأمينات", en: "GOSI" },
  eosb: { ar: "المكافأة", en: "EOSB" },
  ot: { ar: "أساس الإضافي", en: "OT base" },
  wps: { ar: "حماية الأجور", en: "WPS" },
  absence: { ar: "أساس الغياب", en: "Absence base" },
  order: { ar: "الترتيب", en: "Order" },
  system: { ar: "نظامي", en: "System" },
  active: { ar: "نشط", en: "Active" },
  inactive: { ar: "معطّل", en: "Inactive" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا بنود", en: "No components" },
  noAccess: {
    ar: "لا تملك صلاحية إدارة بنود الأجر",
    en: "You cannot manage pay components",
  },
  confirmDelete: {
    ar: "حذف البند؟ إن كان مستخدمًا في هياكل رواتب فسيُعطَّل بدل حذفه.",
    en: "Delete? If used in salary structures it is deactivated instead.",
  },
  codeHint: {
    ar: "الرمز لا يُعدَّل — الاحتساب يستدعيه",
    en: "The code cannot change — calculations reference it",
  },
  flagsHint: {
    ar: "الأعلام تحدّد أثر البند في التأمينات والمكافأة والإضافي",
    en: "Flags decide the component's effect on GOSI, EOSB and OT",
  },
};

type Comp = {
  id: number;
  code: string;
  name_ar: string;
  component_type: string;
  is_gosi_subject: boolean;
  is_eosb_subject: boolean;
  is_overtime_base: boolean;
  is_wps_subject: boolean;
  is_absence_base?: boolean;
  is_system: boolean;
  is_active: boolean;
  display_order: number;
};

const FLAGS: { key: keyof Comp; label: string }[] = [
  { key: "is_gosi_subject", label: "gosi" },
  { key: "is_eosb_subject", label: "eosb" },
  { key: "is_overtime_base", label: "ot" },
  { key: "is_wps_subject", label: "wps" },
  { key: "is_absence_base", label: "absence" },
];

export default function PayComponentsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Comp[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [askDel, setAskDel] = useState<number | null>(null);

  const load = useCallback(() => {
    apiGet<Comp[]>("/payroll/components/")
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

  function startNew() {
    setDraft({
      code: "", name_ar: "", component_type: "earning",
      is_gosi_subject: false, is_eosb_subject: false,
      is_overtime_base: false, is_wps_subject: true,
      is_absence_base: false, display_order: 50, is_active: true,
    });
    setEditing("new");
    setErr("");
  }

  async function save() {
    setSaving(true);
    setErr("");
    try {
      if (editing === "new") {
        await apiPost("/payroll/components/", draft);
      } else {
        await apiPut(`/payroll/components/${editing}/`, draft);
      }
      setEditing(null);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    try {
      const r = await apiDelete<{ deactivated?: boolean; detail?: string }>(
        `/payroll/components/${id}/`);
      if (r?.deactivated && r.detail) {
        setMsg(r.detail);
        setTimeout(() => setMsg(""), 6000);
      }
      load();
    } catch (e) {
      setErr((e as ApiError).message);
      setTimeout(() => setErr(""), 7000);
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
        open={askDel !== null}
        tone="danger"
        confirmLabel={L("del")}
        message={L("confirmDelete")}
        onCancel={() => setAskDel(null)}
        onConfirm={() => {
          const id = askDel;
          setAskDel(null);
          if (id !== null) remove(id);
        }}
      />

      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        {canEdit && editing === null && (
          <button className="btn btn-primary" onClick={startNew}>
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
      {msg && (
        <div style={{
          background: "var(--copper-soft)", color: "var(--copper)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
          fontSize: ".9rem",
        }}>
          {msg}
        </div>
      )}

      {editing !== null && (
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <div className="field" style={{ minWidth: 150 }}>
              <label className="label">{L("code")}</label>
              <input className="input" value={f("code")}
                disabled={editing !== "new"}
                onChange={(e) => set("code", e.target.value.toUpperCase())} />
              {editing !== "new" && (
                <div className="muted" style={{ fontSize: ".76rem" }}>
                  {L("codeHint")}
                </div>
              )}
            </div>

            <div className="field" style={{ minWidth: 200 }}>
              <label className="label">{L("name")}</label>
              <input className="input" value={f("name_ar")}
                onChange={(e) => set("name_ar", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 150 }}>
              <label className="label">{L("kind")}</label>
              <select className="select" value={f("component_type")}
                onChange={(e) => set("component_type", e.target.value)}>
                <option value="earning">{L("earning")}</option>
                <option value="deduction">{L("deduction")}</option>
              </select>
            </div>

            <div className="field" style={{ minWidth: 110 }}>
              <label className="label">{L("order")}</label>
              <input className="input num" value={f("display_order")}
                onChange={(e) =>
                  set("display_order", Number(e.target.value) || 0)} />
            </div>
          </div>

          <div style={{ marginTop: 16 }}>
            <div className="muted" style={{
              fontSize: ".82rem", marginBottom: 8,
            }}>
              {L("flagsHint")}
            </div>
            <div className="row" style={{ gap: 18, flexWrap: "wrap" }}>
              {FLAGS.map((fl) => (
                <label key={String(fl.key)} className="row"
                  style={{ gap: 7, cursor: "pointer" }}>
                  <input type="checkbox"
                    checked={!!draft[fl.key as string]}
                    onChange={(e) =>
                      set(fl.key as string, e.target.checked)}
                    style={{ width: 17, height: 17,
                             accentColor: "var(--teal)" }} />
                  <span style={{ fontSize: ".9rem" }}>{L(fl.label)}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn btn-primary btn-sm" disabled={saving}
              onClick={save}>
              <IcCheck size={16} />
              {L("save")}
            </button>
            <button className="btn btn-ghost btn-sm"
              onClick={() => { setEditing(null); setErr(""); }}>
              <IcX size={16} />
              {L("cancel")}
            </button>
          </div>
        </div>
      )}

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <IcPayroll size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("code")}</th>
                  <th>{L("name")}</th>
                  <th>{L("kind")}</th>
                  <th>{L("gosi")}</th>
                  <th>{L("eosb")}</th>
                  <th>{L("ot")}</th>
                  <th>{L("wps")}</th>
                  <th style={{ width: 140 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.id} style={{
                    opacity: c.is_active ? 1 : .55,
                  }}>
                    <td><span className="num">{c.code}</span></td>
                    <td>
                      {c.name_ar}
                      {c.is_system && (
                        <span className="badge" style={{
                          marginInlineStart: 6, fontSize: ".72rem",
                        }}>
                          {L("system")}
                        </span>
                      )}
                      {!c.is_active && (
                        <span className="badge badge-warn" style={{
                          marginInlineStart: 6, fontSize: ".72rem",
                        }}>
                          {L("inactive")}
                        </span>
                      )}
                    </td>
                    <td className="muted">
                      {c.component_type === "earning"
                        ? L("earning") : L("deduction")}
                    </td>
                    {(["is_gosi_subject", "is_eosb_subject",
                       "is_overtime_base", "is_wps_subject"] as const)
                      .map((k) => (
                        <td key={k}>
                          {c[k]
                            ? <span style={{ color: "var(--teal)" }}>✓</span>
                            : <span className="muted">—</span>}
                        </td>
                      ))}
                    <td>
                      {canEdit && (
                        <div className="row" style={{ gap: 6 }}>
                          <button className="btn btn-sm btn-ghost"
                            onClick={() => {
                              setDraft({ ...c });
                              setEditing(c.id);
                              setErr("");
                            }}>
                            {L("edit")}
                          </button>
                          {!c.is_system && (
                            <button className="btn btn-sm btn-ghost"
                              style={{ color: "var(--danger)" }}
                              onClick={() => setAskDel(c.id)}>
                              {L("del")}
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
