"use client";

/**
 * قائمة المرؤوسين (ق-68).
 *
 * المشرف يرى موظفيه هو فقط — والنطاق team في الخادم هو ما يحصره،
 * لا شرط في الواجهة. فمدير الإدارة يفتح الشاشة نفسها ويرى قسمه.
 */
import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcUsers } from "@/components/Icons";

const T: Dict = {
  title: { ar: "قائمة المرؤوسين", en: "Team members" },
  hint: {
    ar: "موظفوك المباشرون — والاسم يفتح ملفه",
    en: "Your direct reports — click a name to open the profile",
  },
  no: { ar: "الرقم", en: "No." },
  name: { ar: "الموظف", en: "Employee" },
  jobTitle: { ar: "المسمى", en: "Job title" },
  department: { ar: "القسم", en: "Department" },
  joinDate: { ar: "تاريخ الالتحاق", en: "Joined" },
  status: { ar: "الحالة", en: "Status" },
  empty: { ar: "لا مرؤوسين", en: "No team members" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  error: { ar: "تعذّر التحميل", en: "Could not load" },
  count: { ar: "الإجمالي", en: "Total" },
};

type Row = {
  id: number;
  employee_no: string;
  name_ar: string;
  job_title?: string | null;
  department?: string | null;
  join_date?: string | null;
  status?: string;
  status_label?: string;
};

export default function TeamMembersPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    apiGet<Row[] | { rows: Row[] }>("/employees/")
      .then((res) => {
        if (!alive) return;
        setRows(Array.isArray(res) ? res : (res.rows ?? []));
        setBusy(false);
      })
      .catch((e: ApiError) => {
        if (!alive) return;
        setError(e.message || L("error"));
        setBusy(false);
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("hint")}
          </div>
        </div>
        {!busy && !error && (
          <span className="badge">
            {L("count")}: <span className="num">{rows.length}</span>
          </span>
        )}
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : error ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--danger)" }}>
            {error}
          </div>
        ) : rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <IcUsers size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ textAlign: "end" }}>{L("no")}</th>
                  <th>{L("name")}</th>
                  <th>{L("jobTitle")}</th>
                  <th>{L("department")}</th>
                  <th style={{ textAlign: "end" }}>{L("joinDate")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{r.employee_no}</span>
                    </td>
                    <td className="truncate">
                      <Link href={`/employees/${r.id}`}
                        style={{ color: "var(--teal)", fontWeight: 500 }}>
                        {r.name_ar}
                      </Link>
                    </td>
                    <td className="truncate muted">{r.job_title || "—"}</td>
                    <td className="truncate muted">{r.department || "—"}</td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{r.join_date || "—"}</span>
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
