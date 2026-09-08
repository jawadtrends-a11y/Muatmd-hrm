"use client";
/**
 * الرئيسية — لوحة ودجتات يختارها المستخدم (ق-106).
 *
 * وليست ملفّه: الملف صفحة مستقلّة يفتحها من «ملفي». فالرئيسية
 * للمتابعة، وجمعُهما يجعلها عشر بطاقات فوق أحد عشر تبويبًا.
 *
 * والمعروض من صلاحياته ونطاقه: من لا فريق له لا تُعرض له بطاقات
 * الفريق أصلًا — لا في اللوحة ولا في قائمة الاختيار.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import PunchCard from "@/components/PunchCard";
import WidgetCard, { type Widget } from "@/components/DashboardWidgets";
import { IcAlert, IcCheck, IcSettings, IcX } from "@/components/Icons";

const T: Dict = {
  welcome: { ar: "مرحبًا", en: "Welcome" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  customize: { ar: "تخصيص اللوحة", en: "Customize" },
  done: { ar: "تمّ", en: "Done" },
  arrange: { ar: "ترتيب", en: "Arrange" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  saved: { ar: "حُفظت لوحتك", en: "Saved" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  pick: {
    ar: "اختر ما تريد متابعته — المتاح لك حسب دورك",
    en: "Pick what to follow — limited to your role",
  },
  empty: {
    ar: "لا بطاقات مختارة — اضغط «تخصيص اللوحة»",
    en: "No cards selected — press Customize",
  },
};

type Avail = { key: string; name: string; size: string; group: string;
               selected: boolean };
type Group = { key: string; name: string };

export default function HomePage() {
  const { L } = useT(T);
  const [name, setName] = useState("");
  const [data, setData] = useState<Record<string, Widget>>({});
  const [busy, setBusy] = useState(true);
  const [editing, setEditing] = useState(false);
  const [avail, setAvail] = useState<Avail[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  // ترتيب البطاقات وأحجامها — يسحبها المستخدم فتُحفظ.
  const [layout, setLayout] = useState<{ key: string; size?: string }[]>([]);
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [arranging, setArranging] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const ws = await apiGet<{ person?: { first_name?: string } }>(
        "/me/workspace/");
      setName(ws.person?.first_name || "");
      const pref = await apiGet<{ layout: { key: string; size?: string }[] }>(
        "/me/dashboard/");
      setLayout(pref.layout || []);
      setData(await apiGet<Record<string, Widget>>("/me/dashboard/data/"));
    } catch {
      /* اللوحة تُعرض فارغة لا بيضاء */
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openEditor = async () => {
    const d = await apiGet<{ available: Avail[]; groups: Group[];
                             selected: string[] }>("/me/dashboard/");
    setAvail(d.available);
    setGroups(d.groups);
    setPicked(d.selected);
    setEditing(true);
  };

  const toggle = (k: string) =>
    setPicked((p) => (p.includes(k) ? p.filter((x) => x !== k) : [...p, k]));

  const save = async () => {
    setSaving(true);
    try {
      await apiPut("/me/dashboard/", { widget_keys: picked });
      setEditing(false);
      setMsg(L("saved"));
      setTimeout(() => setMsg(""), 3000);
      await load();
    } finally { setSaving(false); }
  };

  const persist = useCallback(async (next: typeof layout) => {
    setLayout(next);
    await apiPut("/me/dashboard/", { widget_keys: next }).catch(() => null);
    setData(await apiGet<Record<string, Widget>>("/me/dashboard/data/")
      .catch(() => ({})));
  }, []);

  const onDrop = (target: string) => {
    if (!dragKey || dragKey === target) return;
    const next = [...layout];
    const from = next.findIndex((x) => x.key === dragKey);
    const to = next.findIndex((x) => x.key === target);
    if (from < 0 || to < 0) return;
    next.splice(to, 0, next.splice(from, 1)[0]);
    setDragKey(null);
    persist(next);
  };

  const cycleSize = (k: string) => {
    const order = ["sm", "md", "lg"];
    const next = layout.map((x) => {
      if (x.key !== k) return x;
      const cur = x.size || data[k]?.size || "md";
      return { ...x, size: order[(order.indexOf(cur) + 1) % order.length] };
    });
    persist(next);
  };

  const keys = layout.length
    ? layout.map((x) => x.key).filter((k) => data[k])
    : Object.keys(data);

  return (
    <div className="stack">
      <div className="spread">
        <h1 style={{ margin: 0 }}>
          {L("welcome")}{name ? `، ${name}` : ""}
        </h1>
        <div className="row" style={{ gap: 6 }}>
          <button className={`btn btn-sm ${arranging ? "btn-primary" : ""}`}
                  onClick={() => setArranging((v) => !v)}>
            {arranging ? L("done") : L("arrange")}
          </button>
          <button className="btn btn-sm" onClick={openEditor}>
            <IcSettings size={15} /> {L("customize")}
          </button>
        </div>
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}

      <PunchCard />

      {busy ? (
        <div className="card" style={{ padding: 40, textAlign: "center",
                                       color: "var(--ink-3)" }}>
          {L("loading")}
        </div>
      ) : keys.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: "center",
                                       color: "var(--ink-3)" }}>
          {L("empty")}
        </div>
      ) : (
        <div style={{ display: "grid", gap: 14,
                      gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
          {keys.map((k) => (
            <div key={k}
                 draggable={arranging}
                 onDragStart={() => setDragKey(k)}
                 onDragOver={(e) => arranging && e.preventDefault()}
                 onDrop={() => onDrop(k)}
                 style={{
                   gridColumn: (data[k]?.size === "lg" ? "1 / -1"
                     : data[k]?.size === "md" ? "span 2" : "span 1"),
                   cursor: arranging ? "grab" : "default",
                   opacity: dragKey === k ? 0.5 : 1,
                 }}>
              <WidgetCard w={data[k]} arranging={arranging}
                          onResize={() => cycleSize(k)} />
            </div>
          ))}
        </div>
      )}

      {editing && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
          display: "grid", placeItems: "center", padding: 20, zIndex: 70,
        }} onClick={() => setEditing(false)}>
          <div className="card" style={{ padding: 24, maxWidth: 620,
                                         width: "100%", maxHeight: "80vh",
                                         overflowY: "auto" }}
               onClick={(e) => e.stopPropagation()}>
            <div className="spread" style={{ marginBottom: 4 }}>
              <h3 style={{ margin: 0 }}>{L("customize")}</h3>
              <button className="btn btn-ghost btn-sm"
                      onClick={() => setEditing(false)}>
                <IcX size={15} />
              </button>
            </div>
            <div className="muted" style={{ fontSize: ".85rem",
                                            marginBottom: 16 }}>
              {L("pick")}
            </div>

            {groups.map((g) => {
              const items = avail.filter((a) => a.group === g.key);
              if (!items.length) return null;
              return (
                <div key={g.key} style={{ marginBottom: 18 }}>
                  <div style={{ fontWeight: 600, fontSize: ".85rem",
                                color: "var(--teal)", marginBottom: 8 }}>
                    {g.name}
                  </div>
                  <div style={{ display: "grid", gap: 6 }}>
                    {items.map((a) => (
                      <label key={a.key} className="row"
                             style={{ gap: 10, cursor: "pointer",
                                      padding: "6px 8px",
                                      borderRadius: "var(--radius-sm)",
                                      background: picked.includes(a.key)
                                        ? "var(--teal-soft)" : "transparent" }}>
                        <input type="checkbox"
                               checked={picked.includes(a.key)}
                               onChange={() => toggle(a.key)} />
                        <span style={{ fontSize: ".9rem" }}>{a.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              );
            })}

            <div className="row" style={{ gap: 8, marginTop: 8 }}>
              <button className="btn btn-primary" onClick={save}
                      disabled={saving}>
                {saving ? L("saving") : L("save")}
              </button>
              <button className="btn" onClick={() => setEditing(false)}>
                {L("cancel")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
