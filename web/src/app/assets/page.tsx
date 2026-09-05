"use client";

/**
 * العهد — تسليمها للموظفين واسترجاعها.
 *
 * والعهدة القائمة تدخل المخالصة عند إنهاء الخدمة، فمن يُنهي خدمة
 * موظف يحتاج معرفة ما بذمّته قبل أن يصرف مستحقاته.
 */
import { useCallback, useEffect, useState } from "react";

import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc, IcPlus, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "العهد", en: "Assets" },
  subtitle: {
    ar: "ما بذمّة الموظفين من عهد وأجهزة",
    en: "Assets currently held by employees",
  },
  add: { ar: "تسليم عهدة", en: "Assign asset" },
  no: { ar: "الرقم", en: "No." },
  name: { ar: "العهدة", en: "Asset" },
  category: { ar: "الفئة", en: "Category" },
  serial: { ar: "الرقم التسلسلي", en: "Serial" },
  value: { ar: "القيمة", en: "Value" },
  employee: { ar: "الموظف", en: "Employee" },
  assigned: { ar: "تاريخ التسليم", en: "Assigned" },
  returned: { ar: "تاريخ الاسترجاع", en: "Returned" },
  status: { ar: "الحالة", en: "Status" },
  ret: { ar: "استرجاع", en: "Return" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا عهد", en: "No assets" },
  noAccess: { ar: "لا تملك هذه الصلاحية", en: "Not permitted" },
  pickEmployee: { ar: "اختر الموظف", en: "Pick employee" },
  outstanding: { ar: "قائمة", en: "Outstanding" },
  onlyOutstanding: { ar: "القائمة فقط", en: "Outstanding only" },
  all: { ar: "الكل", en: "All" },
  note: { ar: "ملاحظة الحالة", en: "Condition note" },
  retStatus: { ar: "حالة الاسترجاع", en: "Return status" },
  retOk: { ar: "سليمة", en: "Good" },
  retDamaged: { ar: "تالفة", en: "Damaged" },
  retLost: { ar: "مفقودة", en: "Lost" },
  confirmReturn: {
    ar: "استرجاع العهدة؟ التالفة والمفقودة تبقى ضمن المخالصة.",
    en: "Return it? Damaged and lost stay in the settlement.",
  },
  catOther: { ar: "أخرى", en: "Other" },
  catDevice: { ar: "جهاز", en: "Device" },
  catVehicle: { ar: "مركبة", en: "Vehicle" },
  catTool: { ar: "أداة", en: "Tool" },
  catUniform: { ar: "زيّ", en: "Uniform" },
};

type Asset = {
  id: number;
  asset_no: string;
  name_ar: string;
  category: string;
  category_label: string;
  serial_number: string;
  value: string;
  employee_no: string;
  name: string;
  assigned_date: string;
  returned_date: string | null;
  status: string;
  status_label: string;
  is_outstanding: boolean;
};

type Emp = { id: number; employee_no: string; name_ar: string };

export default function AssetsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Asset[]>([]);
  const [emps, setEmps] = useState<Emp[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [adding, setAdding] = useState(false);
  const [onlyOut, setOnlyOut] = useState(true);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [askRet, setAskRet] = useState<number | null>(null);
  const [retStatus, setRetStatus] = useState("returned");

  const load = useCallback(() => {
    apiGet<Asset[]>("/assets/")
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
        setCanEdit((d.permissions || []).includes("employees.edit")))
      .catch(() => setCanEdit(false));
    apiGet<Emp[]>("/employees/").then(setEmps).catch(() => setEmps([]));
  }, []);

  function startNew() {
    setDraft({
      employment_id: "", name_ar: "", category: "device",
      serial_number: "", value: "",
      assigned_date: new Date().toISOString().slice(0, 10),
      condition_note: "",
    });
    setAdding(true);
    setErr("");
  }

  async function save() {
    setSaving(true);
    setErr("");
    try {
      await apiPost("/assets/", {
        ...draft,
        employment_id: Number(draft.employment_id),
      });
      setAdding(false);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function doReturn(id: number) {
    try {
      await apiPost(`/assets/${id}/return/`, { status: retStatus });
      load();
    } catch (e) {
      setErr((e as ApiError).message);
      setTimeout(() => setErr(""), 6000);
    }
  }

  const f = (k: string) => String(draft[k] ?? "");
  const set = (k: string, v: unknown) =>
    setDraft((d) => ({ ...d, [k]: v }));

  const visible = onlyOut ? rows.filter((r) => r.is_outstanding) : rows;

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
        open={askRet !== null}
        confirmLabel={L("ret")}
        message={L("confirmReturn")}
        onCancel={() => setAskRet(null)}
        onConfirm={() => {
          const id = askRet;
          setAskRet(null);
          if (id !== null) doReturn(id);
        }}
      />

      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className={`btn btn-sm ${
            onlyOut ? "btn-primary" : "btn-ghost"}`}
            onClick={() => setOnlyOut(true)}>
            {L("onlyOutstanding")}
          </button>
          <button className={`btn btn-sm ${
            !onlyOut ? "btn-primary" : "btn-ghost"}`}
            onClick={() => setOnlyOut(false)}>
            {L("all")}
          </button>
          {canEdit && !adding && (
            <button className="btn btn-primary btn-sm" onClick={startNew}>
              <IcPlus size={16} />
              {L("add")}
            </button>
          )}
        </div>
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
            <div className="field" style={{ minWidth: 220 }}>
              <label className="label">{L("employee")}</label>
              <select className="select" value={f("employment_id")}
                onChange={(e) => set("employment_id", e.target.value)}>
                <option value="">— {L("pickEmployee")} —</option>
                {emps.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.employee_no} — {e.name_ar}
                  </option>
                ))}
              </select>
            </div>

            <div className="field" style={{ minWidth: 190 }}>
              <label className="label">{L("name")}</label>
              <input className="input" value={f("name_ar")}
                onChange={(e) => set("name_ar", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 150 }}>
              <label className="label">{L("category")}</label>
              <select className="select" value={f("category")}
                onChange={(e) => set("category", e.target.value)}>
                <option value="device">{L("catDevice")}</option>
                <option value="vehicle">{L("catVehicle")}</option>
                <option value="tool">{L("catTool")}</option>
                <option value="uniform">{L("catUniform")}</option>
                <option value="other">{L("catOther")}</option>
              </select>
            </div>

            <div className="field" style={{ minWidth: 160 }}>
              <label className="label">{L("serial")}</label>
              <input className="input" value={f("serial_number")}
                onChange={(e) => set("serial_number", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 130 }}>
              <label className="label">{L("value")}</label>
              <input className="input num" value={f("value")}
                onChange={(e) => set("value", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 165 }}>
              <label className="label">{L("assigned")}</label>
              <DateField value={f("assigned_date")}
                onChange={(v) => set("assigned_date", v)} />
            </div>

            <div className="field" style={{ minWidth: 200 }}>
              <label className="label">{L("note")}</label>
              <input className="input" value={f("condition_note")}
                onChange={(e) => set("condition_note", e.target.value)} />
            </div>
          </div>

          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn btn-primary btn-sm" disabled={saving}
              onClick={save}>
              <IcCheck size={16} />
              {L("save")}
            </button>
            <button className="btn btn-ghost btn-sm"
              onClick={() => { setAdding(false); setErr(""); }}>
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
        ) : visible.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <IcDoc size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("no")}</th>
                  <th>{L("name")}</th>
                  <th>{L("employee")}</th>
                  <th style={{ textAlign: "end" }}>{L("value")}</th>
                  <th>{L("assigned")}</th>
                  <th>{L("status")}</th>
                  <th style={{ width: 180 }} />
                </tr>
              </thead>
              <tbody>
                {visible.map((a) => (
                  <tr key={a.id}>
                    <td><span className="num">{a.asset_no}</span></td>
                    <td>
                      {a.name_ar}
                      <div className="muted" style={{ fontSize: ".78rem" }}>
                        {a.category_label}
                        {a.serial_number && ` · ${a.serial_number}`}
                      </div>
                    </td>
                    <td className="truncate">
                      <span className="num">{a.employee_no}</span>
                      {" — "}{a.name}
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{a.value}</span>
                    </td>
                    <td><span className="num">{a.assigned_date}</span></td>
                    <td>
                      <span className={a.is_outstanding
                        ? "badge badge-warn" : "badge badge-ok"}>
                        {a.status_label}
                      </span>
                    </td>
                    <td>
                      {canEdit && a.is_outstanding && (
                        <div className="row" style={{ gap: 6 }}>
                          <select className="select"
                            style={{ maxWidth: 110, fontSize: ".82rem" }}
                            value={retStatus}
                            onChange={(e) => setRetStatus(e.target.value)}>
                            <option value="returned">{L("retOk")}</option>
                            <option value="damaged">{L("retDamaged")}</option>
                            <option value="lost">{L("retLost")}</option>
                          </select>
                          <button className="btn btn-sm btn-ghost"
                            onClick={() => setAskRet(a.id)}>
                            {L("ret")}
                          </button>
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
