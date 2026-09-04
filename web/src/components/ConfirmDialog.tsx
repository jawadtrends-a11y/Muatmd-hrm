"use client";

/**
 * نافذة تأكيد بتصميم النظام.
 *
 * نافذة المتصفح (window.confirm) إنجليزية العنوان والأزرار،
 * وخارجة عن الهوية — فمن يقرأ «hr.muatmd.sa says» ثم نصًّا عربيًا
 * يرى شاشتين لا واحدة.
 */
import { useEffect } from "react";

import { useT, type Dict } from "@/lib/prefs";

const T: Dict = {
  confirm: { ar: "تأكيد", en: "Confirm" },
  cancel: { ar: "إلغاء", en: "Cancel" },
};

export type ConfirmTone = "primary" | "danger";

export default function ConfirmDialog({
  open, message, tone = "primary", confirmLabel,
  onConfirm, onCancel,
}: {
  open: boolean;
  message: string;
  tone?: ConfirmTone;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { L } = useT(T);

  // Esc يُغلق — فالمخرج بيد المستخدم دائمًا
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      onClick={onCancel}
      style={{
        position: "fixed", inset: 0, zIndex: 300,
        background: "rgba(16,28,38,.45)",
        display: "grid", placeItems: "center", padding: 20,
      }}
    >
      <div
        className="card"
        onClick={(e) => e.stopPropagation()}
        style={{ width: "100%", maxWidth: 420, padding: 24 }}
      >
        <div style={{
          fontSize: ".95rem", lineHeight: 1.7, marginBottom: 20,
        }}>
          {message}
        </div>
        <div className="row" style={{ justifyContent: "flex-end", gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={onCancel}>
            {L("cancel")}
          </button>
          <button
            className={`btn btn-sm ${
              tone === "danger" ? "btn-danger" : "btn-primary"}`}
            onClick={onConfirm}
            autoFocus
          >
            {confirmLabel || L("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
