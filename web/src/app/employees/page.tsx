"use client";

/**
 * شاشة الموظفين.
 *
 * ق-15: التوظيف مستقل عن التسجيل النظامي — الأعلام الثلاثة
 * تُعرض صراحةً فيرى مدير الموارد من سُجّل ومن لم يُسجّل.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";

import DocList, { type Column, type Stat } from "@/components/DocList";
import { useT, type Dict } from "@/lib/prefs";

const T: Dict = {
  title: { ar: "الموظفون", en: "Employees" },
  subtitle: {
    ar: "الملفات الوظيفية وحالة التسجيل النظامي",
    en: "Employment records and statutory registration",
  },
  active: { ar: "على رأس العمل", en: "Active" },
  all: { ar: "الكل", en: "All" },
  terminated: { ar: "منتهية خدمتهم", en: "Terminated" },
  suspended: { ar: "موقوفون", en: "Suspended" },
  emptyHint: {
    ar: "ابدأ بإضافة أول موظف",
    en: "Add your first employee",
  },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
};

type Employee = {
  id: number;
  employee_no: string;
  name_ar: string;
  department: string;
  job_title: string;
  join_date: string;
  status: string;
  is_gosi_registered: boolean;
  is_mol_registered: boolean;
  include_in_wps: boolean;
};

const STATUSES = ["active", "", "suspended", "terminated"] as const;

export default function EmployeesPage() {
  const router = useRouter();
  const { L } = useT(T);
  const [status, setStatus] = useState<string>("active");

  const flag = (on: boolean) => (
    <span className={on ? "badge badge-ok" : "badge"}>
      {on ? L("yes") : L("no")}
    </span>
  );

  const columns: Column<Employee>[] = [
    { key: "employee_no", label: { ar: "الرقم الوظيفي", en: "Employee No." },
      width: 120, numeric: true },
    { key: "name_ar", label: { ar: "الموظف", en: "Employee" }, width: 240 },
    { key: "department", label: { ar: "القسم", en: "Department" }, width: 150 },
    { key: "job_title", label: { ar: "المسمى الوظيفي", en: "Job Title" },
      width: 160 },
    { key: "join_date", label: { ar: "المباشرة", en: "Joined" },
      width: 115, numeric: true },
    { key: "gosi", label: { ar: "التأمينات", en: "GOSI" }, width: 95,
      render: (r) => flag(r.is_gosi_registered) },
    { key: "mol", label: { ar: "قوى", en: "MOL" }, width: 85,
      render: (r) => flag(r.is_mol_registered) },
    { key: "wps", label: { ar: "حماية الأجور", en: "WPS" }, width: 110,
      render: (r) => flag(r.include_in_wps) },
    { key: "status", label: { ar: "الحالة", en: "Status" }, width: 120,
      render: (r) => (
        <span className={
          r.status === "active" ? "badge badge-ok"
            : r.status === "terminated" ? "badge" : "badge badge-warn"
        }>
          {r.status === "active" ? L("active") : r.status === "terminated" ? L("terminated") : L("suspended")}
        </span>
      ) },
  ];

  const stats = (rows: Employee[]): Stat[] => [
    { label: { ar: "الموظفون", en: "Employees" }, value: rows.length },
    { label: { ar: "مسجّلون بالتأمينات", en: "GOSI registered" },
      value: rows.filter((r) => r.is_gosi_registered).length, tone: "ok" },
    { label: { ar: "في حماية الأجور", en: "In WPS" },
      value: rows.filter((r) => r.include_in_wps).length, tone: "ok" },
    { label: { ar: "غير مسجّلين بقوى", en: "Not in MOL" },
      value: rows.filter((r) => !r.is_mol_registered).length, tone: "warn" },
  ];

  const filterBar = (
    <div className="row" style={{ gap: 6 }}>
      {STATUSES.map((s) => (
        <button
          key={s || "all"}
          className={`btn btn-sm ${status === s ? "btn-primary" : ""}`}
          onClick={() => setStatus(s)}
        >
          {L(s === "" ? "all" : s)}
        </button>
      ))}
    </div>
  );

  return (
    <div className="stack">
      <div>
        <h1>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".9rem", marginTop: 2 }}>
          {L("subtitle")}
        </div>
      </div>

      <DocList<Employee>
        endpoint="/employees/"
        filters={{ status }}
        columns={columns}
        rowKey={(r) => r.id}
        stats={stats}
        filterBar={filterBar}
        searchFields={(r) =>
          `${r.employee_no} ${r.name_ar} ${r.department} ${r.job_title}`}
        newHref="/employees/new"
        newLabel={{ ar: "موظف جديد", en: "New employee" }}
        onRowClick={(r) => router.push(`/employees/${r.id}`)}
        emptyHint={T.emptyHint}
      />
    </div>
  );
}
