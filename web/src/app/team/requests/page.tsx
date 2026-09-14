"use client";

/**
 * طلبات المرؤوسين (ق-68).
 *
 * شاشة الإجازات والطلبات نفسها: «بانتظار اعتمادي» و«كل الطلبات» —
 * والنطاق يحصرهما في فريق المشرف.
 */
import LeavesPage from "@/app/leaves/page";

export default function TeamRequestsPage() {
  // ⚠️ **والفريق وحده** — لا الشركة كلّها
  return <LeavesPage teamOnly />;
}
