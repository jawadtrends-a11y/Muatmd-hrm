"use client";

/**
 * الصفحة الرئيسية — تجمع ما ينتظر المستخدم.
 *
 * تعرض حسب الصلاحية: ما ينتظر اعتماده، وحالة آخر مسير،
 * والوثائق المنتهية، ورصيده الشخصي.
 */
import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import {
  IcAlert, IcClock, IcDoc, IcLeave, IcPayroll, IcUsers,
} from "@/components/Icons";

const T: Dict = {
  welcome: { ar: "مرحبًا", en: "Welcome" },
  awaiting: { ar: "بانتظار قرارك", en: "Awaiting your decision" },
  requests: { ar: "طلب", en: "requests" },
  review: { ar: "مراجعة", en: "Review" },
  lastRun: { ar: "آخر مسير", en: "Latest payroll run" },
  noRun: { ar: "لا مسير هذا الشهر", en: "No run this month" },
  createRun: { ar: "إنشاء مسير", en: "Create run" },
  openRun: { ar: "فتح", en: "Open" },
  expiring: { ar: "وثائق تنتهي قريبًا", en: "Documents expiring" },
  expired: { ar: "منتهية", en: "Expired" },
  critical: { ar: "حرجة", en: "Critical" },
  viewAll: { ar: "عرض الكل", en: "View all" },
  employees: { ar: "الموظفون", en: "Employees" },
  present: { ar: "حاضرون اليوم", en: "Present today" },
  myBalance: { ar: "رصيد إجازاتي", en: "My leave balance" },
  days: { ar: "يوم", en: "days" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  quickLinks: { ar: "روابط سريعة", en: "Quick links" },
  attendance: { ar: "الحضور", en: "Attendance" },
  leaves: { ar: "الإجازات", en: "Leaves" },
  payroll: { ar: "الرواتب", en: "Payroll" },
  reports: { ar: "التقارير", en: "Reports" },
  myServices: { ar: "خدماتي", en: "My services" },
};

type Workspace = {
  user?: { username: string };
  account?: { name_ar: string };
  active_company?: { name_ar: string };
  permissions: string[];
};

type Approval = { id: number };
type Run = {
  id: number;
  run_no: string;
  period: string;
  status: string;
  status_label: string;
  employee_count: number;
  total_net: string;
  variance_count: number;
};
type ExpiringDocs = {
  total: number;
  by_severity: Record<string, number>;
};
type DailyBoard = { total: number; counts: Record<string, number> };
type MyLeaves = { balances: { name_ar: string; available: string }[] };

function money(v: string) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                  maximumFractionDigits: 2 })
    : v;
}

export default function HomePage() {
  const { L } = useT(T);

  const [ws, setWs] = useState<Workspace | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [docs, setDocs] = useState<ExpiringDocs | null>(null);
  const [board, setBoard] = useState<DailyBoard | null>(null);
  const [leaves, setLeaves] = useState<MyLeaves | null>(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    const year = new Date().getFullYear();
    Promise.all([
      apiGet<Workspace>("/me/workspace/").catch(() => null),
      apiGet<Approval[]>("/me/approvals/").catch(() => []),
      apiGet<Run[]>(`/payroll/runs/?year=${year}`).catch(() => []),
      apiGet<ExpiringDocs>("/documents/expiring/?within_days=60")
        .catch(() => null),
      apiGet<DailyBoard>("/attendance/daily/").catch(() => null),
      apiGet<MyLeaves>("/me/leaves/").catch(() => null),
    ]).then(([w, a, runs, d, b, l]) => {
      setWs(w);
      setApprovals(a);
      setRun(runs.length > 0 ? runs[0] : null);
      setDocs(d);
      setBoard(b);
      setLeaves(l);
      setBusy(false);
    });
  }, []);

  if (busy) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("loading")}
      </div>
    );
  }

  const name = ws?.user?.username || "";
  const expiredCount = docs?.by_severity?.["منتهية"] ?? 0;
  const criticalCount = docs?.by_severity?.["حرجة"] ?? 0;
  const presentToday = board?.counts?.present ?? 0;

  return (
    <div className="stack">
      <div>
        <h1>
          {L("welcome")}
          {name ? `، ${name}` : ""}
        </h1>
        <div className="muted" style={{ fontSize: ".9rem", marginTop: 2 }}>
          {ws?.active_company?.name_ar || ws?.account?.name_ar || ""}
        </div>
      </div>

      {/* ══ بانتظار قرارك ══ */}
      {approvals.length > 0 && (
        <Link href="/leaves" className="card" style={{
          padding: 18, display: "block",
          borderInlineStartWidth: 4,
          borderInlineStartColor: "var(--copper)",
        }}>
          <div className="spread">
            <div className="row">
              <IcAlert size={20} className="" />
              <div>
                <div style={{ fontWeight: 600, color: "var(--copper)" }}>
                  {L("awaiting")}
                </div>
                <div className="muted" style={{ fontSize: ".88rem" }}>
                  <span className="num">{approvals.length}</span>{" "}
                  {L("requests")}
                </div>
              </div>
            </div>
            <span className="btn btn-sm">{L("review")}</span>
          </div>
        </Link>
      )}

      {/* ══ البطاقات ══ */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
        gap: 14,
      }}>
        {/* آخر مسير */}
        {run !== null && (
          <div className="card" style={{ padding: 18 }}>
            <div className="row" style={{ marginBottom: 10 }}>
              <IcPayroll size={19} />
              <span className="muted" style={{ fontSize: ".85rem" }}>
                {L("lastRun")}
              </span>
            </div>
            <div style={{ fontSize: "1.3rem", fontWeight: 600 }}>
              <span className="num">{money(run.total_net)}</span>
            </div>
            <div className="spread" style={{ marginTop: 8 }}>
              <span className="muted" style={{ fontSize: ".85rem" }}>
                <span className="num">{run.period}</span> ·{" "}
                <span className="num">{run.employee_count}</span>
              </span>
              <span className="badge">{run.status_label}</span>
            </div>
            <Link href={`/payroll/${run.id}`} className="btn btn-sm"
              style={{ marginTop: 12, width: "100%" }}>
              {L("openRun")}
            </Link>
          </div>
        )}

        {/* الحضور اليوم */}
        {board && (
          <div className="card" style={{ padding: 18 }}>
            <div className="row" style={{ marginBottom: 10 }}>
              <IcClock size={19} />
              <span className="muted" style={{ fontSize: ".85rem" }}>
                {L("present")}
              </span>
            </div>
            <div style={{ fontSize: "1.6rem", fontWeight: 600,
                          color: "var(--ok)" }}>
              <span className="num">{presentToday}</span>
              <span className="muted" style={{
                fontSize: "1rem", fontWeight: 500,
              }}>
                {" / "}
                <span className="num">{board.total}</span>
              </span>
            </div>
            <Link href="/attendance" className="btn btn-sm"
              style={{ marginTop: 12, width: "100%" }}>
              {L("attendance")}
            </Link>
          </div>
        )}

        {/* الوثائق */}
        {docs && docs.total > 0 && (
          <div className="card" style={{
            padding: 18,
            borderInlineStartWidth: expiredCount > 0 ? 4 : 1,
            borderInlineStartColor: expiredCount > 0
              ? "var(--danger)" : "var(--line)",
          }}>
            <div className="row" style={{ marginBottom: 10 }}>
              <IcDoc size={19} />
              <span className="muted" style={{ fontSize: ".85rem" }}>
                {L("expiring")}
              </span>
            </div>
            <div className="row" style={{ gap: 8 }}>
              {expiredCount > 0 && (
                <span className="badge badge-danger">
                  <span className="num">{expiredCount}</span> {L("expired")}
                </span>
              )}
              {criticalCount > 0 && (
                <span className="badge badge-warn">
                  <span className="num">{criticalCount}</span> {L("critical")}
                </span>
              )}
            </div>
            <Link href="/reports" className="btn btn-sm"
              style={{ marginTop: 12, width: "100%" }}>
              {L("viewAll")}
            </Link>
          </div>
        )}

        {/* رصيدي */}
        {leaves && leaves.balances.length > 0 && (
          <div className="card" style={{ padding: 18 }}>
            <div className="row" style={{ marginBottom: 10 }}>
              <IcLeave size={19} />
              <span className="muted" style={{ fontSize: ".85rem" }}>
                {L("myBalance")}
              </span>
            </div>
            {leaves.balances.slice(0, 2).map((b) => (
              <div key={b.name_ar} className="spread"
                style={{ marginBottom: 4 }}>
                <span style={{ fontSize: ".9rem" }}>{b.name_ar}</span>
                <span style={{ fontWeight: 600 }}>
                  <span className="num">{b.available}</span>
                  <span className="muted" style={{ fontSize: ".8rem" }}>
                    {" "}{L("days")}
                  </span>
                </span>
              </div>
            ))}
            <Link href="/me" className="btn btn-sm"
              style={{ marginTop: 10, width: "100%" }}>
              {L("myServices")}
            </Link>
          </div>
        )}
      </div>

      {/* ══ روابط سريعة ══ */}
      <div className="card" style={{ padding: 18 }}>
        <div className="muted" style={{ fontSize: ".85rem", marginBottom: 12 }}>
          {L("quickLinks")}
        </div>
        <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
          <Link href="/employees" className="btn btn-sm">
            <IcUsers size={16} /> {L("employees")}
          </Link>
          <Link href="/attendance" className="btn btn-sm">
            <IcClock size={16} /> {L("attendance")}
          </Link>
          <Link href="/leaves" className="btn btn-sm">
            <IcLeave size={16} /> {L("leaves")}
          </Link>
          <Link href="/payroll" className="btn btn-sm">
            <IcPayroll size={16} /> {L("payroll")}
          </Link>
          <Link href="/reports" className="btn btn-sm">
            <IcDoc size={16} /> {L("reports")}
          </Link>
        </div>
      </div>
    </div>
  );
}
