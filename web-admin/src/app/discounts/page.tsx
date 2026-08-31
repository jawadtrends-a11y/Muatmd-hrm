"use client";

/**
 * إدارة الخصومات (ق-47).
 *
 * ثلاثة أنواع: كود يُدخله العميل، وسعر خاص مستمر، وخصم لمرة
 * واحدة. والخصم السنوي يُضبط هنا لا في بذرة الباقة.
 */
import { useCallback, useEffect, useState } from "react";

import { pGet, pPost, pDelete, AdminError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcPlus, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الخصومات", en: "Discounts" },
  subtitle: {
    ar: "الخصم السنوي يُضبط هنا لا في بذرة الباقة — فيبقى مرئيًا ومتغيّرًا",
    en: "Discounts are managed here, not buried in plan seeds",
  },
  newDiscount: { ar: "خصم جديد", en: "New discount" },
  code: { ar: "الكود", en: "Code" },
  name: { ar: "الاسم", en: "Name" },
  scope: { ar: "النوع", en: "Type" },
  value: { ar: "القيمة", en: "Value" },
  used: { ar: "الاستخدام", en: "Used" },
  validUntil: { ar: "صالح حتى", en: "Valid until" },
  status: { ar: "الحالة", en: "Status" },
  coupon: { ar: "كود خصم", en: "Coupon" },
  recurring: { ar: "سعر خاص مستمر", en: "Recurring" },
  one_time: { ar: "لمرة واحدة", en: "One-time" },
  percent: { ar: "نسبة %", en: "Percent %" },
  amount: { ar: "مبلغ ثابت", en: "Fixed amount" },
  active: { ar: "نشط", en: "Active" },
  inactive: { ar: "معطّل", en: "Inactive" },
  deactivate: { ar: "تعطيل", en: "Deactivate" },
  create: { ar: "إنشاء", en: "Create" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  kind: { ar: "طريقة الحساب", en: "Calculation" },
  maxUses: { ar: "أقصى استخدام", en: "Max uses" },
  coversSetup: { ar: "يشمل رسوم الإعداد", en: "Covers setup fee" },
  cycle: { ar: "يسري على الدورة", en: "Applies to cycle" },
  allCycles: { ar: "الدورتان", en: "Both cycles" },
  monthly: { ar: "شهري", en: "Monthly" },
  annual: { ar: "سنوي", en: "Annual" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا خصومات", en: "No discounts" },
  noAccess: { ar: "لا صلاحية", en: "No access" },
  unlimited: { ar: "بلا حد", en: "Unlimited" },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
};

type Discount = {
  id: number;
  code: string;
  name_ar: string;
  scope: string;
  scope_label: string;
  kind: string;
  value: string;
  applies_to_cycle: string;
  covers_setup_fee: boolean;
  valid_until: string | null;
  max_uses: number | null;
  used_count: number;
  is_active: boolean;
};

function NewDialog({
  L, onCreate, onClose, busy,
}: {
  L: (k: string, f?: string) => string;
  onCreate: (data: Record<string, unknown>) => void;
  onClose: () => void;
  busy: boolean;
}) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [scope, setScope] = useState("coupon");
  const [kind, setKind] = useState("percent");
  const [value, setValue] = useState("");
  const [cycle, setCycle] = useState("");
  const [maxUses, setMaxUses] = useState("");
  const [coversSetup, setCoversSetup] = useState(false);

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.5)",
      display: "grid", placeItems: "center", zIndex: 60, padding: 20,
    }}>
      <div className="card" style={{
        width: "100%", maxWidth: 420, padding: 24,
        maxHeight: "90vh", overflowY: "auto",
      }}>
        <h2 style={{ fontSize: "1.1rem", marginBottom: 16 }}>
          {L("newDiscount")}
        </h2>

        <div className="stack">
          <div className="field">
            <label className="label">{L("code")}</label>
            <input className="input" dir="ltr" value={code} autoFocus
              onChange={(e) => setCode(e.target.value.toUpperCase())} />
          </div>

          <div className="field">
            <label className="label">{L("name")}</label>
            <input className="input" value={name}
              onChange={(e) => setName(e.target.value)} />
          </div>

          <div className="field">
            <label className="label">{L("scope")}</label>
            <select className="select" value={scope}
              onChange={(e) => setScope(e.target.value)}>
              <option value="coupon">{L("coupon")}</option>
              <option value="recurring">{L("recurring")}</option>
              <option value="one_time">{L("one_time")}</option>
            </select>
          </div>

          <div className="row">
            <div className="field grow">
              <label className="label">{L("kind")}</label>
              <select className="select" value={kind}
                onChange={(e) => setKind(e.target.value)}>
                <option value="percent">{L("percent")}</option>
                <option value="amount">{L("amount")}</option>
              </select>
            </div>
            <div className="field grow">
              <label className="label">{L("value")}</label>
              <input type="number" className="input" value={value}
                onChange={(e) => setValue(e.target.value)} />
            </div>
          </div>

          <div className="field">
            <label className="label">{L("cycle")}</label>
            <select className="select" value={cycle}
              onChange={(e) => setCycle(e.target.value)}>
              <option value="">{L("allCycles")}</option>
              <option value="monthly">{L("monthly")}</option>
              <option value="annual">{L("annual")}</option>
            </select>
          </div>

          <div className="field">
            <label className="label">{L("maxUses")}</label>
            <input type="number" className="input" value={maxUses}
              placeholder={L("unlimited")}
              onChange={(e) => setMaxUses(e.target.value)} />
          </div>

          <div className="field">
            <label className="label">{L("coversSetup")}</label>
            <select className="select" value={coversSetup ? "1" : "0"}
              onChange={(e) => setCoversSetup(e.target.value === "1")}>
              <option value="0">{L("no")}</option>
              <option value="1">{L("yes")}</option>
            </select>
          </div>

          <div className="row" style={{ marginTop: 4 }}>
            <button className="btn btn-primary"
              disabled={busy || !code.trim() || !value}
              onClick={() => onCreate({
                code: code.trim(), name_ar: name.trim() || code.trim(),
                scope, kind, value,
                applies_to_cycle: cycle,
                max_uses: maxUses ? Number(maxUses) : null,
                covers_setup_fee: coversSetup,
              })}>
              {L("create")}
            </button>
            <button className="btn btn-ghost" onClick={onClose}>
              {L("cancel")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DiscountsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Discount[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [dialog, setDialog] = useState(false);
  const [acting, setActing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setRows(await pGet<Discount[]>("/platform/discounts/"));
    } catch (e) {
      setDenied((e as AdminError).isForbidden);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function create(data: Record<string, unknown>) {
    setActing(true);
    setError("");
    try {
      await pPost("/platform/discounts/", data);
      setDialog(false);
      await load();
    } catch (e) {
      setError((e as AdminError).message);
    } finally {
      setActing(false);
    }
  }

  async function deactivate(id: number) {
    await pDelete(`/platform/discounts/${id}/`).catch(() => {});
    await load();
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
      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => setDialog(true)}>
          <IcPlus size={17} />
          {L("newDiscount")}
        </button>
      </div>

      {error && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
        }}>
          {error}
        </div>
      )}

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("empty")}
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <colgroup>
                <col style={{ width: "150px" }} />
                <col style={{ width: "200px" }} />
                <col style={{ width: "150px" }} />
                <col style={{ width: "110px" }} />
                <col style={{ width: "110px" }} />
                <col style={{ width: "120px" }} />
                <col style={{ width: "110px" }} />
                <col style={{ width: "110px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th style={{ textAlign: "end" }}>{L("code")}</th>
                  <th>{L("name")}</th>
                  <th>{L("scope")}</th>
                  <th style={{ textAlign: "end" }}>{L("value")}</th>
                  <th style={{ textAlign: "end" }}>{L("used")}</th>
                  <th style={{ textAlign: "end" }}>{L("validUntil")}</th>
                  <th>{L("status")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.id} style={{ opacity: d.is_active ? 1 : 0.55 }}>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{d.code}</span>
                    </td>
                    <td>{d.name_ar}</td>
                    <td className="muted">{d.scope_label}</td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{d.value}</span>
                      {d.kind === "percent" ? "%" : ""}
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{d.used_count}</span>
                      {d.max_uses != null && (
                        <span className="muted">
                          {" / "}<span className="num">{d.max_uses}</span>
                        </span>
                      )}
                    </td>
                    <td style={{ textAlign: "end" }}>
                      {d.valid_until
                        ? <span className="num">{d.valid_until}</span> : "—"}
                    </td>
                    <td>
                      <span className={d.is_active ? "badge badge-ok" : "badge"}>
                        {d.is_active ? L("active") : L("inactive")}
                      </span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      {d.is_active && (
                        <button className="btn btn-sm btn-ghost"
                          style={{ color: "var(--danger)" }}
                          onClick={() => deactivate(d.id)}>
                          <IcX size={15} />
                          {L("deactivate")}
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

      {dialog && (
        <NewDialog L={L} onCreate={create}
          onClose={() => setDialog(false)} busy={acting} />
      )}
    </div>
  );
}
