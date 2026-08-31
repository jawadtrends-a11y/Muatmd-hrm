"use client";

/**
 * هيكل لوحة المنصة (ق-51).
 *
 * القائمة تُفلتر بقدرات الدور: viewer يقرأ، support يفعّل ويمدّد،
 * owner كل شيء. والشريط الأحمر يظهر عند الانتحال فلا يُنسى السياق.
 */
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";

import { pGet, pPost, can, type PlatformUser } from "@/lib/api";
import { loadPrefs, usePrefs, useT, type Dict } from "@/lib/prefs";
import {
  IcAlert, IcChart, IcDoc, IcHome, IcLogout, IcMoon, IcSettings,
  IcSun, IcUser, IcUsers, IcWallet, IcX,
} from "@/components/Icons";

const PUBLIC = ["/login"];

const T: Dict = {
  dashboard: { ar: "المؤشرات", en: "Dashboard" },
  accounts: { ar: "الحسابات", en: "Accounts" },
  discounts: { ar: "الخصومات", en: "Discounts" },
  settings: { ar: "إعدادات المنصة", en: "Platform settings" },
  logout: { ar: "خروج", en: "Sign out" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  endImpersonation: { ar: "إنهاء الجلسة", en: "End session" },
  minutesLeft: { ar: "دقيقة متبقية", en: "min left" },
};

type NavItem = {
  href: string;
  key: string;
  icon: React.ComponentType<{ size?: number }>;
  cap: string;
};

const NAV: NavItem[] = [
  { href: "/", key: "dashboard", icon: IcHome, cap: "dashboard.view" },
  { href: "/accounts", key: "accounts", icon: IcUsers, cap: "accounts.view" },
  { href: "/discounts", key: "discounts", icon: IcWallet,
    cap: "discounts.manage" },
  { href: "/settings", key: "settings", icon: IcSettings,
    cap: "platform.settings" },
];

export default function AdminShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, setTheme } = usePrefs();
  const { L } = useT(T);

  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<PlatformUser | null>(null);

  const isPublic = PUBLIC.some((p) => pathname.startsWith(p));

  useEffect(() => {
    loadPrefs();
  }, []);

  useEffect(() => {
    if (isPublic) {
      setReady(true);
      return;
    }
    pGet<PlatformUser>("/platform/auth/me")
      .then((u) => { setUser(u); setReady(true); })
      .catch(() => router.replace("/login"));
  }, [pathname, isPublic, router]);

  if (isPublic) return <>{children}</>;

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

  const nav = NAV.filter((n) => can(user, n.cap));
  const imp = user?.impersonating;

  async function logout() {
    await pPost("/platform/auth/logout").catch(() => {});
    router.replace("/login");
  }

  async function endImpersonation() {
    await pPost("/platform/impersonate/end").catch(() => {});
    location.reload();
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <aside style={{
        width: "var(--sidebar-w)", background: "var(--paper)",
        borderInlineEnd: "1px solid var(--line)",
        position: "fixed", insetBlock: 0, insetInlineStart: 0,
        display: "flex", flexDirection: "column", zIndex: 40,
      }}>
        <div style={{
          height: "var(--topbar-h)", display: "flex", alignItems: "center",
          padding: "0 20px", borderBottom: "1px solid var(--line)",
          fontWeight: 600, color: "var(--teal)",
        }}>
          لوحة معتمد
        </div>

        <nav style={{ padding: 12, flex: 1 }}>
          {nav.map((item) => {
            const active = item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} style={{
                display: "flex", alignItems: "center", gap: 11,
                padding: "9px 12px", borderRadius: "var(--radius-sm)",
                marginBottom: 2, fontWeight: 500,
                color: active ? "var(--teal)" : "var(--ink-2)",
                background: active ? "var(--teal-soft)" : "transparent",
              }}>
                <Icon size={19} />
                {L(item.key)}
              </Link>
            );
          })}
        </nav>

        <div style={{
          padding: 14, borderTop: "1px solid var(--line)",
          fontSize: ".85rem",
        }}>
          <div style={{ fontWeight: 500 }}>{user?.full_name}</div>
          <div className="muted" style={{ fontSize: ".8rem" }}>
            {user?.role_label}
          </div>
        </div>
      </aside>

      <div style={{
        flex: 1, marginInlineStart: "var(--sidebar-w)", minWidth: 0,
      }}>
        {/* ══ الشريط الأحمر — الانتحال (ق-46) ══ */}
        {imp?.active && (
          <div style={{
            background: "var(--danger)", color: "#fff",
            padding: "10px 20px", display: "flex", alignItems: "center",
            gap: 12, fontWeight: 500, position: "sticky", top: 0, zIndex: 50,
          }}>
            <IcAlert size={19} />
            <div className="grow">
              <div>{imp.message}</div>
              <div style={{ fontSize: ".82rem", opacity: .9 }}>
                {imp.warning}
              </div>
            </div>
            <span style={{ fontSize: ".85rem", whiteSpace: "nowrap" }}>
              <span className="num">{imp.minutes_left}</span> {L("minutesLeft")}
            </span>
            <button className="btn btn-sm" onClick={endImpersonation}>
              <IcX size={15} />
              {L("endImpersonation")}
            </button>
          </div>
        )}

        <header style={{
          height: "var(--topbar-h)", background: "var(--paper)",
          borderBottom: "1px solid var(--line)",
          display: "flex", alignItems: "center", padding: "0 20px", gap: 12,
        }}>
          <div className="grow" />
          <button className="btn btn-ghost btn-sm"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? <IcSun size={17} /> : <IcMoon size={17} />}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={logout}
            style={{ color: "var(--danger)" }}>
            <IcLogout size={17} />
            {L("logout")}
          </button>
        </header>

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
