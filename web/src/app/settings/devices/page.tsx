"use client";

/**
 * أجهزة البصمة.
 *
 * والمفتاح يُعرض مرة واحدة عند الإنشاء: من يقرأ القاعدة لا ينتحل
 * جهازًا، ومن ينساه يُنشئ جهازًا جديدًا.
 */
import { useCallback, useEffect, useState } from "react";

import { apiDelete, apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import { IcAlert, IcCheck, IcClock, IcPlus, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "أجهزة البصمة", en: "Punch devices" },
  subtitle: {
    ar: "الأجهزة المصرَّح لها بإرسال البصمات",
    en: "Devices allowed to submit punches",
  },
  add: { ar: "جهاز جديد", en: "New device" },
  code: { ar: "رمز الجهاز", en: "Device code" },
  name: { ar: "الاسم", en: "Name" },
  site: { ar: "الموقع", en: "Site" },
  noSite: { ar: "بلا موقع", en: "No site" },
  lastSeen: { ar: "آخر اتصال", en: "Last seen" },
  never: { ar: "لم يتصل بعد", en: "Never" },
  status: { ar: "الحالة", en: "Status" },
  active: { ar: "نشط", en: "Active" },
  inactive: { ar: "معطّل", en: "Inactive" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا أجهزة", en: "No devices" },
  noAccess: {
    ar: "لا تملك صلاحية إدارة الأجهزة",
    en: "You cannot manage devices",
  },
  confirmDelete: {
    ar: "حذف الجهاز؟ لن يستطيع إرسال بصمات بعدها.",
    en: "Delete? It will no longer submit punches.",
  },
  codeHint: {
    ar: "الرمز لا يُعدَّل — الجهاز يُصادق به",
    en: "The code cannot change — the device authenticates with it",
  },
  keyTitle: { ar: "مفتاح الجهاز", en: "Device key" },
  keyHint: {
    ar: "احفظه الآن — لا يُعرض مرة أخرى، ومن ينساه يُنشئ جهازًا جديدًا",
    en: "Save it now — it is never shown again",
  },
  copy: { ar: "نسخ", en: "Copy" },
  copied: { ar: "نُسخ", en: "Copied" },
  close: { ar: "إغلاق", en: "Close" },
};

type Device = {
  id: number;
  device_code: string;
  name_ar: string;
  site: string | null;
  site_id: number | null;
  last_seen_at: string | null;
  is_active: boolean;
};

type Site = { id: number; name_ar: string };

export default function DevicesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Device[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [askDel, setAskDel] = useState<number | null>(null);
  const [newKey, setNewKey] = useState("");
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    apiGet<Device[]>("/attendance/devices/")
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
        setCanEdit((d.permissions || []).includes("sites.manage")))
      .catch(() => setCanEdit(false));
    apiGet<Site[]>("/sites/").then(setSites).catch(() => setSites([]));
  }, []);

  async function save() {
    setSaving(true);
    setErr("");
    try {
      if (editing === "new") {
        const r = await apiPost<{ api_key?: string }>(
          "/attendance/devices/", draft);
        if (r?.api_key) {
          setNewKey(r.api_key);
          setCopied(false);
        }
      } else {
        await apiPut(`/attendance/devices/${editing}/`, draft);
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
      await apiDelete(`/attendance/devices/${id}/`);
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

      {/* المفتاح يُعرض مرة واحدة */}
      {newKey && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 300,
          background: "rgba(16,28,38,.45)",
          display: "grid", placeItems: "center", padding: 20,
        }}>
          <div className="card" style={{
            width: "100%", maxWidth: 520, padding: 24,
          }}>
            <h3 style={{ fontSize: "1.05rem", marginBottom: 6 }}>
              {L("keyTitle")}
            </h3>
            <div style={{
              background: "var(--copper-soft)", color: "var(--copper)",
              padding: "10px 14px", borderRadius: "var(--radius-sm)",
              fontSize: ".86rem", marginBottom: 14,
            }}>
              {L("keyHint")}
            </div>
            <div className="num" style={{
              background: "var(--paper-2)", padding: "12px 14px",
              borderRadius: "var(--radius-sm)", wordBreak: "break-all",
              fontSize: ".88rem", marginBottom: 14,
            }}>
              {newKey}
            </div>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn btn-ghost btn-sm"
                onClick={() => {
                  navigator.clipboard?.writeText(newKey);
                  setCopied(true);
                }}>
                {copied ? L("copied") : L("copy")}
              </button>
              <button className="btn btn-primary btn-sm"
                onClick={() => setNewKey("")}>
                {L("close")}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        {canEdit && editing === null && (
          <button className="btn btn-primary" onClick={() => {
            setDraft({ device_code: "", name_ar: "", site_id: "",
                       is_active: true });
            setEditing("new");
            setErr("");
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

      {editing !== null && (
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <div className="field" style={{ minWidth: 160 }}>
              <label className="label">{L("code")}</label>
              <input className="input" value={f("device_code")}
                disabled={editing !== "new"}
                onChange={(e) =>
                  set("device_code", e.target.value.toUpperCase())} />
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

            <div className="field" style={{ minWidth: 180 }}>
              <label className="label">{L("site")}</label>
              <select className="select" value={f("site_id")}
                onChange={(e) => set("site_id", e.target.value)}>
                <option value="">— {L("noSite")} —</option>
                {sites.map((s) => (
                  <option key={s.id} value={s.id}>{s.name_ar}</option>
                ))}
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
            <IcClock size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("code")}</th>
                  <th>{L("name")}</th>
                  <th>{L("site")}</th>
                  <th>{L("lastSeen")}</th>
                  <th>{L("status")}</th>
                  <th style={{ width: 140 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.id}>
                    <td><span className="num">{d.device_code}</span></td>
                    <td>{d.name_ar}</td>
                    <td className="muted">{d.site || L("noSite")}</td>
                    <td className="muted">
                      {d.last_seen_at
                        ? <span className="num">
                            {String(d.last_seen_at).slice(0, 16)
                              .replace("T", " ")}
                          </span>
                        : L("never")}
                    </td>
                    <td>
                      <span className={d.is_active
                        ? "badge badge-ok" : "badge"}>
                        {d.is_active ? L("active") : L("inactive")}
                      </span>
                    </td>
                    <td>
                      {canEdit && (
                        <div className="row" style={{ gap: 6 }}>
                          <button className="btn btn-sm btn-ghost"
                            onClick={() => {
                              setDraft({
                                name_ar: d.name_ar,
                                site_id: d.site_id ?? "",
                                is_active: d.is_active,
                                device_code: d.device_code,
                              });
                              setEditing(d.id);
                              setErr("");
                            }}>
                            {L("edit")}
                          </button>
                          <button className="btn btn-sm btn-ghost"
                            style={{ color: "var(--danger)" }}
                            onClick={() => setAskDel(d.id)}>
                            {L("del")}
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
