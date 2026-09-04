"use client";

/**
 * هيكل التطبيق: قائمة جانبية فاتحة + شريط علوي.
 *
 * 🔑 حارس التوثيق: أي مسار بلا توكن يُحوَّل للدخول **بلا رسم
 * الهيكل** — فلا يرى المستخدم ومضة من واجهة لا يملكها.
 *
 * 🔑 الخيارات تختلف بالدور لا الشاشات (ق-53): الموظف يرى
 * قسائمه وطلباته، ومدير الموارد يرى كل شيء — من نفس المسارات.
 */
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";

import { apiGet, getToken, setToken, ApiError } from "@/lib/api";
import { loadPrefs, usePrefs, useT, type Dict } from "@/lib/prefs";
import {
  IcAlert, IcChart, IcClock, IcDoc, IcGlobe, IcHome, IcLeave, IcLogout,
  IcMenu, IcMoon, IcOrg, IcPayroll, IcSettings, IcSun, IcUser, IcUsers,
  IcWallet, IcX,
} from "@/components/Icons";
import NotificationBell from "@/components/NotificationBell";

const PUBLIC_PATHS = ["/login", "/accept-invitation", "/signup"];

const T: Dict = {
  home: { ar: "الرئيسية", en: "Home" },
  employees: { ar: "الموظفون", en: "Employees" },
  attendance: { ar: "الحضور والانصراف", en: "Attendance" },
  leaves: { ar: "الإجازات والطلبات", en: "Leaves & Requests" },
  team: { ar: "إدارة الفريق", en: "Team management" },
  teamMembers: { ar: "قائمة المرؤوسين", en: "Team members" },
  teamAttendance: { ar: "حضور المرؤوسين", en: "Team attendance" },
  teamRequests: { ar: "طلبات المرؤوسين", en: "Team requests" },
  teamAssign: { ar: "إسناد طلب", en: "Assign request" },
  payroll: { ar: "الرواتب", en: "Payroll" },
  reports: { ar: "التقارير", en: "Reports" },
  org: { ar: "الهيكل التنظيمي", en: "Organization" },
  myAttendance: { ar: "حضوري", en: "My Attendance" },
  myLeaves: { ar: "إجازاتي", en: "My Leaves" },
  myServices: { ar: "خدماتي", en: "My Services" },
  myTrack: { ar: "طلباتي", en: "My Requests" },
  myPayslips: { ar: "قسائم راتبي", en: "My Payslips" },
  myLetters: { ar: "خطاباتي", en: "My Letters" },
  myAccount: { ar: "حسابي", en: "My Account" },
  sites: { ar: "مواقع العمل", en: "Work Sites" },
  settings: { ar: "الإعدادات", en: "Settings" },
  subscription: { ar: "الاشتراك", en: "Subscription" },
  greeting: { ar: "مرحبًا، ", en: "Hi, " },
  logout: { ar: "تسجيل الخروج", en: "Sign out" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  readOnly: {
    ar: "الحساب للقراءة فقط — جدّد الاشتراك لاستعادة الوصول الكامل",
    en: "Account is read-only — renew to restore full access",
  },
  trialLeft: { ar: "تجربة مجانية — متبقٍ", en: "Free trial — remaining" },
  days: { ar: "يوم", en: "days" },
  renewSoon: { ar: "ينتهي اشتراكك خلال", en: "Subscription ends in" },
  renew: { ar: "تجديد", en: "Renew" },
};

type Workspace = {
  person: {
    display_name: string;
    first_name?: string;
    preferred_locale?: string;
  } | null;
  account: { name: string } | null;
  company: { name: string } | null;
  permissions: string[];
  /** نطاق كل صلاحية على حدة (ق-67) — الاستثناء الشخصي قد يوسّعه */
  permission_scopes?: Record<string, string>;
  roles?: { code: string; name_ar: string; scope: string }[];
  subscription?: {
    state: string;
    is_writable: boolean;
    days_left: number | null;
    renewal_alert: boolean;
    trial: { days_left: number | null } | null;
  };
};

type NavItem = {
  href: string;
  key: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  /** بنود فرعية تنطوي تحت هذا البند — قائمة قابلة للطيّ */
  children?: NavItem[];
  /**
   * أدنى نطاق يُظهر البند (ق-68).
   * "team" لإدارة الفريق — فالمشرف يصل لفريقه منها.
   * والافتراضي "department": البنود العامة لمدير الإدارة فما فوق.
   */
  minScope?: "team" | "department";
  /**
   * عدّاد أحمر على البند — ما ينتظر قرارك يُرى من القائمة بلا
   * فتح الشاشة. ويظهر على الأب أيضًا حين تُطوى القائمة.
   */
  badge?: "approvals";
  /** يظهر لمن يملك إحدى هذه الصلاحيات — فارغ يعني للجميع */
  perms?: string[];
  /**
   * ق-58: البند الإداري يحتاج نطاقًا أوسع من «نفسي».
   * الموظف يملك employees.view بنطاق own — فيرى نفسه فقط،
   * ولا معنى لعرض شاشة «الموظفون» له.
   */
  needsScope?: boolean;
};

const NAV: NavItem[] = [
  { href: "/", key: "home", icon: IcHome },

  // ── إدارية: تحتاج نطاقًا أوسع من «نفسي» (ق-58) ──
  { href: "/employees", key: "employees", icon: IcUsers,
    perms: ["employees.view"], needsScope: true },
  { href: "/attendance", key: "attendance", icon: IcClock,
    perms: ["attendance.view"], needsScope: true },
  { href: "/leaves", key: "leaves", icon: IcLeave,
    perms: ["leaves.view"], needsScope: true },
  // ق-68: إدارة الفريق — بنود المشرف مجموعة تحت عنوان واحد
  {
    href: "/team", key: "team", icon: IcUsers,
    perms: ["employees.view"], needsScope: true, minScope: "team",
    children: [
      { href: "/team/members", key: "teamMembers", icon: IcDoc,
        perms: ["employees.view"] },
      { href: "/team/attendance", key: "teamAttendance", icon: IcClock,
        perms: ["attendance.view"] },
      { href: "/team/requests", key: "teamRequests", icon: IcLeave,
        perms: ["requests.approve"], badge: "approvals" },
      { href: "/team/assign", key: "teamAssign", icon: IcDoc,
        perms: ["requests.manage"] },
    ],
  },
  { href: "/payroll", key: "payroll", icon: IcPayroll,
    perms: ["payroll.view"], needsScope: true },
  { href: "/reports", key: "reports", icon: IcChart,
    perms: ["payroll.view", "employees.view"], needsScope: true },
  // ق-68: مدير الإدارة يرى الهيكل، ويبدّل موقع عمل موظفيه من
  // المواقع المضافة — فيظهران له من نطاق إدارته
  { href: "/org", key: "org", icon: IcOrg,
    perms: ["org.view"], needsScope: true, minScope: "department" },
  { href: "/sites", key: "sites", icon: IcClock,
    perms: ["sites.view"] },

  // ── شخصية: لكل موظف عن نفسه ──
  { href: "/me/attendance", key: "myAttendance", icon: IcClock,
    perms: ["attendance.view"] },
  { href: "/me/leaves", key: "myLeaves", icon: IcLeave,
    perms: ["leaves.view", "requests.create"] },
  { href: "/me/requests", key: "myServices", icon: IcDoc,
    perms: ["requests.create"] },
  { href: "/me/track", key: "myTrack", icon: IcDoc,
    perms: ["requests.create"] },
  { href: "/me", key: "myPayslips", icon: IcPayroll,
    perms: ["payslips.view_own"] },
  { href: "/me/letters", key: "myLetters", icon: IcDoc,
    perms: ["requests.create"] },
  // ق-58: حسابي لكل مستخدم — صورته ولغته وكلمة مروره
  { href: "/me/account", key: "myAccount", icon: IcUser },
];

/** دائرة حمراء بعدد ما ينتظر قرارًا */
function Badge({ n }: { n: number }) {
  return (
    <span className="num" style={{
      minWidth: 19, height: 19, padding: "0 5px", borderRadius: 10,
      background: "var(--danger)", color: "#fff",
      fontSize: ".7rem", fontWeight: 700, flexShrink: 0,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      {n > 99 ? "99+" : n}
    </span>
  );
}


/** هل يحمل هذا البند أو أحد أبنائه عدّادًا؟ */
function hasBadge(item: NavItem): boolean {
  return item.badge === "approvals"
    || (item.children || []).some((c) => c.badge === "approvals");
}


export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { lang, theme, isRtl, toggleLang, setTheme } = usePrefs();
  const { L } = useT(T);

  const [ready, setReady] = useState(false);
  const [ws, setWs] = useState<Workspace | null>(null);
  /** ق-68: عدد ما ينتظر قرارك — يُحدَّث كل دقيقة */
  const [pendingCount, setPendingCount] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement | null>(null);
  /** أي المجموعات مفتوحة — والافتراضي مفتوحة إن كنا داخلها */
  const [openGroups, setOpenGroups] =
    useState<Record<string, boolean>>({});

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  useEffect(() => {
    loadPrefs();
  }, []);

  useEffect(() => {
    if (isPublic) {
      setReady(true);
      return;
    }
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    apiGet<Workspace>("/me/workspace/")
      .then((data) => {
        setWs(data);
        setReady(true);
      })
      .catch((e: ApiError) => {
        if (e.isAuth) {
          setToken(null);
          router.replace("/login");
        } else {
          setReady(true);
        }
      });
  }, [pathname, isPublic, router]);

  // الصفحات العامة بلا هيكل
  const perms = new Set(ws?.permissions ?? []);

  /**
   * ق-58: البند الإداري يحتاج نطاقًا أوسع من «نفسي».
   *
   * الموظف يملك employees.view بنطاق own — يرى نفسه فقط، فلا
   * معنى لعرض شاشة «الموظفون» أو «التقارير» له.
   */
  const SCOPE_RANK: Record<string, number> = {
    own: 0, team: 1, department: 2, branch: 3, company: 4, account: 5,
  };
  /**
   * ق-67: النطاق يُفحص لكل صلاحية على حدة لا لأوسع نطاق للمستخدم.
   *
   * فالموظف قد يُمنح صلاحية واحدة بنطاق أوسع من دوره باستثناء
   * شخصي — وفحص أوسع نطاق عام يحجب البند رغم المنح، فيبدو المنح
   * معطوبًا وهو يعمل.
   */
  const scopes: Record<string, string> = ws?.permission_scopes ?? {};

  /**
   * ق-68: البند الإداري لمن نطاقه أوسع من «فريقي».
   *
   * فالمشرف نطاقه team ويصل لفريقه من «إدارة الفريق» — وإظهار
   * «الموظفون» و«الحضور» له تكرار يشتّت. ومدير الإدارة فما فوق
   * (department وbranch وcompany وaccount) يرى البنود العامة.
   */
  const wideEnough = (perm: string, min: number) =>
    (SCOPE_RANK[scopes[perm]] ?? 0) >= min;

  const can = (item: NavItem) => {
    if (!item.perms) return true;
    const held = item.perms.filter((p) => perms.has(p));
    if (held.length === 0) return false;
    if (item.needsScope) {
      // ق-68: البند الإداري لمن نطاقه أوسع من إدارته.
      //
      // فالمشرف يصل لفريقه ومدير الإدارة لقسمه من «إدارة الفريق»،
      // وإظهار «الموظفون» و«الحضور» لهما تكرار يشتّت. والموارد
      // فما فوق (branch وcompany وaccount) يرون البنود العامة.
      const min = item.minScope === "team" ? 1
                : item.minScope === "department" ? 2
                : 3;
      return held.some((p) => wideEnough(p, min));
    }
    return true;
  };
  const nav = NAV.filter(can);

  /**
   * البند النشط = الأطول تطابقًا مع المسار.
   *
   * بلا هذا: /me يطابق /me/attendance و/me/leaves، فيُضاء
   * «قسائم راتبي» مع كل شاشة شخصية.
   */
  const activeHref = nav
    .filter((n) => n.href === "/"
      ? pathname === "/"
      : pathname === n.href || pathname.startsWith(n.href + "/"))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href ?? "";

  /**
   * حارس المسارات (ق-58).
   *
   * إخفاء البند من القائمة ليس حماية — من يعرف الرابط يفتحه
   * ويرى شاشة فارغة مربكة. فالمسار غير المصرّح يُعيد للرئيسية
   * بلا تنبيه، كأنه لم يكن.
   *
   * والخادم يحمي البيانات أصلًا — هذا يمنع الارتباك لا التسرّب.
   */
  // ق-68: ما ينتظر قرارك يُرى من القائمة بلا فتح الشاشة
  useEffect(() => {
    if (!ready || isPublic || !ws) return;
    // العدّاد يجمع ما ينتظر قرارك: الطلبات والتغييرات الوظيفية
    const load = () => {
      Promise.all([
        apiGet<unknown[]>("/me/approvals/").catch(() => []),
        apiGet<unknown[]>("/me/job-changes/").catch(() => []),
      ]).then(([a, b]) => setPendingCount(
        (Array.isArray(a) ? a.length : 0) + (Array.isArray(b) ? b.length : 0)
      )).catch(() => setPendingCount(0));
    };
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [ready, isPublic, ws]);

  useEffect(() => {
    if (!ready || isPublic || !ws) return;

    // ⚠️ الرئيسية لا تُفحص — وإلا صارت الحلقة لا نهائية.
    // وبند "/" يُستثنى من البحث لأن startsWith يطابقه دائمًا.
    if (pathname === "/") return;

    const item = NAV
      .filter((n) => n.href !== "/" &&
        (pathname === n.href || pathname.startsWith(n.href + "/")))
      .sort((a, b) => b.href.length - a.href.length)[0];

    if (item && !can(item)) {
      router.replace("/");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, pathname, ws]);

  /**
   * القائمة تُغلق بالنقر خارجها وبالانتقال لصفحة أخرى.
   *
   * فبقاؤها مفتوحة تحجب المحتوى، ومن ينتقل لا يقصد إبقاءها.
   */
  useEffect(() => {
    if (!accountOpen) return;
    const onDown = (e: MouseEvent) => {
      if (!accountRef.current?.contains(e.target as Node)) {
        setAccountOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [accountOpen]);

  useEffect(() => { setAccountOpen(false); }, [pathname]);

  if (isPublic) return <>{children}</>;

  // 🔑 لا يُرسم الهيكل قبل التحقق
  if (!ready) {
    return (
      <div style={{
        display: "grid", placeItems: "center", minHeight: "100vh",
        color: "var(--ink-3)",
      }}>
        {L("loading")}
      </div>
    );
  }




  const sub = ws?.subscription;
  const readOnly = sub && !sub.is_writable;

  const logout = () => {
    setToken(null);
    router.replace("/login");
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      {/* ══ القائمة الجانبية ══ */}
      <aside
        className="no-print"
        style={{
          width: "var(--sidebar-w)",
          background: "var(--paper)",
          borderInlineEnd: "1px solid var(--line)",
          position: "fixed",
          insetBlock: 0,
          insetInlineStart: 0,
          zIndex: 40,
          transform: menuOpen ? "none" : undefined,
          display: "flex",
          flexDirection: "column",
        }}
        data-open={menuOpen}
      >
        <div style={{
          height: "var(--topbar-h)", display: "flex", alignItems: "center",
          padding: "0 20px", borderBottom: "1px solid var(--line)",
          fontWeight: 600, fontSize: "1.05rem", color: "var(--teal)",
        }}>
          معتمد
          <span className="muted" style={{
            fontSize: ".78rem", fontWeight: 500, marginInlineStart: 8,
          }}>
            HR
          </span>
        </div>

        <nav style={{ padding: 12, flex: 1, overflowY: "auto" }}>
          {nav.map((item) => {
            const Icon = item.icon;
            const kids = (item.children ?? []).filter(can);

            // البند ذو الأبناء عنوان قابل للطيّ لا رابطًا:
            // النقر يفتح القائمة الفرعية بدل الانتقال لصفحة فارغة
            if (kids.length > 0) {
              const inside = pathname.startsWith(item.href);
              const open = openGroups[item.key] ?? inside;
              return (
                <div key={item.href} style={{ marginBottom: 2 }}>
                  <button
                    onClick={() => setOpenGroups((g) => ({
                      ...g, [item.key]: !open,
                    }))}
                    style={{
                      width: "100%", display: "flex", alignItems: "center",
                      gap: 11, padding: "9px 12px",
                      borderRadius: "var(--radius-sm)",
                      fontWeight: 500, font: "inherit", cursor: "pointer",
                      border: "none", textAlign: "start",
                      color: inside ? "var(--teal)" : "var(--ink-2)",
                      background: "transparent",
                    }}
                  >
                    <Icon size={19} />
                    <span style={{ flex: 1 }}>{L(item.key)}</span>
                    {hasBadge(item) && pendingCount > 0 && (
                      <Badge n={pendingCount} />
                    )}
                    <svg
                      width="15" height="15" viewBox="0 0 24 24"
                      fill="none" stroke="currentColor" strokeWidth="2.2"
                      strokeLinecap="round" strokeLinejoin="round"
                      style={{
                        opacity: .55, flexShrink: 0,
                        transform: open ? "rotate(180deg)" : "none",
                        transition: "transform .18s",
                      }}
                    >
                      <path d="M6 9l6 6 6-6" />
                    </svg>
                  </button>

                  {open && kids.map((kid) => {
                    const kidActive = kid.href === activeHref;
                    const KidIcon = kid.icon;
                    return (
                      <Link
                        key={kid.href}
                        href={kid.href}
                        onClick={() => setMenuOpen(false)}
                        style={{
                          display: "flex", alignItems: "center", gap: 9,
                          padding: "8px 12px",
                          marginInlineStart: 14, marginBottom: 2,
                          borderRadius: "var(--radius-sm)",
                          fontWeight: 500, fontSize: ".93rem",
                          color: kidActive ? "var(--teal)" : "var(--ink-3)",
                          background: kidActive
                            ? "var(--teal-soft)" : "transparent",
                        }}
                      >
                        <KidIcon size={16} />
                        <span style={{ flex: 1 }}>{L(kid.key)}</span>
                        {kid.badge === "approvals" && pendingCount > 0 && (
                          <Badge n={pendingCount} />
                        )}
                      </Link>
                    );
                  })}
                </div>
              );
            }

            const active = item.href === activeHref;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMenuOpen(false)}
                style={{
                  display: "flex", alignItems: "center", gap: 11,
                  padding: "9px 12px", borderRadius: "var(--radius-sm)",
                  marginBottom: 2, fontWeight: 500,
                  color: active ? "var(--teal)" : "var(--ink-2)",
                  background: active ? "var(--teal-soft)" : "transparent",
                }}
              >
                <Icon size={19} />
                <span style={{ flex: 1 }}>{L(item.key)}</span>
                {item.badge === "approvals" && pendingCount > 0 && (
                  <Badge n={pendingCount} />
                )}
              </Link>
            );
          })}
        </nav>

        {/* ق-58: إعدادات الشركة لمن يملك صلاحيتها — والموظف له «حسابي».
            ق-68: تُحجب عن المشرف، فهو لا يملك company.edit. */}
        {perms.has("company.edit") && (
          <div style={{ padding: 12, borderTop: "1px solid var(--line)" }}>
            <Link
              href="/settings"
              style={{
                display: "flex", alignItems: "center", gap: 11,
                padding: "9px 12px", borderRadius: "var(--radius-sm)",
                color: "var(--ink-2)", fontWeight: 500,
              }}
            >
              <IcSettings size={19} />
              {L("settings")}
            </Link>
          </div>
        )}
      </aside>

      {/* ══ المحتوى ══ */}
      <div style={{
        flex: 1,
        marginInlineStart: "var(--sidebar-w)",
        minWidth: 0,
      }}>
        {/* الشريط العلوي */}
        <header
          className="no-print"
          style={{
            height: "var(--topbar-h)",
            background: "var(--paper)",
            borderBottom: "1px solid var(--line)",
            position: "sticky", top: 0, zIndex: 30,
            display: "flex", alignItems: "center",
            padding: "0 20px", gap: 12,
          }}
        >
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setMenuOpen((v) => !v)}
            aria-label="menu"
            style={{ display: "none" }}
          >
            {menuOpen ? <IcX size={18} /> : <IcMenu size={18} />}
          </button>

          <div className="grow truncate muted" style={{ fontSize: ".9rem" }}>
            {ws?.company?.name || ws?.account?.name || ""}
          </div>

          {/* جرس الإشعارات — ما ينتظر انتباهك يُرى أينما كنت */}
          <NotificationBell />

          <button
            className="btn btn-ghost btn-sm"
            onClick={toggleLang}
            title={lang === "ar" ? "English" : "العربية"}
          >
            <IcGlobe size={17} />
            {lang === "ar" ? "EN" : "ع"}
          </button>

          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            title={theme === "dark" ? "نهاري" : "ليلي"}
          >
            {theme === "dark" ? <IcSun size={17} /> : <IcMoon size={17} />}
          </button>

          <div ref={accountRef} style={{ position: "relative" }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setAccountOpen((v) => !v)}
            >
              <IcUser size={17} />
              <span className="truncate" style={{ maxWidth: 190 }}>
                {ws?.person?.first_name
                  ? `${L("greeting")}${ws.person.first_name}`
                  : (ws?.person?.display_name || "—")}
              </span>
            </button>

            {accountOpen && (
              <div
                className="card"
                style={{
                  position: "absolute", insetInlineEnd: 0, top: "calc(100% + 6px)",
                  minWidth: 210, padding: 6, boxShadow: "var(--shadow-lg)",
                  zIndex: 50,
                }}
              >
                {/* بيانات مالية عن الحساب: مالك الحساب
                    والمدير العام ومدير الموارد */}
                {perms.has("account.view") && (
                <Link
                  href="/settings/subscription"
                  onClick={() => setAccountOpen(false)}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "9px 12px", borderRadius: "var(--radius-sm)",
                    color: "var(--ink-2)",
                  }}
                >
                  <IcWallet size={18} />
                  {L("subscription")}
                </Link>
                )}
                <button
                  onClick={logout}
                  className="btn btn-ghost"
                  style={{
                    width: "100%", justifyContent: "flex-start",
                    color: "var(--danger)",
                  }}
                >
                  <IcLogout size={18} />
                  {L("logout")}
                </button>
              </div>
            )}
          </div>
        </header>

        {/* شريط حالة الاشتراك — نحاسي لا أحمر */}
        {readOnly && (
          <div style={{
            background: "var(--copper-soft)", color: "var(--copper)",
            padding: "10px 20px", display: "flex", alignItems: "center",
            gap: 10, borderBottom: "1px solid var(--line)", fontWeight: 500,
          }}>
            <IcAlert size={18} />
            <span className="grow">{L("readOnly")}</span>
            <Link href="/settings/subscription" className="btn btn-sm">
              {L("renew")}
            </Link>
          </div>
        )}

        {!readOnly && sub?.trial?.days_left != null && (
          <div style={{
            background: "var(--teal-soft)", color: "var(--teal)",
            padding: "9px 20px", display: "flex", alignItems: "center",
            gap: 10, borderBottom: "1px solid var(--line)", fontWeight: 500,
          }}>
            <span className="grow">
              {L("trialLeft")}{" "}
              <span className="num">{sub.trial.days_left}</span> {L("days")}
            </span>
            <Link href="/settings/subscription" className="btn btn-sm btn-primary">
              {L("renew")}
            </Link>
          </div>
        )}

        {!readOnly && sub?.renewal_alert && sub.days_left != null && (
          <div style={{
            background: "var(--copper-soft)", color: "var(--copper)",
            padding: "9px 20px", display: "flex", alignItems: "center",
            gap: 10, borderBottom: "1px solid var(--line)", fontWeight: 500,
          }}>
            <IcAlert size={17} />
            <span className="grow">
              {L("renewSoon")} <span className="num">{sub.days_left}</span>{" "}
              {L("days")}
            </span>
            <Link href="/settings/subscription" className="btn btn-sm">
              {L("renew")}
            </Link>
          </div>
        )}

        {/* حاوية 1440 موسّطة */}
        <main style={{
          maxWidth: "var(--shell-max)", margin: "0 auto",
          padding: "24px 20px 48px", width: "100%",
        }}>
          {children}
        </main>
      </div>
    </div>
  );
}
