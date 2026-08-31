"use client";

/**
 * عميل API لوحة المنصة (ق-51).
 *
 * ⚠️ معزول تمامًا عن عميل نظام العميل: جلسة كوكي منفصلة
 * (muatmd_platform_session) لا رمز، ومسارات /platform/* لا /api/*.
 * لا يشاركان تخزينًا ولا ترويسات.
 */

export const API_BASE = process.env.NEXT_PUBLIC_ADMIN_BASE || "";

export class AdminError extends Error {
  status: number;
  code: string;
  detail: unknown;

  constructor(status: number, message: string, code = "", detail?: unknown) {
    super(message);
    this.name = "AdminError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }

  get isAuth() {
    return this.status === 401;
  }
  get isForbidden() {
    return this.status === 403;
  }
  get isNetwork() {
    return this.status === 0;
  }
  /** 428 — يحتاج تأكيدًا صريحًا قبل الكتابة في حساب عميل (ق-46) */
  get needsConfirm() {
    return this.status === 428;
  }
  /** يلزم رمز التحقق الثنائي */
  get needsTotp() {
    return this.code === "totp_required";
  }
}

async function parse(res: Response) {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text.slice(0, 300) };
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "include",      // الكوكي هو المصادقة
    });
  } catch (e) {
    throw new AdminError(0, "تعذّر الاتصال بالخادم", "network", e);
  }

  const data = await parse(res);

  if (!res.ok) {
    const d = data as { detail?: string; code?: string } | null;
    throw new AdminError(
      res.status,
      d?.detail || `خطأ ${res.status}`,
      d?.code || "",
      data,
    );
  }

  return data as T;
}

export const pGet = <T = unknown>(path: string) => request<T>("GET", path);
export const pPost = <T = unknown>(path: string, body?: unknown) =>
  request<T>("POST", path, body);
export const pPut = <T = unknown>(path: string, body?: unknown) =>
  request<T>("PUT", path, body);
export const pDelete = <T = unknown>(path: string) =>
  request<T>("DELETE", path);

export function qs(params: Record<string, unknown>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** قدرات الدور — تُقرأ مرة عند الدخول وتحكم عرض الأزرار */
export type PlatformUser = {
  username: string;
  full_name: string;
  email: string;
  role: string;
  role_label: string;
  capabilities: string[];
  totp_enabled: boolean;
  last_login_at: string | null;
  impersonating: {
    active: boolean;
    account: string;
    minutes_left: number;
    message: string;
    warning: string;
  } | null;
};

export function can(user: PlatformUser | null, capability: string): boolean {
  return !!user?.capabilities?.includes(capability);
}
