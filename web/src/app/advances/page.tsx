"use client";

/**
 * السلف — طلبها واعتمادها ومتابعة سدادها.
 *
 * والسلفة تُخصم من المسير قسطًا قسطًا، فمن يمنحها يرى ما بقي على
 * الموظف قبل أن يمنحه أخرى.
 */
import { useCallback, useEffect, useState } from "react";

import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import { IcAlert, IcCheck, IcPlus, IcWallet, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "السلف", en: "Advances" },
  subtitle: {
    ar: "السلف الممنوحة وأقساطها المتبقية",
    en: "Granted advances and their remaining instalments",
  },
  add: { ar: "سلفة جديدة", en: "New advance" },
  no: { ar: "الرقم", en: "No." },
  employee: { ar: "الموظف", en: "Employee" },
  amount: { ar: "المبلغ", en: "Amount" },
  repaid: { ar: "المسدَّد", en: "Repaid" },
  outstanding: { ar: "المتبقّي", en: "Outstanding" },
  method: { ar: "طريقة السداد", en: "Method" },
  installments: { ar: "الأقساط", en: "Instalments" },
  start: { ar: "يبدأ من", en: "Starts" },
  status: { ar: "الحالة", en: "Status" },
  approve: { ar: "اعتماد", en: "Approve" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا سلف", en: "No advances" },
  noAccess: { ar: "لا تملك هذه الصلاحية", en: "Not permitted" },
  disabled: {
    ar: "نظام السلف غير مفعّل — فعّله من إعدادات الرواتب",
    en: "Advances are disabled — enable them in payroll settings",
  },
  pickEmployee: { ar: "اختر الموظف", en: "Pick employee" },
  count: { ar: "عدد الأقساط", en: "Instalments" },
  startYear: { ar: "سنة البداية", en: "Start year" },
  startMonth: { ar: "شهر البداية", en: "Start month" },
  note: { ar: "ملاحظة", en: "Note" },
  confirmApprove: {
    ar: "اعتماد السلفة؟ ستُخصم أقساطها من المسير ولا يُعاد القرار.",
    en: "Approve? Instalments will be deducted and this is final.",
  },
};

type Advance = {
  id: number;
  advance_no: string;
  employee_no: string;
  name: string;
  amount: string;
  repaid: string;
  outstanding: string;
  repayment_label: string;
  installments_count: number;
  installment_amount: string | null;
  start: string;
  status: string;
  status_label: string;
};

type Emp = { id: number; employee_no: string; name_ar: string };

export default function AdvancesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Advance[]>([]);
  const [emps, setEmps] = useState<Emp[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [off, setOff] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [askApprove, setAskApprove] = useState<number | null>(null);

  const load = useCallback(() => {
    apiGet<Advance[]>("/advances/")
      .then((d) => { setRows(d); setBusy(false); })
      .catch((e: ApiError) => {
        if (e.status === 409) setOff(true);
        else if (e.status === 403) setDenied(true);
        setBusy(false);
      });
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((d) =>
        setCanEdit((d.permissions || []).includes("payroll.structures")))
      .catch(() => setCanEdit(false));
    apiGet<Emp[]>("/employees/").then(setEmps).catch(() => setEmps([]));
  }, []);

  function startNew() {
    const now = new Date();
    setDraft({
      employment_id: "", amount: "", installments_count: 6,
      repayment_method: "installments",
      start_year: now.getFullYear(),
      start_month: now.getMonth() + 2 > 12 ? 1 : now.getMonth() + 2,
      note: "",
    });
    setAdding(true);
    setErr("");
  }

  async function save() {
    setSaving(true);
    setErr("");
    try {
      await apiPost("/advances/", {
        ...draft,
        employment_id: Number(draft.employment_id),
        installments_count: Number(draft.installments_count),
        start_year: Number(draft.start_year),
        start_month: Number(draft.start_month),
      });
      setAdding(false);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function approve(id: number) {
    try {
      await apiPost(`/advances/${id}/approve/`, {});
      load();
    } catch (e) {
      setErr((e as ApiError).message);
      setTimeout(() => setErr(""), 6000);
    }
  }

  const f = (k: string) => String(draft[k] ?? "");
  const set = (k: string, v: unknown) =>
    setDraft((d) => ({ ...d, [k]: v }));

  if (off) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{L("disabled")}</div>
      </div>
    );
  }

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
        open={askApprove !== null}
        confirmLabel={L("approve")}
        message={L("confirmApprove")}
        onCancel={() => setAskApprove(null)}
        onConfirm={() => {
          const id = askApprove;
          setAskApprove(null);
          if (id !== null) approve(id);
        }}
      />

      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        {canEdit && !adding && (
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

            <div className="field" style={{ minWidth: 140 }}>
              <label className="label">{L("amount")}</label>
              <input className="input num" value={f("amount")}
                onChange={(e) => set("amount", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 120 }}>
              <label className="label">{L("count")}</label>
              <input className="input num" value={f("installments_count")}
                onChange={(e) =>
                  set("installments_count", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 120 }}>
              <label className="label">{L("startYear")}</label>
              <input className="input num" value={f("start_year")}
                onChange={(e) => set("start_year", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 120 }}>
              <label className="label">{L("startMonth")}</label>
              <input className="input num" value={f("start_month")}
                onChange={(e) => set("start_month", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 200 }}>
              <label className="label">{L("note")}</label>
              <input className="input" value={f("note")}
                onChange={(e) => set("note", e.target.value)} />
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
        ) : rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <IcWallet size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("no")}</th>
                  <th>{L("employee")}</th>
                  <th style={{ textAlign: "end" }}>{L("amount")}</th>
                  <th style={{ textAlign: "end" }}>{L("repaid")}</th>
                  <th style={{ textAlign: "end" }}>{L("outstanding")}</th>
                  <th>{L("installments")}</th>
                  <th>{L("start")}</th>
                  <th>{L("status")}</th>
                  <th style={{ width: 110 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id}>
                    <td><span className="num">{a.advance_no}</span></td>
                    <td className="truncate">
                      <span className="num">{a.employee_no}</span>
                      {" — "}{a.name}
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{a.amount}</span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num muted">{a.repaid}</span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num" style={{
                        fontWeight: 600,
                        color: Number(a.outstanding) > 0
                          ? "var(--copper)" : "var(--teal)",
                      }}>
                        {a.outstanding}
                      </span>
                    </td>
                    <td className="muted">
                      {a.installments_count}
                      {a.installment_amount && (
                        <span style={{ fontSize: ".8rem" }}>
                          {" × "}{a.installment_amount}
                        </span>
                      )}
                    </td>
                    <td><span className="num">{a.start}</span></td>
                    <td>
                      <span className={
                        a.status === "approved" || a.status === "active"
                          ? "badge badge-ok"
                          : a.status === "closed" ? "badge"
                          : "badge badge-warn"}>
                        {a.status_label}
                      </span>
                    </td>
                    <td>
                      {canEdit && a.status === "pending" && (
                        <button className="btn btn-sm btn-primary"
                          onClick={() => setAskApprove(a.id)}>
                          {L("approve")}
                        </button>
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
