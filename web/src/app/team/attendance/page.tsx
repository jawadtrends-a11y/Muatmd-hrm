"use client";

/**
 * حضور المرؤوسين (ق-68).
 *
 * الشاشة نفسها التي يراها مدير الموارد — والنطاق في الخادم هو ما
 * يحصر كلًّا في نطاقه. فلا تكرار للكود ولا شرط في الواجهة.
 */
import AttendancePage from "@/app/attendance/page";

export default function TeamAttendancePage() {
  return <AttendancePage />;
}
