"use client";

/**
 * إدارة الخصومات (ق-47).
 *
 * ثلاثة أنواع: كود يُدخله العميل، وسعر خاص مستمر، وخصم لمرة
 * واحدة. والخصم السنوي يُضبط هنا لا في بذرة الباقة.
 */
import { useCallback, useEffect, useState } from "react";

import { pGet, pPost, pPut, pDelete, AdminError } from "@/lib/api";
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
  campaign: { ar: "حملة عامة (بلا كود)", en: "Campaign (no code)" },
  audience: { ar: "الفئة المستهدفة", en: "Audience" },
  audAll: { ar: "جميع العملاء", en: "All customers" },
  audNew: { ar: "العملاء الجدد", en: "New customers" },
  audRenewal: { ar: "عملاء التجديد", en: "Renewals" },
  stackable: { ar: "يُجمع مع كود الخصم", en: "Stacks with coupon" },
  stackHint: {
    ar: "إن كان مطفأً فالأعلى قيمةً وحده يُطبَّق",
    en: "If off, only the larger discount applies",
  },
  campHint: {
    ar: "الكود معرّفٌ داخليٌّ لك — لا يراه العميل، والخصم يُطبَّق تلقائيًّا",
    en: "The code is an internal label — applied automatically",
  },
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
  edit: { ar: "تعديل", en: "Edit" },
  save: { ar: "حفظ", en: "Save" },
  codeLocked: { ar: "الكود لا يُعدَّل — فهو مرجع الإيصالات الصادرة",
                en: "Code cannot be changed" },
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
  audience?: string;
  audience_label?: string;
  stackable?: boolean;
  valid_from?: string | null;
};

function NewDialog({
  L, onCreate, onClose, busy, initial,
}: {
  L: (k: string, f?: string) => string;
  onCreate: (data: Record<string, unknown>) => void;
  onClose: () => void;
  busy: boolean;
  /** ⚠️⚠️ ق-٢٩٢: **حملةٌ بقيمةٍ خاطئةٍ كانت تُعطَّل وتُعاد** (تنبيه
   *  جواد) — فالحوار نفسه يُعدّل. **والكود لا يُمسّ**: هو مرجع ما
   *  صدر من إيصالات، وتغييرُه يقطع أثرها. */
  initial?: Discount | null;
}) {
  const ed = !!initial;
  const [code, setCode] = useState(initial?.code || "");
  const [name, setName] = useState(initial?.name_ar || "");
  const [scope, setScope] = useState(initial?.scope || "coupon");
  const [audience, setAudience] = useState(initial?.audience || "all");
  const [stackable, setStackable] = useState(!!initial?.stackable);
  const [kind, setKind] = useState(initial?.kind || "percent");
  const [value, setValue] = useState(initial?.value || "");
  const [cycle, setCycle] = useState(initial?.applies_to_cycle || "");
  const [active, setActive] = useState(initial?.is_active ?? true);
  const [maxUses, setMaxUses] = useState(
    initial?.max_uses != null ? String(initial.max_uses) : "");
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
            {/* ⚠️ ق-٢٩٢: **الكود لا يُعدَّل** — فهو مرجع ما صدر من
                إيصالات، وتغييرُه يقطع أثرها. */}
            <input className="input" dir="ltr" value={code}
              autoFocus={!ed} disabled={ed}
              onChange={(e) => setCode(e.target.value.toUpperCase())} />
            {ed && (
              <div className="muted" style={{ fontSize: ".8rem" }}>
                {L("codeLocked")}
              </div>
            )}
          </div>

          {ed && (
            <div className="field">
              <label className="row" style={{ gap: 8, cursor: "pointer" }}>
                <input type="checkbox" checked={active}
                  onChange={(e) => setActive(e.target.checked)} />
                <span>{L("active")}</span>
              </label>
            </div>
          )}

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
              <option value="campaign">{L("campaign")}</option>
            </select>
          </div>

          {/* ⭐ ق-٢٨٦: **حملةٌ عامّةٌ بلا كود** — كاليوم الوطنيّ ونهاية
              السنة. وحقولها تظهر معها وحدها. */}
          {scope === "campaign" && (
            <>
              <div className="field">
                <label className="label">{L("audience")}</label>
                <select className="select" value={audience}
                  onChange={(e) => setAudience(e.target.value)}>
                  <option value="all">{L("audAll")}</option>
                  <option value="new">{L("audNew")}</option>
                  <option value="renewal">{L("audRenewal")}</option>
                </select>
              </div>
              <div className="field">
                <label className="row" style={{ gap: 8, cursor: "pointer" }}>
                  <input type="checkbox" checked={stackable}
                    onChange={(e) => setStackable(e.target.checked)} />
                  <span>{L("stackable")}</span>
                </label>
                <div className="muted" style={{ fontSize: ".8rem" }}>
                  {L("stackHint")}
                </div>
                <div className="muted" style={{ fontSize: ".8rem",
                                                marginTop: 4 }}>
                  {L("campHint")}
                </div>
              </div>
            </>
          )}

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
                audience, stackable, is_active: active,
              })}>
              {L(ed ? "save" : "create")}
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

  // ⚠️ ق-٢٩٢: الحوار نفسه يُنشئ ويُعدّل — والكود ثابتٌ في التعديل
  const [editing, setEditing] = useState<Discount | null>(null);

  async function update(data: Record<string, unknown>) {
    if (!editing) return;
    setActing(true);
    setError("");
    try {
      const { code: _c, scope: _s, kind: _k, ...rest } = data;
      await pPut(`/platform/discounts/${editing.id}/`, rest);
      setEditing(null);
      await load();
    } catch (e) {
      setError((e as AdminError).message);
    } finally {
      setActing(false);
    }
  }

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
                      {/* ⚠️⚠️ ق-٢٩٢: **والتعديل متاحٌ للمعطَّل كذلك** —
                          فمن عطّل حملةً بالخطأ **لا سبيل له لإعادتها**،
                          و`is_active` من حقول التعديل. */}
                      <button className="btn btn-sm btn-ghost"
                        onClick={() => setEditing(d)}>
                        {L("edit")}
                      </button>
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

      {(dialog || editing) && (
        <NewDialog L={L} initial={editing}
          onCreate={editing ? update : create}
          onClose={() => { setDialog(false); setEditing(null); }}
          busy={acting} />
      )}
    </div>
  );
}
