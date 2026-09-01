"use client";

/**
 * الصفحة الرئيسية — تختلف بالدور (ق-54).
 *
 * الموظف العادي يرى بياناته الشخصية، والمدير يرى ما ينتظره
 * وحالة المسير والحضور.
 */
import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import PunchCard from "@/components/PunchCard";
import {
  IcAlert, IcCheck, IcClock, IcDoc, IcLeave, IcPayroll, IcUser,
  IcUsers, IcWallet, IcX,
} from "@/components/Icons";

const T: Dict = {
  welcome: { ar: "مرحبًا", en: "Welcome" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  // بطاقة الموظف
  myProfile: { ar: "ملفي الوظيفي", en: "My profile" },
  employeeNo: { ar: "الرقم الوظيفي", en: "Employee No." },
  department: { ar: "القسم", en: "Department" },
  jobTitle: { ar: "المسمى", en: "Job title" },
  manager: { ar: "مديري المباشر", en: "My manager" },
  branch: { ar: "الفرع", en: "Branch" },
  joinDate: { ar: "تاريخ المباشرة", en: "Joined" },
  serviceLength: { ar: "مدة الخدمة", en: "Service" },
  years: { ar: "سنة", en: "y" },
  months: { ar: "شهرًا", en: "m" },
  probation: { ar: "تحت التجربة حتى", en: "Probation until" },
  // الراتب
  mySalary: { ar: "راتبي", en: "My salary" },
  gross: { ar: "الإجمالي", en: "Gross" },
  bank: { ar: "البنك", en: "Bank" },
  iban: { ar: "الآيبان", en: "IBAN" },
  // التسجيل
  registration: { ar: "تسجيلي النظامي", en: "Registration" },
  gosi: { ar: "التأمينات", en: "GOSI" },
  mol: { ar: "قوى", en: "MOL" },
  wps: { ar: "حماية الأجور", en: "WPS" },
  registered: { ar: "مسجّل", en: "Yes" },
  notRegistered: { ar: "غير مسجّل", en: "No" },
  // الوثائق
  myDocs: { ar: "وثائقي", en: "My documents" },
  expiresIn: { ar: "تنتهي خلال", en: "Expires in" },
  days: { ar: "يوم", en: "days" },
  expired: { ar: "منتهية", en: "Expired" },
  // الالتزامات
  obligations: { ar: "التزاماتي", en: "My obligations" },
  advances: { ar: "سلف قائمة", en: "Advances" },
  assets: { ar: "عهد", en: "Assets" },
  // الروابط
  requestSomething: { ar: "تقديم طلب", en: "Submit a request" },
  myLeaves: { ar: "إجازاتي", en: "My leaves" },
  myPayslips: { ar: "قسائم راتبي", en: "My payslips" },
  // المدير
  awaiting: { ar: "بانتظار قرارك", en: "Awaiting you" },
  requests: { ar: "طلب", en: "requests" },
  review: { ar: "مراجعة", en: "Review" },
  presentToday: { ar: "حاضرون اليوم", en: "Present today" },
  lastRun: { ar: "آخر مسير", en: "Latest run" },
  open: { ar: "فتح", en: "Open" },
  noProfile: {
    ar: "لا ملف موظف مرتبط بحسابك — راجع مدير الموارد البشرية",
    en: "No employee profile linked to your account",
  },
};

type Profile = {
  employee: {
    employee_no: string; name_ar: string; department: string;
    branch: string; job_title: string; manager: string;
    status_label: string;
  };
  service: {
    join_date: string; years: number; months: number;
    in_probation: boolean; probation_end: string | null;
  };
  salary: {
    gross: string; bank: string; iban: string;
    lines: { component: string; amount: string }[];
  };
  registration: { gosi: boolean; mol: boolean; wps: boolean };
  documents: {
    type: string; expiry_date: string; days_left: number; severity: string;
  }[];
  obligations: {
    advances_outstanding: string; advances_count: number;
    assets_count: number; assets_value: string;
  };
};

type Approval = { id: number };
type Run = {
  id: number; period: string; total_net: string; status_label: string;
};
type Board = { total: number; counts: Record<string, number> };

function money(v: string) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                  maximumFractionDigits: 2 })
    : v;
}


/* ══ صف بيان — خارج المكوّن الرئيسي ══ */

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="spread" style={{
      padding: "8px 0", borderBottom: "1px solid var(--line)",
    }}>
      <span className="muted" style={{ fontSize: ".86rem" }}>{label}</span>
      <span style={{ fontWeight: 500 }}>{value || "—"}</span>
    </div>
  );
}

/* ══ لوحة الموظف ══ */

function EmployeeHome({
  p, L,
}: {
  p: Profile;
  L: (k: string, f?: string) => string;
}) {
  const e = p.employee;
  const flag = (on: boolean) => (
    <span className={on ? "badge badge-ok" : "badge badge-warn"}>
      {on ? L("registered") : L("notRegistered")}
    </span>
  );

  const tone = (sev: string) =>
    sev === "منتهية" ? "badge-danger"
      : sev === "حرجة" ? "badge-warn"
      : sev === "قريبة" ? "badge-warn" : "badge";

  return (
    <div className="stack">
      {/* الوثائق المنتهية — أعلى الشاشة إن وُجدت */}
      {p.documents.some((d) => d.days_left <= 14) && (
        <div style={{
          background: "var(--copper-soft)", color: "var(--copper)",
          padding: "12px 15px", borderRadius: "var(--radius-sm)",
          fontWeight: 500,
        }}>
          <div className="row" style={{ marginBottom: 6 }}>
            <IcAlert size={18} />
            {L("myDocs")}
          </div>
          {p.documents.filter((d) => d.days_left <= 14).map((d, i) => (
            <div key={i} style={{ fontSize: ".9rem" }}>
              • {d.type} —{" "}
              {d.days_left < 0 ? L("expired") : (
                <>
                  {L("expiresIn")} <span className="num">{d.days_left}</span>{" "}
                  {L("days")}
                </>
              )}
            </div>
          ))}
        </div>
      )}

      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
        gap: 16,
      }}>
        {/* الملف الوظيفي */}
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ marginBottom: 10 }}>
            <IcUser size={19} />
            <h2 style={{ fontSize: "1rem" }}>{L("myProfile")}</h2>
          </div>
          <Row label={L("employeeNo")}
            value={<span className="num">{e.employee_no}</span>} />
          <Row label={L("department")} value={e.department} />
          <Row label={L("jobTitle")} value={e.job_title} />
          <Row label={L("branch")} value={e.branch} />
          <Row label={L("manager")} value={e.manager} />
          <Row label={L("joinDate")}
            value={<span className="num">{p.service.join_date}</span>} />
          <Row label={L("serviceLength")} value={
            <>
              <span className="num">{p.service.years}</span> {L("years")}{" "}
              <span className="num">{p.service.months}</span> {L("months")}
            </>
          } />
          {p.service.in_probation && p.service.probation_end && (
            <Row label={L("probation")} value={
              <span className="badge badge-warn">
                <span className="num">{p.service.probation_end}</span>
              </span>
            } />
          )}
        </div>

        {/* الراتب */}
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ marginBottom: 10 }}>
            <IcPayroll size={19} />
            <h2 style={{ fontSize: "1rem" }}>{L("mySalary")}</h2>
          </div>

          <div style={{
            fontSize: "1.6rem", fontWeight: 600, color: "var(--teal)",
            marginBottom: 12,
          }}>
            <span className="num">{money(p.salary.gross)}</span>
          </div>

          {p.salary.lines.map((l, i) => (
            <Row key={i} label={l.component}
              value={<span className="num">{money(l.amount)}</span>} />
          ))}

          <Row label={L("bank")} value={p.salary.bank} />
          <Row label={L("iban")} value={
            <span className="num" style={{ fontSize: ".85rem" }}>
              {p.salary.iban || "—"}
            </span>
          } />
        </div>

        {/* التسجيل والالتزامات */}
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ marginBottom: 10 }}>
            <IcCheck size={19} />
            <h2 style={{ fontSize: "1rem" }}>{L("registration")}</h2>
          </div>
          <Row label={L("gosi")} value={flag(p.registration.gosi)} />
          <Row label={L("mol")} value={flag(p.registration.mol)} />
          <Row label={L("wps")} value={flag(p.registration.wps)} />

          {(p.obligations.advances_count > 0 ||
            p.obligations.assets_count > 0) && (
            <>
              <div className="row" style={{ marginTop: 16, marginBottom: 8 }}>
                <IcWallet size={18} />
                <h3 style={{ fontSize: ".95rem" }}>{L("obligations")}</h3>
              </div>
              {p.obligations.advances_count > 0 && (
                <Row label={L("advances")} value={
                  <span className="num" style={{ color: "var(--danger)" }}>
                    {money(p.obligations.advances_outstanding)}
                  </span>
                } />
              )}
              {p.obligations.assets_count > 0 && (
                <Row label={L("assets")} value={
                  <>
                    <span className="num">{p.obligations.assets_count}</span>
                    {" · "}
                    <span className="num">
                      {money(p.obligations.assets_value)}
                    </span>
                  </>
                } />
              )}
            </>
          )}
        </div>
      </div>

      {/* روابط سريعة */}
      <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
        <Link href="/me/requests" className="btn btn-primary">
          <IcDoc size={17} />
          {L("requestSomething")}
        </Link>
        <Link href="/me/leaves" className="btn">
          <IcLeave size={17} />
          {L("myLeaves")}
        </Link>
        <Link href="/me" className="btn">
          <IcPayroll size={17} />
          {L("myPayslips")}
        </Link>
      </div>
    </div>
  );
}


/* ══ لوحة المدير ══ */

function ManagerHome({
  approvals, run, board, L,
}: {
  approvals: Approval[];
  run: Run | null;
  board: Board | null;
  L: (k: string, f?: string) => string;
}) {
  return (
    <div className="stack">
      {approvals.length > 0 && (
        <Link href="/leaves" className="card" style={{
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
    </div>
  );
}

/* ══ الشاشة ══ */

export default function HomePage() {
  const { L } = useT(T);

  const [profile, setProfile] = useState<Profile | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [board, setBoard] = useState<Board | null>(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    const year = new Date().getFullYear();
    Promise.all([
      apiGet<Profile>("/me/profile/").catch(() => null),
      apiGet<Approval[]>("/me/approvals/").catch(() => [] as Approval[]),
      apiGet<Run[]>(`/payroll/runs/?year=${year}`).catch(() => [] as Run[]),
      apiGet<Board>("/attendance/daily/").catch(() => null),
    ]).then(([p, a, runs, b]) => {
      setProfile(p);
      setApprovals(a);
      setRun(runs.length > 0 ? runs[0] : null);
      setBoard(b);
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

  const isManager = board !== null || run !== null || approvals.length > 0;

  return (
    <div className="stack">
      <h1>
        {L("welcome")}
        {profile?.employee?.name_ar ? `، ${profile.employee.name_ar}` : ""}
      </h1>

      {/* ق-62: البصمة أول ما يراه الموظف — زرّان لا أكثر */}
      <PunchCard />

      {isManager && (
        <ManagerHome approvals={approvals} run={run} board={board} L={L} />
      )}

      {profile ? (
        <EmployeeHome p={profile} L={L} />
      ) : !isManager ? (
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
