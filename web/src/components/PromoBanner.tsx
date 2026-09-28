"use client";

/**
 * شريط العرض — لشاشتي الأسعار: العامّة (قبل التسجيل) والاشتراك.
 *
 * ⚠️⚠️ ق-٢٨١: **كودٌ لا يعرفه أحدٌ لا يُستعمل** (تنبيه جواد): تُنشئه اللوحة
 * ويقبله الخادم، **ولا مكانَ يُعلن عنه** — فيبقى حبرًا.
 *
 * ⚠️ **ولا يظهر شيءٌ عند الخطأ**: فشريطٌ مكسورٌ أسوأ من غيابه.
 */
import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";

type Promo = { enabled: boolean; text?: string; code?: string };

export default function PromoBanner() {
  const [p, setP] = useState<Promo | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/promo/`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setP(d))
      .catch(() => setP(null));
  }, []);

  if (!p?.enabled || !p.text) return null;

  return (
    <div style={{
      background: "var(--brand-50, #e8f5f4)",
      border: "1px solid var(--brand, #0E7C86)",
      borderRadius: 10, padding: "12px 16px", marginBottom: 16,
      display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
    }}>
      <span style={{ fontWeight: 600 }}>{p.text}</span>
      {p.code && (
        <button type="button"
          onClick={() => {
            navigator.clipboard?.writeText(p.code!);
            setCopied(true);
            setTimeout(() => setCopied(false), 1800);
          }}
          style={{
            background: "var(--brand, #0E7C86)", color: "#fff",
            border: 0, borderRadius: 6, padding: "6px 14px",
            fontWeight: 700, cursor: "pointer", letterSpacing: ".5px",
          }}>
          {copied ? "نُسخ ✓" : p.code}
        </button>
      )}
    </div>
  );
}
