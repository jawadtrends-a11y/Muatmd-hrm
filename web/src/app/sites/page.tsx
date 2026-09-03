"use client";

/**
 * مواقع العمل (ق-62).
 *
 * المواقع مستقلة عن الفروع — فمشروع مؤقت أو موقع عميل ليس
 * فرعًا في السجل التجاري.
 */
import { useCallback, useEffect, useState } from "react";

import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcPlus, IcUsers, IcX } from "@/components/Icons";
import DateField from "@/components/DateField";
import SiteMap from "@/components/SiteMap";

const T: Dict = {
  title: { ar: "مواقع العمل", en: "Work sites" },
  subtitle: {
    ar: "نطاقات البصمة — مستقلة عن الفروع",
    en: "Punch geofences — independent of branches",
  },
  newSite: { ar: "موقع جديد", en: "New site" },
  code: { ar: "الرمز", en: "Code" },
  nameAr: { ar: "اسم الموقع", en: "Site name" },
  city: { ar: "المدينة", en: "City" },
  address: { ar: "العنوان", en: "Address" },
  latitude: { ar: "خط العرض", en: "Latitude" },
  longitude: { ar: "خط الطول", en: "Longitude" },
  radius: { ar: "نصف القطر (متر)", en: "Radius (m)" },
  radiusHint: { ar: "حجم الموقع نفسه", en: "Size of the site" },
  tolerance: { ar: "هامش التسامح (متر)", en: "Tolerance (m)" },
  toleranceHint: {
    ar: "بين 50 و500 — الـGPS يخطئ داخل المباني",
    en: "50 to 500 — GPS drifts indoors",
  },
  effectiveRadius: { ar: "النطاق المقبول", en: "Accepted range" },
  enforce: { ar: "التحقق من الموقع", en: "Enforce geofence" },
  enforceHint: {
    ar: "عند تعطيله تُقبل البصمة من أي مكان",
    en: "When off, punches are accepted anywhere",
  },
  employees: { ar: "الموظفون", en: "Employees" },
  devices: { ar: "الأجهزة", en: "Devices" },
  status: { ar: "الحالة", en: "Status" },
  active: { ar: "نشط", en: "Active" },
  inactive: { ar: "معطّل", en: "Inactive" },
  enforced: { ar: "محقَّق", en: "Enforced" },
  open: { ar: "مفتوح", en: "Open" },
  noCoords: { ar: "بلا إحداثيات", en: "No coordinates" },
  manage: { ar: "الموظفون", en: "Employees" },
  edit: { ar: "تعديل", en: "Edit" },
  deactivate: { ar: "تعطيل", en: "Deactivate" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا مواقع — أضف الأول", en: "No sites yet" },
  required: { ar: "الرمز والاسم مطلوبان", en: "Code and name required" },
  noAccess: { ar: "لا صلاحية لهذا القسم", en: "No access" },
  meters: { ar: "متر", en: "m" },
  pickOnMap: {
    ar: "حدّد الموقع على الخريطة",
    en: "Pick the location on the map",
  },
  assignTitle: { ar: "موظفو الموقع", en: "Site employees" },
  fromHint: {
    ar: "تاريخ بداية العمل في الموقع — البصمة تُقاس منه",
    en: "Start date at this site — attendance is measured from it",
  },
  since: { ar: "من", en: "From" },
  addEmployee: { ar: "إضافة موظف", en: "Add employee" },
  remove: { ar: "إزالة", en: "Remove" },
  close: { ar: "إغلاق", en: "Close" },
  primary: { ar: "أساسي", en: "Primary" },
};

type Site = {
  id: number; code: string; name_ar: string;
  city: string; address: string;
  latitude: string | null; longitude: string | null;
  radius_meters: number; tolerance_meters: number;
  effective_radius: number;
  enforce_geofence: boolean; has_coordinates: boolean;
  manager: string; employees: number; devices: number;
  is_active: boolean;
};

type Assignment = {
  id: number; employment_id: number;
  employee_no: string; name: string; is_primary: boolean;
};

type Employee = { id: number; employee_no: string; name_ar: string };


/* ══ نموذج الموقع — خارج المكوّن الرئيسي ══ */

function SiteForm({
  initial, L, onSave, onCancel, busy, error,
}: {
  initial: Site | null;
  L: (k: string, f?: string) => string;
  onSave: (data: Record<string, unknown>) => void;
  onCancel: () => void;
  busy: boolean;
  error: string;
}) {
  const [code, setCode] = useState(initial?.code ?? "");
  const [name, setName] = useState(initial?.name_ar ?? "");
  const [city, setCity] = useState(initial?.city ?? "");
  const [address, setAddress] = useState(initial?.address ?? "");
  const [lat, setLat] = useState<number | null>(
    initial?.latitude ? Number(initial.latitude) : null);
  const [lng, setLng] = useState<number | null>(
    initial?.longitude ? Number(initial.longitude) : null);
  const [radius, setRadius] = useState(initial?.radius_meters ?? 100);
  const [tolerance, setTolerance] = useState(initial?.tolerance_meters ?? 100);
  const [enforce, setEnforce] = useState(initial?.enforce_geofence ?? true);

  const missing = !code.trim() || !name.trim();
  const effective = radius + tolerance;

  return (
    <div className="card" style={{ padding: 20 }}>
      <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
        <div className="field" style={{ maxWidth: 140 }}>
          <label className="label">
            {L("code")}<span style={{ color: "var(--danger)" }}>*</span>
          </label>
          <input className="input" dir="ltr" value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())} />
        </div>
        <div className="field" style={{ maxWidth: 260 }}>
          <label className="label">
            {L("nameAr")}<span style={{ color: "var(--danger)" }}>*</span>
          </label>
          <input className="input" value={name}
            onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field" style={{ maxWidth: 160 }}>
          <label className="label">{L("city")}</label>
          <input className="input" value={city}
            onChange={(e) => setCity(e.target.value)} />
        </div>
        <div className="field" style={{ maxWidth: 280 }}>
          <label className="label">{L("address")}</label>
          <input className="input" value={address}
            onChange={(e) => setAddress(e.target.value)} />
        </div>
      </div>

      {/* ══ الخريطة ══ */}
      <div style={{ marginTop: 14 }}>
        <label className="label" style={{ marginBottom: 6, display: "block" }}>
          {L("pickOnMap")}
        </label>
        <SiteMap
          latitude={lat} longitude={lng} radius={effective}
          onPick={(la, ln) => { setLat(la); setLng(ln); }}
        />
      </div>

      {/* ══ الإحداثيات والنطاق ══ */}
      <div className="row" style={{
        flexWrap: "wrap", alignItems: "flex-start", marginTop: 14,
      }}>
        <div className="field" style={{ maxWidth: 170 }}>
          <label className="label">{L("latitude")}</label>
          <input className="input" dir="ltr" type="number" step="0.0000001"
            value={lat ?? ""}
            onChange={(e) => setLat(
              e.target.value === "" ? null : Number(e.target.value))} />
        </div>
        <div className="field" style={{ maxWidth: 170 }}>
          <label className="label">{L("longitude")}</label>
          <input className="input" dir="ltr" type="number" step="0.0000001"
            value={lng ?? ""}
            onChange={(e) => setLng(
              e.target.value === "" ? null : Number(e.target.value))} />
        </div>

        <div className="field" style={{ maxWidth: 150 }}>
          <label className="label">{L("radius")}</label>
          <input className="input" dir="ltr" type="number"
            min={20} max={5000} value={radius}
            onChange={(e) => setRadius(Number(e.target.value))} />
          <div className="hint">{L("radiusHint")}</div>
        </div>

        <div className="field" style={{ maxWidth: 170 }}>
          <label className="label">{L("tolerance")}</label>
          <input className="input" dir="ltr" type="number"
            min={50} max={500} step={10} value={tolerance}
            onChange={(e) => setTolerance(Number(e.target.value))} />
          <div className="hint">{L("toleranceHint")}</div>
        </div>

        <div className="field" style={{ maxWidth: 170 }}>
          <label className="label">{L("effectiveRadius")}</label>
          <div style={{
            padding: "9px 12px", background: "var(--teal-soft)",
            borderRadius: "var(--radius-sm)", fontWeight: 600,
            color: "var(--teal)",
          }}>
            <span className="num">{effective}</span> {L("meters")}
          </div>
        </div>

        <div className="field" style={{ maxWidth: 190 }}>
          <label className="label">{L("enforce")}</label>
          <select className="select" value={enforce ? "1" : "0"}
            onChange={(e) => setEnforce(e.target.value === "1")}>
            <option value="1">{L("enforced")}</option>
            <option value="0">{L("open")}</option>
          </select>
          <div className="hint">{L("enforceHint")}</div>
        </div>
      </div>

      {error && (
        <div style={{
          marginTop: 12, background: "var(--danger-soft)",
          color: "var(--danger)", padding: "10px 13px",
          borderRadius: "var(--radius-sm)", fontSize: ".9rem",
        }}>
          {error}
        </div>
      )}

      <div className="row" style={{ marginTop: 16 }}>
        <button className="btn btn-primary" disabled={busy || missing}
          onClick={() => onSave({
            code: code.trim(), name_ar: name.trim(),
            city: city.trim(), address: address.trim(),
            latitude: lat, longitude: lng,
            radius_meters: radius, tolerance_meters: tolerance,
            enforce_geofence: enforce,
          })}>
          <IcCheck size={17} />
          {busy ? L("saving") : L("save")}
        </button>
        <button className="btn btn-ghost" onClick={onCancel}>
          {L("cancel")}
        </button>
        {missing && (
          <span className="muted" style={{ fontSize: ".85rem" }}>
            {L("required")}
          </span>
        )}
      </div>
    </div>
  );
}


/* ══ نافذة موظفي الموقع ══ */

function AssignDialog({
  site, L, onClose,
}: {
  site: Site;
  L: (k: string, f?: string) => string;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<Assignment[]>([]);
  const [pool, setPool] = useState<Employee[]>([]);
  const [pick, setPick] = useState("");
  /**
   * ق-77: النقل بتاريخ سريان — البصمة تُقاس بنطاق الموقع، فنقل
   * بلا تاريخ يجعل بصمات الأمس تُقاس بموقع اليوم.
   */
  const [err, setErr] = useState("");
  const [from, setFrom] = useState(
    () => new Date().toISOString().slice(0, 10));
  const [busy, setBusy] = useState(true);

  const load = useCallback(() => {
    Promise.all([
      apiGet<Assignment[]>(`/sites/${site.id}/employees/`).catch(() => []),
      apiGet<Employee[]>("/employees/?status=active").catch(() => []),
    ]).then(([a, e]) => { setRows(a); setPool(e); setBusy(false); });
  }, [site.id]);

  useEffect(load, [load]);

  const assigned = new Set(rows.map((r) => r.employment_id));
  const available = pool.filter((e) => !assigned.has(e.id));

  async function add() {
    if (!pick || !from) return;
    try {
      await apiPost(`/sites/${site.id}/employees/`, {
        employment_id: Number(pick),
        effective_from: from,      // ق-77: النقل بتاريخه
      });
      setPick("");
      setErr("");
      load();
    } catch (e) {
      // الخطأ يُعرض لا يُبلع: من يُسنِد يحتاج معرفة ما منعه
      setErr((e as ApiError).message);
    }
  }

  async function remove(id: number) {
    // apiDelete بلا جسم — المعرّف في الرابط
    await apiDelete(
      `/sites/${site.id}/employees/?employment_id=${id}`).catch(() => {});
    load();
  }

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", zIndex: 60, padding: 20,
    }}>
      <div className="card" style={{
        width: "100%", maxWidth: 560, padding: 24,
        maxHeight: "85vh", overflowY: "auto",
      }}>
        <div className="spread" style={{ marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: "1.1rem" }}>{L("assignTitle")}</h2>
            <div className="muted" style={{ fontSize: ".88rem" }}>
              {site.name_ar}
            </div>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={onClose}>
            <IcX size={16} />
          </button>
        </div>

        <div className="row" style={{ marginBottom: 16 }}>
          <select className="select grow" value={pick}
            onChange={(e) => setPick(e.target.value)}>
            <option value="">— {L("addEmployee")} —</option>
            {available.map((e) => (
              <option key={e.id} value={e.id}>
                {e.employee_no} — {e.name_ar}
              </option>
            ))}
          </select>
          {/* بلا maxWidth: النمط يُطبَّق على حاوية التقويم فتقصّه */}
          <div style={{ width: 165, flexShrink: 0 }}>
            <DateField value={from} onChange={setFrom} />
          </div>
          <button className="btn btn-primary" disabled={!pick || !from}
            onClick={add}>
            <IcPlus size={16} />
          </button>
        </div>

        {err && (
          <div style={{
            background: "var(--danger-soft)", color: "var(--danger)",
            padding: "9px 12px", borderRadius: "var(--radius-sm)",
            marginBottom: 12, fontSize: ".86rem",
          }}>
            {err}
          </div>
        )}

        {busy ? (
          <div style={{ padding: 24, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : rows.length === 0 ? (
          <div style={{ padding: 24, textAlign: "center", color: "var(--ink-3)" }}>
            {L("empty")}
          </div>
        ) : (
          rows.map((r) => (
            <div key={r.id} className="spread" style={{
              padding: "10px 0", borderBottom: "1px solid var(--line)",
            }}>
              <div>
                <span className="num">{r.employee_no}</span>
                {" — "}{r.name}
                {r.is_primary && (
                  <span className="badge badge-teal"
                    style={{ marginInlineStart: 8, fontSize: ".72rem" }}>
                    {L("primary")}
                  </span>
                )}
              </div>
              <button className="btn btn-sm btn-ghost"
                style={{ color: "var(--danger)" }}
                onClick={() => remove(r.employment_id)}>
                {L("remove")}
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ══ الشاشة ══ */

export default function SitesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Site[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [form, setForm] = useState<Site | null | "new">(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [assigning, setAssigning] = useState<Site | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setRows(await apiGet<Site[]>("/sites/"));
    } catch (e) {
      setDenied((e as ApiError).isForbidden);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  /**
   * الزر الذي يظهر ثم يُرفض عند الضغط خلل: يوهم المستخدم بقدرة
   * لا يملكها. فمن لا يملك تعديل الحضور لا يرى زر «موقع جديد» —
   * ومدير الإدارة يُسنِد موظفيه للمواقع المضافة ولا ينشئ (ق-68).
   */
  const [canManage, setCanManage] = useState(false);
  const [canAssign, setCanAssign] = useState(false);

  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((d) => {
        const p = new Set(d.permissions || []);
        setCanManage(p.has("sites.manage"));
        setCanAssign(p.has("sites.assign"));
      })
      .catch(() => { setCanManage(false); setCanAssign(false); });
  }, []);

  async function save(data: Record<string, unknown>) {
    setSaving(true);
    setError("");
    try {
      if (form && form !== "new") {
        await apiPut(`/sites/${form.id}/`, data);
      } else {
        await apiPost("/sites/", data);
      }
      setForm(null);
      await load();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function deactivate(site: Site) {
    await apiDelete(`/sites/${site.id}/`).catch(() => {});
    load();
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
        {!form && canManage && (
          <button className="btn btn-primary" onClick={() => {
            setForm("new"); setError("");
          }}>
            <IcPlus size={17} />
            {L("newSite")}
          </button>
        )}
      </div>

      {form && (
        <SiteForm
          initial={form === "new" ? null : form}
          L={L} onSave={save} onCancel={() => setForm(null)}
          busy={saving} error={error} />
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
                <col style={{ width: "110px" }} />
                <col style={{ width: "220px" }} />
                <col style={{ width: "130px" }} />
                <col style={{ width: "140px" }} />
                <col style={{ width: "120px" }} />
                <col style={{ width: "100px" }} />
                <col style={{ width: "210px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th>{L("code")}</th>
                  <th>{L("nameAr")}</th>
                  <th>{L("city")}</th>
                  <th style={{ textAlign: "end" }}>{L("effectiveRadius")}</th>
                  <th>{L("enforce")}</th>
                  <th style={{ textAlign: "end" }}>{L("employees")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id} style={{ opacity: s.is_active ? 1 : 0.55 }}>
                    <td><span className="num">{s.code}</span></td>
                    <td>{s.name_ar}</td>
                    <td className="muted">{s.city || "—"}</td>
                    <td style={{ textAlign: "end" }}>
                      {s.has_coordinates ? (
                        <>
                          <span className="num">{s.effective_radius}</span>{" "}
                          {L("meters")}
                        </>
                      ) : (
                        <span className="badge badge-warn">{L("noCoords")}</span>
                      )}
                    </td>
                    <td>
                      <span className={s.enforce_geofence
                        ? "badge badge-ok" : "badge"}>
                        {s.enforce_geofence ? L("enforced") : L("open")}
                      </span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{s.employees}</span>
                    </td>
                    <td>
                      <div className="row" style={{
                        gap: 6, justifyContent: "flex-end",
                      }}>
                        {/* كل زر بصلاحيته: من يُسنِد ليس بالضرورة
                            من يُنشئ، ومن يطّلع لا يرى الأزرار (ق-78) */}
                        {canAssign && (
                          <button className="btn btn-sm btn-ghost"
                            onClick={() => setAssigning(s)}>
                            <IcUsers size={15} />
                            {L("manage")}
                          </button>
                        )}
                        {canManage && (
                          <button className="btn btn-sm btn-ghost"
                            onClick={() => { setForm(s); setError(""); }}>
                            {L("edit")}
                          </button>
                        )}
                        {canManage && s.is_active && (
                          <button className="btn btn-sm btn-ghost"
                            style={{ color: "var(--danger)" }}
                            onClick={() => deactivate(s)}>
                            {L("deactivate")}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {assigning && (
        <AssignDialog site={assigning} L={L}
          onClose={() => { setAssigning(null); load(); }} />
      )}
    </div>
  );
}
