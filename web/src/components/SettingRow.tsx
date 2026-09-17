"use client";
/**
 * صفُّ إعدادٍ واحد (ق-218).
 *
 * ⚠️ **ومشتركٌ بين شاشات الإعدادات**: فنسخُه في كلٍّ **يعني
 * أربعة مواضع لتغييرٍ واحد**.
 */
import React from "react";

export default function SettingRow({
  label, hint, children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{
      padding: "14px 0", borderBottom: "1px solid var(--line)",
    }}>
      <div className="spread" style={{ gap: 16, flexWrap: "wrap" }}>
        <div className="grow" style={{ minWidth: 220 }}>
          {/* ق-217: ⚠️ **وخطٌّ أكبر** (بلاغ جواد) — فالصغير يُجهد */}
          <div style={{ fontWeight: 500, fontSize: "1rem" }}>
            {label}
          </div>
          {hint && (
            <div className="muted" style={{ fontSize: ".86rem",
                                            marginTop: 3,
                                            lineHeight: 1.8 }}>
              {hint}
            </div>
          )}
        </div>
        <div style={{ minWidth: 190 }}>{children}</div>
      </div>
    </div>
  );
}
