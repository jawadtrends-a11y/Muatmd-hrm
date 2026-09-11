"use client";
/**
 * دليل الزملاء (ق-131).
 *
 * ⚠️ **بلا بيانات حسّاسة** — فالدليل يفتحه كل موظف، ومن أراد
 * الملفّ يذهب إليه بصلاحيته.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcSearch, IcUsers } from "@/components/Icons";

const T: Dict = {
  title: { ar: "دليل الزملاء", en: "Directory" },
  sub: {
    ar: "ابحث عن زميلك ووسيلة التواصل معه",
    en: "Find a colleague and how to reach them",
  },
  search: { ar: "ابحث بالاسم أو الرقم أو الإدارة…", en: "Search…" },
  name: { ar: "الموظف", en: "Employee" },
  job: { ar: "المسمّى", en: "Job title" },
  dept: { ar: "الإدارة", en: "Department" },
  contact: { ar: "التواصل", en: "Contact" },
  empty: { ar: "لا نتائج", en: "No results" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "الدليل غير متاح في باقتكم", en: "Not in your plan" },
  count: { ar: "زميلًا", en: "colleagues" },
};

type Row = {
  employment_id: number; employee_no: string; name: string;
  job_title: string; department: string; branch: string;
  email: string; mobile: string;
};

export default function DirectoryPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Row[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ rows: Row[] }>("/directory/");
      setRows(d.rows);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const visible = q.trim()
    ? rows.filter((r) =>
        `${r.name} ${r.employee_no} ${r.job_title} ${r.department}`
          .toLowerCase().includes(q.toLowerCase()))
    : rows;

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

  return (
    <div className="stack">
      <div>
        <h1 style={{ margin: 0 }}>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("sub")}
        </div>
      </div>

      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div style={{ position: "relative", maxWidth: 380 }}>
        <span style={{ position: "absolute", insetInlineStart: 11, top: 10,
                       color: "var(--ink-3)", pointerEvents: "none" }}>
          <IcSearch size={17} />
        </span>
        <input className="input" style={{ paddingInlineStart: 36 }}
               placeholder={L("search")} value={q}
               onChange={(e) => setQ(e.target.value)} />
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {visible.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>
            <IcUsers size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("name")}</th>
                  <th style={{ width: 170 }}>{L("job")}</th>
                  <th style={{ width: 150 }}>{L("dept")}</th>
                  <th style={{ width: 220 }}>{L("contact")}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => (
                  <tr key={r.employment_id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{r.name}</div>
                      <div className="muted num"
                           style={{ fontSize: ".76rem" }}>
                        {r.employee_no}
                      </div>
                    </td>
                    <td className="muted">{r.job_title || "—"}</td>
                    <td className="muted">{r.department || "—"}</td>
                    <td>
                      {r.mobile && (
                        <a href={`tel:${r.mobile}`} className="num"
                           style={{ display: "block", fontSize: ".84rem" }}>
                          {r.mobile}
                        </a>
                      )}
                      {r.email && (
                        <a href={`mailto:${r.email}`}
                           style={{ fontSize: ".8rem",
                                    color: "var(--ink-3)" }}>
                          {r.email}
                        </a>
                      )}
                      {!r.mobile && !r.email && (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="muted" style={{ fontSize: ".85rem" }}>
        <span className="num">{visible.length}</span> {L("count")}
      </div>
    </div>
  );
}
