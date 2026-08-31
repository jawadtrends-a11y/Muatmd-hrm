"use client";

/** مؤشرات المنصة — الشاشة الأولى للسوبر أدمن. */
import { useEffect, useState } from "react";
import Link from "next/link";

import { pGet } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcUsers, IcWallet } from "@/components/Icons";

const T: Dict = {
  title: { ar: "مؤشرات المنصة", en: "Platform metrics" },
  accounts: { ar: "الحسابات", en: "Accounts" },
  revenue: { ar: "إيراد الشهر", en: "Revenue this month" },
  overdue: { ar: "فواتير متأخرة", en: "Overdue invoices" },
  expiring: { ar: "اشتراكات تنتهي قريبًا", en: "Expiring soon" },
  failedPayments: { ar: "مدفوعات فاشلة", en: "Failed payments" },
  byState: { ar: "الاشتراكات بالحالة", en: "Subscriptions by state" },
  viewAccounts: { ar: "عرض الحسابات", en: "View accounts" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  trial: { ar: "تجربة", en: "Trial" },
  active: { ar: "نشط", en: "Active" },
  grace: { ar: "مهلة", en: "Grace" },
  read_only: { ar: "قراءة فقط", en: "Read-only" },
  past_due: { ar: "متأخر", en: "Past due" },
  cancelled: { ar: "ملغى", en: "Cancelled" },
};

type Dash = {
  accounts_total: number;
  subscriptions_by_state: Record<string, number>;
  revenue_this_month: string;
  overdue_invoices: number;
  expiring_soon: number;
  failed_payments_this_month: number;
};

function money(v: string) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                  maximumFractionDigits: 2 })
    : v;
}

export default function DashboardPage() {
  const { L } = useT(T);
  const [d, setD] = useState<Dash | null>(null);

  useEffect(() => {
    pGet<Dash>("/platform/dashboard/").then(setD).catch(() => setD(null));
  }, []);

  if (!d) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("loading")}
      </div>
    );
  }

  const cards = [
    { key: "accounts", value: String(d.accounts_total), icon: IcUsers },
    { key: "revenue", value: money(d.revenue_this_month), icon: IcWallet,
      tone: "var(--ok)" },
    { key: "overdue", value: String(d.overdue_invoices), icon: IcAlert,
      tone: d.overdue_invoices > 0 ? "var(--danger)" : undefined },
    { key: "expiring", value: String(d.expiring_soon), icon: IcAlert,
      tone: d.expiring_soon > 0 ? "var(--copper)" : undefined },
    { key: "failedPayments", value: String(d.failed_payments_this_month),
      icon: IcAlert,
      tone: d.failed_payments_this_month > 0 ? "var(--danger)" : undefined },
  ];

  return (
    <div className="stack">
      <div className="spread">
        <h1>{L("title")}</h1>
        <Link href="/accounts" className="btn btn-sm btn-primary">
          {L("viewAccounts")}
        </Link>
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
        gap: 14,
      }}>
        {cards.map((c) => {
          const Icon = c.icon;
          return (
            <div key={c.key} className="card" style={{ padding: 18 }}>
              <div className="row" style={{ marginBottom: 8 }}>
                <Icon size={18} />
                <span className="muted" style={{ fontSize: ".84rem" }}>
                  {L(c.key)}
                </span>
              </div>
              <div style={{
                fontSize: "1.5rem", fontWeight: 600,
                color: c.tone || "var(--ink)",
              }}>
                <span className="num">{c.value}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 14 }}>{L("byState")}</h2>
        <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
          {Object.entries(d.subscriptions_by_state).map(([state, n]) => (
            <div key={state} className="badge" style={{
              padding: "8px 14px", fontSize: ".9rem",
            }}>
              {L(state, state)}: <span className="num">{n}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
