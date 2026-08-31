"use client";

/** الصفحة الرئيسية — نقطة انطلاق مؤقتة حتى نبني اللوحة. */
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";

const T: Dict = {
  welcome: { ar: "مرحبًا", en: "Welcome" },
  ready: { ar: "النظام جاهز", en: "System ready" },
  perms: { ar: "صلاحياتك", en: "Your permissions" },
  company: { ar: "الشركة", en: "Company" },
};

type Workspace = {
  person: { display_name: string } | null;
  company: { name: string } | null;
  permissions: string[];
};

export default function HomePage() {
  const { L } = useT(T);
  const [ws, setWs] = useState<Workspace | null>(null);

  useEffect(() => {
    apiGet<Workspace>("/me/workspace").then(setWs).catch(() => {});
  }, []);

  return (
    <div className="stack">
      <h1>
        {L("welcome")}
        {ws?.person ? `، ${ws.person.display_name}` : ""}
      </h1>

      <div className="card" style={{ padding: 20 }}>
        <div className="spread" style={{ marginBottom: 12 }}>
          <span className="muted">{L("company")}</span>
          <strong>{ws?.company?.name || "—"}</strong>
        </div>
        <div className="spread">
          <span className="muted">{L("perms")}</span>
          <span className="num">{ws?.permissions?.length ?? 0}</span>
        </div>
      </div>
    </div>
  );
}
