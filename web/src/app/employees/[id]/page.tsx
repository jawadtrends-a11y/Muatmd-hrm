"use client";

/** ملف موظف — يفتحه مدير الموارد من القائمة. */
import { useParams } from "next/navigation";

import EmployeeProfileView from "@/components/EmployeeProfileView";

export default function EmployeeProfilePage() {
  const params = useParams();
  return <EmployeeProfileView employmentId={Number(params.id)} showBack />;
}
