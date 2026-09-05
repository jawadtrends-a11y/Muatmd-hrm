"use client";

/**
 * أنواع الإجازات وسياساتها (ق-83).
 *
 * ينبّه ولا يمنع: نظام العمل يتغيّر، ومن يبني لمئات الشركات لا
 * يعرقل مواكبتها. فمن ينقص عن الحد النظامي يرى تحذيرًا ويقرّر.
 */
import { useCallback, useEffect, useState } from "react";

import { apiDelete, apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import { IcAlert, IcCheck, IcLeave, IcPlus, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "أنواع الإجازات", en: "Leave types" },
  subtitle: {
    ar: "سياسات الاستحقاق والأجر والترحيل",
    en: "Entitlement, pay and carry-forward policies",
  },
  add: { ar: "نوع جديد", en: "New type" },
  code: { ar: "الرمز", en: "Code" },
  name: { ar: "الاسم", en: "Name" },
  paid: { ar: "مدفوعة", en: "Paid" },
  unpaid: { ar: "بلا أجر", en: "Unpaid" },
  payPct: { ar: "نسبة الأجر", en: "Pay %" },
  perYear: { ar: "أيام السنة", en: "Days/year" },
  perEvent: { ar: "أيام الحالة", en: "Days/event" },
  after5: { ar: "بعد 5 سنوات", en: "After 5y" },
  statutory: { ar: "الحد النظامي", en: "Statutory min" },
  carry: { ar: "الترحيل", en: "Carry forward" },
  actions: { ar: "الإجراءات", en: "Actions" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا أنواع", en: "No types" },
  noAccess: {
    ar: "لا تملك صلاحية إدارة الإجازات",
    en: "You cannot manage leave types",
  },
  belowStatutory: {
    ar: "دون الحد النظامي",
    en: "Below statutory minimum",
  },
  belowHint: {
    ar: "الأيام أقل من الحد النظامي — راجع نظام العمل",
    en: "Days are below the statutory minimum",
  },
  confirmDelete: {
    ar: "حذف هذا النوع؟ إن كان نظاميًا فإلغاؤه مخالف لنظام العمل، "
        + "ولا يُتراجع عن الحذف.",
    en: "Delete this type? If statutory, removing it breaches labour law.",
  },
  codeHint: {
    ar: "الرمز لا يُعدَّل بعد الإنشاء — المنطق يستدعيه",
    en: "The code cannot change — logic references it",
  },
  accrual: { ar: "طريقة الاستحقاق", en: "Accrual" },
  annual: { ar: "سنوية", en: "Annual" },
  perEventM: { ar: "بالحالة", en: "Per event" },
  none: { ar: "لا ترحيل", en: "None" },
  full: { ar: "كامل", en: "Full" },
  capped: { ar: "بحدّ أقصى", en: "Capped" },
};

type LeaveType = {
  id: number;
  code: string;
  name_ar: string;
  is_paid: boolean;
  pay_percentage: string;
  accrual_method: string;
  days_per_year: string;
  days_after_five_years: string;
  days_per_event: string;
  statutory_min_days: string;
  carry_forward_policy: string;
  max_carry_forward_days: string;
  below_statutory?: boolean;
};

type Draft = Partial<Record<keyof LeaveType, string | boolean>>;


/** رقم للعرض — والفارغ شرطة لا "None" */
function num(v?: string | null) {
  return v && v !== "None" ? v : "—";
}

export default function LeaveTypesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<LeaveType[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [askDel, setAskDel] = useState<number | null>(null);

  const load = useCallback(() => {
    apiGet<LeaveType[]>("/leaves/types/")
      .then((d) => { setRows(d); setBusy(false); })
      .catch((e: ApiError) => {
        setDenied(e.status === 403);
        setBusy(false);
      });
  }, []);

  useEffect(() => { load(); }, [load]);

  function startNew() {
    setDraft({
      code: "", name_ar: "", is_paid: true, pay_percentage: "100",
      accrual_method: "annual", days_per_year: "0",
      days_per_event: "0", days_after_five_years: "0",
      statutory_min_days: "0", carry_forward_policy: "none",
      max_carry_forward_days: "0",
    });
    setEditing("new");
    setErr("");
  }

  function startEdit(t: LeaveType) {
    setDraft({ ...t } as unknown as Draft);
    setEditing(t.id);
    setErr("");
  }

  async function save() {
    setSaving(true);
    setErr("");
    try {
      if (editing === "new") {
        await apiPost("/leaves/types/new/", draft);
      } else {
        await apiPut(`/leaves/types/${editing}/`, draft);
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
      await apiDelete(`/leaves/types/${id}/`);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
      setTimeout(() => setErr(""), 6000);
    }
  }

  /** الفراغ فراغ لا نص "None" — والمستخدم يرى حقلًا لا خطأً */
  const f = (k: keyof LeaveType) => {
    const v = draft[k];
    return v === null || v === undefined || v === "None" ? "" : String(v);
  };
  const set = (k: keyof LeaveType, v: string | boolean) =>
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
        {editing === null && (
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

      {editing !== null && (
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <div className="field" style={{ minWidth: 140 }}>
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

            <div className="field" style={{ minWidth: 190 }}>
              <label className="label">{L("name")}</label>
              <input className="input" value={f("name_ar")}
                onChange={(e) => set("name_ar", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 130 }}>
              <label className="label">{L("paid")}</label>
              <select className="select"
                value={draft.is_paid ? "1" : "0"}
                onChange={(e) => set("is_paid", e.target.value === "1")}>
                <option value="1">{L("paid")}</option>
                <option value="0">{L("unpaid")}</option>
              </select>
            </div>

            <div className="field" style={{ minWidth: 110 }}>
              <label className="label">{L("payPct")}</label>
              <input className="input num" value={f("pay_percentage")}
                onChange={(e) => set("pay_percentage", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 150 }}>
              <label className="label">{L("accrual")}</label>
              <select className="select" value={f("accrual_method")}
                onChange={(e) => set("accrual_method", e.target.value)}>
                <option value="annual">{L("annual")}</option>
                <option value="per_event">{L("perEventM")}</option>
              </select>
            </div>

            <div className="field" style={{ minWidth: 110 }}>
              <label className="label">{L("perYear")}</label>
              <input className="input num" value={f("days_per_year")}
                onChange={(e) => set("days_per_year", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 110 }}>
              <label className="label">{L("after5")}</label>
              <input className="input num" value={f("days_after_five_years")}
                onChange={(e) =>
                  set("days_after_five_years", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 110 }}>
              <label className="label">{L("perEvent")}</label>
              <input className="input num" value={f("days_per_event")}
                onChange={(e) => set("days_per_event", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 120 }}>
              <label className="label">{L("statutory")}</label>
              <input className="input num" value={f("statutory_min_days")}
                onChange={(e) => set("statutory_min_days", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 150 }}>
              <label className="label">{L("carry")}</label>
              <select className="select" value={f("carry_forward_policy")}
                onChange={(e) =>
                  set("carry_forward_policy", e.target.value)}>
                <option value="none">{L("none")}</option>
                <option value="full">{L("full")}</option>
                <option value="capped">{L("capped")}</option>
              </select>
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
            <IcLeave size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("code")}</th>
                  <th>{L("name")}</th>
                  <th>{L("paid")}</th>
                  <th style={{ textAlign: "end" }}>{L("perYear")}</th>
                  <th style={{ textAlign: "end" }}>{L("perEvent")}</th>
                  <th style={{ textAlign: "end" }}>{L("statutory")}</th>
                  <th style={{ width: 140 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id}>
                    <td><span className="num">{t.code}</span></td>
                    <td>
                      {t.name_ar}
                      {t.below_statutory && (
                        <span className="badge badge-warn" style={{
                          marginInlineStart: 8, fontSize: ".72rem",
                        }} title={L("belowHint")}>
                          {L("belowStatutory")}
                        </span>
                      )}
                    </td>
                    <td className="muted">
                      {t.is_paid
                        ? `${L("paid")} ${t.pay_percentage}%`
                        : L("unpaid")}
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{num(t.days_per_year)}</span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{num(t.days_per_event)}</span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num muted">
                        {num(t.statutory_min_days)}
                      </span>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 6 }}>
                        <button className="btn btn-sm btn-ghost"
                          onClick={() => startEdit(t)}>
                          {L("edit")}
                        </button>
                        <button className="btn btn-sm btn-ghost"
                          style={{ color: "var(--danger)" }}
                          onClick={() => setAskDel(t.id)}>
                          {L("del")}
                        </button>
                      </div>
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
