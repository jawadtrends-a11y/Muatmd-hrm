"use client";

/**
 * الصفحة الرئيسية (ق-65).
 *
 *   الموظف العادي → **ملفه الكامل** بتبويباته مباشرةً
 *   المدير        → لوحته الإدارية + ملفه
 *
 * فلا زر «ملفي الكامل» ولا انتقال — الملف هو الشاشة.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiGet } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import PunchCard from "@/components/PunchCard";
import EmployeeProfileView from "@/components/EmployeeProfileView";
import {
  IcAlert, IcClock, IcPayroll, IcUser,
} from "@/components/Icons";

const T: Dict = {
  welcome: { ar: "مرحبًا", en: "Welcome" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  awaiting: { ar: "بانتظار قرارك", en: "Awaiting you" },
  requests: { ar: "طلب", en: "requests" },
  delegAwaiting: { ar: "إنابة تنتظر قرارك", en: "Delegation awaiting you" },
  delegCount: { ar: "طلب إنابة", en: "delegation requests" },
  review: { ar: "مراجعة", en: "Review" },
  presentToday: { ar: "حاضرون اليوم", en: "Present today" },
  lastRun: { ar: "آخر مسير", en: "Latest run" },
  open: { ar: "فتح", en: "Open" },
  noProfile: {
    ar: "لا ملف موظف مرتبط بحسابك — راجع مدير الموارد البشرية",
    en: "No employee profile linked to your account",
  },
};

type Approval = { id: number };
type Run = {
  id: number; period: string; total_net: string; status_label: string;
};
type Board = { total: number; counts: Record<string, number> };
type Ws = { permissions: string[]; roles?: { scope: string }[] };

function money(v: string) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                  maximumFractionDigits: 2 })
    : v;
}

export default function HomePage() {
  const { L } = useT(T);

  const [ws, setWs] = useState<Ws | null>(null);
  const [empId, setEmpId] = useState<number | null>(null);
  const [name, setName] = useState("");
  /** ق-75: إنابات تنتظر قراري — تخصّ كل موظف لا الإداري وحده */
  const [delegCount, setDelegCount] = useState(0);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [board, setBoard] = useState<Board | null>(null);
  const [busy, setBusy] = useState(true);
  const [noProfile, setNoProfile] = useState(false);

  useEffect(() => {
    apiGet<Ws>("/me/workspace/")
      .then(setWs)
      .catch(() => setWs({ permissions: [] }));
  }, []);

  /**
   * ق-68: شاشة الإجازات العامة محجوبة عن المشرف — يصل لطلبات فريقه
   * من «إدارة الفريق». فالزر يوجّه لما يملكه فعلًا، وإلا أعاده
   * حارس المسارات للرئيسية من حيث جاء.
   */
  const approvalsHref = (ws?.roles ?? []).some(
    (r) => r.scope !== "own" && r.scope !== "team")
    ? "/leaves" : "/team/requests";

  useEffect(() => {
    if (!ws) return;

    const perms = new Set(ws.permissions ?? []);
    const isAdmin = (ws.roles ?? []).some((r) => r.scope !== "own");

    // ق-75: إنابات تنتظر قراري — تخصّ كل موظف لا الإداري وحده
    apiGet<{ incoming: { status: string }[] }>("/me/delegations/")
      .then((d) => setDelegCount(
        (d.incoming || []).filter((x) => x.status === "pending").length))
      .catch(() => setDelegCount(0));

    const year = new Date().getFullYear();

    Promise.all([
      apiGet<{ employee: { employment_id: number; name_ar: string } }>(
        "/me/profile/").catch(() => null),
      isAdmin
        ? apiGet<Approval[]>("/me/approvals/").catch(() => [] as Approval[])
        : Promise.resolve([] as Approval[]),
      isAdmin && perms.has("payroll.view")
        ? apiGet<Run[]>(`/payroll/runs/?year=${year}`).catch(() => [] as Run[])
        : Promise.resolve([] as Run[]),
      isAdmin && perms.has("attendance.view")
        ? apiGet<Board>("/attendance/daily/").catch(() => null)
        : Promise.resolve(null),
    ]).then(([me, a, runs, b]) => {
      if (me?.employee) {
        setEmpId(me.employee.employment_id);
        setName(me.employee.name_ar);
      } else {
        setNoProfile(true);
      }
      setApprovals(a);
      setRun(runs.length > 0 ? runs[0] : null);
      setBoard(b);
      setBusy(false);
    });
  }, [ws]);

  if (busy) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("loading")}
      </div>
    );
  }

  const isAdmin = (ws?.roles ?? []).some((r) => r.scope !== "own");

  return (
    <div className="stack">
      <h1>
        {L("welcome")}{name ? `، ${name}` : ""}
      </h1>

      {/* البصمة — أول ما يحتاجه يوميًا */}
      <PunchCard />

      {/* ق-75: إنابة تنتظر قرارك — لكل موظف لا الإداري وحده */}
      {delegCount > 0 && (
        <Link href="/me/track" className="card" style={{
          padding: 18, display: "block",
          borderInlineStartWidth: 4,
          borderInlineStartColor: "var(--teal)",
        }}>
          <div className="spread">
            <div className="row">
              <IcAlert size={20} />
              <div>
                <div style={{ fontWeight: 600, color: "var(--teal)" }}>
                  {L("delegAwaiting")}
                </div>
                <div className="muted" style={{ fontSize: ".88rem" }}>
                  <span className="num">{delegCount}</span>{" "}
                  {L("delegCount")}
                </div>
              </div>
            </div>
            <span className="btn btn-sm">{L("review")}</span>
          </div>
        </Link>
      )}

      {/* لوحة المدير */}
      {isAdmin && (
        <>
          {approvals.length > 0 && (
            <Link href={approvalsHref} className="card" style={{
              padding: 18, display: "block",
              borderInlineStartWidth: 4,
              borderInlineStartColor: "var(--copper)",
            }}>
              <div className="spread">
                <div className="row">
                  <IcAlert size={20} />
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

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: 14,
          }}>
            {board && (
              <div className="card" style={{ padding: 18 }}>
                <div className="row" style={{ marginBottom: 8 }}>
                  <IcClock size={18} />
                  <span className="muted" style={{ fontSize: ".85rem" }}>
                    {L("presentToday")}
                  </span>
                </div>
                <div style={{ fontSize: "1.6rem", fontWeight: 600,
                              color: "var(--ok)" }}>
                  <span className="num">{board.counts?.present ?? 0}</span>
                  <span className="muted" style={{ fontSize: "1rem" }}>
                    {" / "}<span className="num">{board.total}</span>
                  </span>
                </div>
                <Link href="/attendance" className="btn btn-sm"
                  style={{ marginTop: 12, width: "100%" }}>
                  {L("open")}
                </Link>
              </div>
            )}

            {run && (
              <div className="card" style={{ padding: 18 }}>
                <div className="row" style={{ marginBottom: 8 }}>
                  <IcPayroll size={18} />
                  <span className="muted" style={{ fontSize: ".85rem" }}>
                    {L("lastRun")}
                  </span>
                </div>
                <div style={{ fontSize: "1.35rem", fontWeight: 600 }}>
                  <span className="num">{money(run.total_net)}</span>
                </div>
                <div className="spread" style={{ marginTop: 6 }}>
                  <span className="muted" style={{ fontSize: ".85rem" }}>
                    <span className="num">{run.period}</span>
                  </span>
                  <span className="badge">{run.status_label}</span>
                </div>
                <Link href={`/payroll/${run.id}`} className="btn btn-sm"
                  style={{ marginTop: 12, width: "100%" }}>
                  {L("open")}
                </Link>
              </div>
            )}
          </div>
        </>
      )}

      {/* الملف الكامل — لا زر ولا انتقال */}
      {empId ? (
        <EmployeeProfileView employmentId={empId} />
      ) : noProfile ? (
        <div className="card" style={{
          padding: 32, textAlign: "center", color: "var(--copper)",
        }}>
          <IcAlert size={22} />
          <div style={{ marginTop: 8 }}>{L("noProfile")}</div>
        </div>
      ) : null}
    </div>
  );
}
