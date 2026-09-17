"use client";

/**
 * الإعدادات — ثلاثة أقسام:
 *   إعدادات الرواتب · الاشتراك · الفريق والصلاحيات
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcPayroll, IcUsers, IcWallet } from "@/components/Icons";

/**
 * ق-217: **مجموعات الإعدادات** — ⚠️⚠️ **بطاقاتٌ لا قائمةٌ
 * طويلة** (بلاغ جواد): فأربعةٌ وعشرون بندًا في عمودٍ واحد
 * **تُقرأ سطرًا سطرًا والعين تتوه**.
 *
 * ⚠️ **والتجميع يُقلّل زمن البحث**: فمن يريد «أنواع الإجازات»
 * **يذهب لمجموعة الطلبات مباشرةً**.
 */
const GROUPS: {
  key: string;
  items: { href: string; label: string; hint: string; perm: string }[];
}[] = [
  {
    key: "grpOrg",
    items: [
      { href: "/settings/company", label: "company",
        hint: "companyHint", perm: "company.view" },
      { href: "/settings/holidays", label: "holidays",
        hint: "holidaysHint", perm: "org.view" },
      { href: "/settings/tags", label: "tagsLink",
        hint: "tagsHint", perm: "employees.view" },
    ],
  },
  {
    key: "grpAccess",
    items: [
      { href: "/settings/users", label: "users",
        hint: "usersHint", perm: "access.view" },
      { href: "/settings/access", label: "roles",
        hint: "rolesHint", perm: "access.manage" },
      { href: "/settings/api-keys", label: "apiKeys",
        hint: "apiKeysHint", perm: "account.manage" },
    ],
  },
  {
    key: "grpPayroll",
    items: [
      { href: "/settings/pay-components", label: "payComponents",
        hint: "payComponentsHint", perm: "payroll.view" },
      { href: "/settings/job-grades", label: "grades",
        hint: "gradesHint", perm: "employees.view" },
      { href: "/settings/allowances", label: "allowancesLink",
        hint: "allowancesHint", perm: "payroll.view" },
      { href: "/settings/expense-categories", label: "expenseCats",
        hint: "expenseCatsHint", perm: "payroll.view" },
      { href: "/settings/bank-templates", label: "bankTpl",
        hint: "bankTplHint", perm: "payroll.view" },
      { href: "/settings/gl", label: "glLink",
        hint: "glHint", perm: "payroll.view" },
      { href: "/settings/payroll-approval", label: "payrollChain",
        hint: "payrollChainHint", perm: "payroll.view" },
      // ق-218: **شاشاتٌ موضوعية** — حقولُ النموذج الطويل
      { href: "/settings/eosb", label: "eosbLink",
        hint: "eosbLinkHint", perm: "payroll.view" },
      { href: "/settings/payroll-rules", label: "payrollRules",
        hint: "payrollRulesHint", perm: "payroll.view" },
      { href: "/settings/advances", label: "advancesPolicy",
        hint: "advancesPolicyHint", perm: "payroll.view" },
    ],
  },
  {
    key: "grpAttendance",
    items: [
      { href: "/settings/shifts", label: "shifts",
        hint: "shiftsHint", perm: "attendance.view" },
      { href: "/settings/devices", label: "devices",
        hint: "devicesHint", perm: "sites.view" },
      { href: "/settings/exemptions", label: "exemptions",
        hint: "exemptionsHint", perm: "attendance.view" },
      { href: "/settings/attendance-policy", label: "attPolicy",
        hint: "attPolicyHint", perm: "attendance.view" },
    ],
  },
  {
    key: "grpRequests",
    items: [
      { href: "/settings/leave-types", label: "leaveTypes",
        hint: "leaveTypesHint", perm: "leaves.view" },
      { href: "/settings/approval-chains", label: "chains",
        hint: "chainsHint", perm: "leaves.view" },
      { href: "/settings/custom-requests", label: "customReqs",
        hint: "customReqsHint", perm: "requests.view" },
      { href: "/settings/penalty-policy", label: "penaltyPolicy",
        hint: "penaltyPolicyHint", perm: "employees.view" },
      { href: "/settings/policies", label: "policiesLink",
        hint: "policiesHint", perm: "employees.view" },
    ],
  },
  {
    key: "grpOther",
    items: [
      { href: "/settings/letter-templates", label: "letterTemplates",
        hint: "letterTemplatesHint", perm: "employees.view" },
      { href: "/settings/notification-templates", label: "notifTpl",
        hint: "notifTplHint", perm: "company.view" },
      { href: "/settings/imports", label: "importsLink",
        hint: "importsHint", perm: "employees.create" },
    ],
  },
];

const T: Dict = {
  // ق-217: عناوين المجموعات
  grpOrg: { ar: "المنشأة", en: "Organization" },
  grpAccess: { ar: "المستخدمون والصلاحيات", en: "Users & access" },
  grpPayroll: { ar: "الرواتب", en: "Payroll" },
  grpAttendance: { ar: "الحضور", en: "Attendance" },
  grpRequests: { ar: "الطلبات واللوائح", en: "Requests & policies" },
  grpOther: { ar: "القوالب والبيانات", en: "Templates & data" },
  eosbLink: { ar: "مكافأة نهاية الخدمة", en: "End-of-service" },
  eosbLinkHint: { ar: "الأجر الذي تُحتسب عليه المكافأة",
                  en: "The wage the award is computed on" },
  payrollRules: { ar: "قواعد احتساب الرواتب", en: "Payroll rules" },
  payrollRulesHint: { ar: "الإضافيّ وأساس اليوم وتاريخ الاقتطاع",
                      en: "Overtime, day basis, cutoff" },
  advancesPolicy: { ar: "سياسة السلف", en: "Advances policy" },
  advancesPolicyHint: { ar: "الحدود والأقساط وشروط المنح",
                        en: "Limits and conditions" },
  attPolicy: { ar: "البصمة والتواجد", en: "Punch & presence" },
  attPolicyHint: { ar: "بصمة الجوال وتتبّع الموقع وأنشطة العمل",
                   en: "Mobile punch, presence, activities" },
  title: { ar: "الإعدادات", en: "Settings" },
  general: { ar: "إعدادات عامة", en: "General" },
  users: { ar: "المستخدمون", en: "Users" },
  company: { ar: "بيانات المنشأة", en: "Company details" },
  holidays: { ar: "العطل الرسمية", en: "Public holidays" },
  exemptions: { ar: "الإعفاء من البصمة", en: "Attendance exemptions" },
  exemptionsHint: {
    ar: "من لا يُطالَب ببصمة ولا يُعدّ غائبًا",
    en: "Employees not required to punch",
  },
  holidaysHint: {
    ar: "عطل الشركة — لا تُخصم من الرصيد ولا من الأجر",
    en: "Company holidays — not deducted from balance or pay",
  },
  companyHint: {
    ar: "السجل التجاري والأرقام النظامية وبريد التواصل",
    en: "Registration, statutory numbers and contact email",
  },
  notifTpl: { ar: "قوالب الإشعارات", en: "Notification templates" },
  notifTplHint: {
    ar: "نصّ كل إشعار في قنواته",
    en: "Text of each notification",
  },
  bankTpl: { ar: "قوالب البنوك", en: "Bank templates" },
  bankTplHint: {
    ar: "صيغة ملف الرواتب لكل بنك",
    en: "Payroll file format per bank",
  },
  grades: { ar: "السلّم الوظيفي", en: "Job scale" },
  gradesHint: {
    ar: "المراتب ودرجاتها — اختياري",
    en: "Grades and steps — optional",
  },
  payComponents: { ar: "بنود الأجر", en: "Pay components" },
  payComponentsHint: {
    ar: "الاستحقاقات والاستقطاعات وأعلامها",
    en: "Earnings, deductions and flags",
  },
  devices: { ar: "أجهزة البصمة", en: "Punch devices" },
  devicesHint: {
    ar: "الأجهزة المصرَّح لها بإرسال البصمات",
    en: "Devices allowed to submit punches",
  },
  shifts: { ar: "فترات العمل", en: "Shifts" },
  shiftsHint: {
    ar: "أوقات الدوام وأيامه وفترات السماح",
    en: "Working hours, days and grace",
  },
  chains: { ar: "سلاسل الاعتماد", en: "Approval chains" },
  chainsHint: {
    ar: "من يعتمد كل نوع من الطلبات",
    en: "Who approves each request type",
  },
  leaveTypes: { ar: "أنواع الإجازات", en: "Leave types" },
  leaveTypesHint: {
    ar: "سياسات الاستحقاق والأجر والترحيل",
    en: "Entitlement and pay policies",
  },
  letterTemplates: { ar: "قوالب الخطابات", en: "Letter templates" },
  letterTemplatesHint: {
    ar: "صيغ الشهادات والتعريفات بمتغيّراتها",
    en: "Certificate and letter templates",
  },
  policiesLink: { ar: "السياسات", en: "Policies" },
  policiesHint: {
    ar: "سياسات المنشأة وإقرار الموظفين بها",
    en: "Company policies and acknowledgements",
  },
  penaltyPolicy: { ar: "لائحة الجزاءات", en: "Penalty policy" },
  penaltyPolicyHint: {
    ar: "المخالفات ودرجاتها ونسخ اللائحة",
    en: "Violations, degrees, and policy versions",
  },
  tagsLink: { ar: "وسوم الموظفين", en: "Employee tags" },
  tagsHint: {
    ar: "تصنيفاتٌ تُرشّح بها قوائمك",
    en: "Labels to filter your lists",
  },
  allowancesLink: { ar: "المخصّصات المصروفة", en: "Claimable allowances" },
  allowancesHint: {
    ar: "غداء عمل ومواصلات وغيرها — ومن يستحقّها",
    en: "Meal, transport and more — and who may claim",
  },
  expenseCats: { ar: "فئات المصروفات", en: "Expense categories" },
  expenseCatsHint: {
    ar: "وقود وسفر وضيافة — وسقوفها",
    en: "Fuel, travel, hospitality — and caps",
  },
  payrollChain: { ar: "سلسلة اعتماد المسير", en: "Payroll approval" },
  payrollChainHint: {
    ar: "من يعتمد المسير وبأيّ ترتيب",
    en: "Who approves payroll and in what order",
  },
  customReqs: { ar: "الطلبات المخصّصة", en: "Custom requests" },
  customReqsHint: {
    ar: "أنواع طلبات تُنشئها بحقولها",
    en: "Request types you define",
  },
  apiKeys: { ar: "مفاتيح API", en: "API keys" },
  apiKeysHint: {
    ar: "اربط أنظمتك ببياناتك برمجيًّا",
    en: "Connect your systems programmatically",
  },
  glLink: { ar: "القيد المحاسبيّ", en: "GL export" },
  glHint: {
    ar: "اربط بنود الأجر بحساباتك وصدّر القيد",
    en: "Map components to accounts and export",
  },
  importsLink: { ar: "الاستيراد من نظامٍ سابق", en: "Import" },
  importsHint: {
    ar: "الموظفون وأرصدة الإجازات والحضور",
    en: "Employees, balances and attendance",
  },
  usersHint: {
    ar: "حسابات الدخول وصلاحياتها",
    en: "Login accounts and permissions",
  },
  roles: { ar: "الأدوار والصلاحيات", en: "Roles & permissions" },
  rolesHint: { ar: "من يرى ماذا، ومن يعتمد ماذا",
               en: "Who sees and approves what" },
  payroll: { ar: "الإعدادات العامة", en: "General settings" },
  subscription: { ar: "الاشتراك", en: "Subscription" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  saved: { ar: "حُفظت التغييرات", en: "Saved" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا صلاحية لهذا القسم", en: "No access to this section" },
  noSub: { ar: "لا اشتراك لهذا الحساب بعد", en: "No subscription yet" },
  overTitle: { ar: "موظفون زائدون عن اشتراكك", en: "Employees over your plan" },
  overBody: {
    ar: "لديك {n} موظفًا زائدًا — والمستحقّ {a} ريالًا عن {d} يومًا متبقّية",
    en: "{n} extra employees — {a} SAR for the remaining {d} days",
  },
  overPay: { ar: "دفع الفرق", en: "Pay the difference" },
  overPaying: { ar: "جارٍ التجهيز…", en: "Preparing…" },
  browsePlans: { ar: "عرض الباقات والاشتراك", en: "View plans" },
  noSubHint: {
    ar: "يُفعّله مدير المنصة — راجعه لتفعيل اشتراك منشأتك",
    en: "Activated by the platform administrator",
  },
  // إعدادات الرواتب
  eosbBasis: { ar: "أجر مكافأة نهاية الخدمة", en: "EOSB wage basis" },
  otBasis: { ar: "أساس العمل الإضافي", en: "Overtime basis" },
  otBasisHint: {
    ar: "الأساس المعتمد لكل ساعة إضافية",
    en: "Rate used for each overtime hour",
  },
  otChoice: { ar: "السماح باختيار معامِل الإضافي", en: "Rate choice" },
  otChoiceHint: {
    ar: "يُظهر للموظف خيار ×2 في طلبه — والمعتمِد يقبل أو يرفض",
    en: "Lets employees request ×2 — approver accepts or rejects",
  },
  otBasisX2: { ar: "أساس معامِل ×2", en: "×2 basis" },
  otBasisX2Hint: {
    ar: "يُستعمل حين يُعتمد طلبٌ بـ×2",
    en: "Used when a ×2 request is approved",
  },
  activitiesOn: { ar: "أنشطة العمل", en: "Work activities" },
  activitiesHint: {
    ar: "مهامّ يومية يُسندها المديرون — وتفعيلها لا يُلزمهم",
    en: "Daily tasks managers may assign — not mandatory",
  },
  presenceOn: { ar: "تتبّع التواجد في الموقع", en: "Presence tracking" },
  presenceHint: {
    ar: "داخل الموقع أو خارجه أثناء الفترة — ولا يُحفظ موقع الموظف",
    en: "Inside/outside during shift — actual location never stored",
  },
  presenceTolerance: { ar: "تسامح الخروج (دقيقة)", en: "Tolerance (min)" },
  toleranceHint: {
    ar: "لا يُقترَح خصمٌ دونها — كساعة البريك",
    en: "No deduction suggested below this — e.g. break time",
  },
  eosbHint: {
    ar: "يجب تحديده قبل أول مسير مستحقات — الصمت هنا قرار مالي لم يتخذه أحد",
    en: "Must be set before the first settlement run",
  },
  basicHousingTransport: {
    ar: "الراتب الأساسي + بدل السكن والمواصلات",
    en: "Basic + housing and transport",
  },
  basicAll: {
    ar: "الراتب الأساسي + جميع البدلات",
    en: "Basic + all allowances",
  },
  mobilePunch: { ar: "بصمة الجوال", en: "Mobile punch" },
  mobilePunchHint: {
    ar: "الافتراضي للشركة — وفترة العمل وملف الموظف يغلبانه",
    en: "Company default — shift and employee override it",
  },
  enabled: { ar: "مفعّلة", en: "Enabled" },
  disabled: { ar: "معطّلة", en: "Disabled" },
  basicOnly: { ar: "الأساسي فقط", en: "Basic only" },
  basicHousing: { ar: "الأساسي + السكن", en: "Basic + housing" },
  flagged: { ar: "حسب أعلام المكوّنات", en: "By component flags" },
  notSet: { ar: "لم يُحدَّد بعد", en: "Not set" },
  daysPerMonth: { ar: "أيام الشهر للاحتساب", en: "Days per month" },
  cutoffDay: { ar: "يوم الاقتطاع", en: "Cutoff day" },
  cutoffHint: {
    ar: "يوم إقفال الحضور للمسير — فإعداد الرواتب يسبق نهاية الشهر",
    en: "Attendance cutoff for the payroll period",
  },
  calendarMonth: { ar: "الشهر التقويميّ (بلا اقتطاع)",
                   en: "Calendar month" },
  cutoffExample: {
    ar: "⚠️ راتب سبتمبر يُحسب من {n} أغسطس إلى {d} سبتمبر — والحضور والإضافي والخصومات كلّها بهذا المدى",
    en: "September pay covers {n} Aug → {d} Sep",
  },
  varianceThreshold: { ar: "عتبة تنبيه الفروقات %", en: "Variance threshold %" },
  advancesEnabled: { ar: "تمكين نظام السلف", en: "Enable advances" },
  advanceMax: { ar: "الحد الأقصى للسلفة", en: "Max advance amount" },
  advanceMaxMonths: { ar: "الحد بعدد الرواتب", en: "Max in salary months" },
  advanceBlock: {
    ar: "منع سلفة ثانية قبل سداد الأولى",
    en: "Block second advance while one is outstanding",
  },
  payslipGosi: {
    ar: "عرض حصة صاحب العمل في القسيمة",
    en: "Show employer GOSI share on payslip",
  },
  payslipLeave: {
    ar: "عرض رصيد الإجازات في القسيمة",
    en: "Show leave balance on payslip",
  },
  payslipPrev: {
    ar: "عرض مقارنة بالشهر السابق",
    en: "Show previous month comparison",
  },
  payslipHint: {
    ar: "القسيمة للراتب وحده — كل بند إضافي يفتح بابًا لسؤال جديد",
    en: "The payslip is for pay only",
  },
  // الاشتراك
  plan: { ar: "الباقة", en: "Plan" },
  state: { ar: "الحالة", en: "State" },
  cycle: { ar: "الدورة", en: "Cycle" },
  periodEnd: { ar: "ينتهي في", en: "Ends on" },
  daysLeft: { ar: "المتبقي", en: "Days left" },
  days: { ar: "يوم", en: "days" },
  autoRenew: { ar: "التجديد التلقائي", en: "Auto renewal" },
  paymentMethod: { ar: "طريقة الدفع", en: "Payment method" },
  savedCard: { ar: "البطاقة المحفوظة", en: "Saved card" },
  invoices: { ar: "سجلّ المدفوعات", en: "Payment history" },
  payDate: { ar: "التاريخ", en: "Date" },
  payMethod: { ar: "الوسيلة", en: "Method" },
  payPeriod: { ar: "الفترة", en: "Period" },
  invoiceNote: {
    ar: "تصلك الفاتورة الضريبية بالبريد فور نجاح الدفع",
    en: "Your tax invoice arrives by email once payment succeeds",
  },
  amount: { ar: "المبلغ", en: "Amount" },
  status: { ar: "الحالة", en: "Status" },
  dueDate: { ar: "الاستحقاق", en: "Due" },
  yes: { ar: "نعم", en: "Yes" },
  no: { ar: "لا", en: "No" },
  none: { ar: "لا شيء", en: "None" },
  empty: { ar: "لا سجلات", en: "No records" },
};

// ق-218: ⚠️ **وتبويب «الرواتب» حُذف** — فحقوله انتقلت لأربع
// شاشاتٍ موضوعية: **نهاية الخدمة · قواعد الرواتب · السلف ·
// البصمة والتواجد**.
const SECTIONS = ["subscription"] as const;
type Section = (typeof SECTIONS)[number];

type PayrollSettings = {
  eosb_wage_basis: string;
  allow_mobile_punch: boolean;
  payroll_days_per_month: number;
  // ق-157: تاريخ الاقتطاع — ٠ يعني الشهر التقويميّ
  payroll_cutoff_day: number;
  variance_threshold_percent: string;
  advances_enabled: boolean;
  advance_max_amount: string | null;
  advance_max_months_of_salary: string | null;
  advance_block_if_outstanding: boolean;
  payslip_show_employer_gosi: boolean;
  payslip_show_leave_balance: boolean;
  payslip_show_previous_month: boolean;
  // ق-137: معامِل الإضافي
  overtime_basis: string;
  overtime_basis_x2: string;
  allow_overtime_rate_choice: boolean;
  // ق-143: أنشطة العمل
  activities_enabled: boolean;
  // ق-144: تتبّع التواجد
  presence_tracking_enabled: boolean;
  presence_tolerance_minutes: number;
  overtime_basis_options: { value: string; label: string }[];
  [k: string]: unknown;
};

type Subscription = {
  state: string;
  state_label: string;
  plan: string | null;
  cycle_label: string;
  payment_method: string;
  auto_renew: boolean;
  period_end: string | null;
  days_left: number | null;
  saved_card: { brand: string; last_four: string } | null;
};

type Overage = {
  added: number; amount: string; days_remaining: number;
  employees_after: number;
};
type MySub = {
  subscribed_employees?: number; active_employees?: number;
  overage?: Overage;
};

type PaymentRow = {
  id: number; date: string; amount: string;
  status: string; status_label: string; paid: boolean;
  period: string; method: string; last4: string;
};


function money(v: unknown) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                  maximumFractionDigits: 2 })
    : String(v ?? "—");
}


/* ══ صف إعداد — خارج المكوّن الرئيسي ══ */

function Row({
  label, hint, children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{
      padding: "12px 0", borderBottom: "1px solid var(--line)",
    }}>
      <div className="spread" style={{ gap: 16 }}>
        <div className="grow">
          <div style={{ fontWeight: 500 }}>{label}</div>
          {hint && (
            <div className="muted" style={{ fontSize: ".82rem", marginTop: 2 }}>
              {hint}
            </div>
          )}
        </div>
        <div style={{ minWidth: 180 }}>{children}</div>
      </div>
    </div>
  );
}

/* ══ إعدادات الرواتب ══ */



/* ══ لوحة الاشتراك ══ */

function SubscriptionPanel({
  L,
}: {
  L: (k: string, f?: string) => string;
}) {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [mine, setMine] = useState<MySub | null>(null);
  const [payments, setPayments] = useState<PaymentRow[]>([]);
  const [busy, setBusy] = useState(true);
  const [paying, setPaying] = useState(false);
  const [checkout, setCheckout] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    Promise.all([
      apiGet<Subscription>("/account/subscription/").catch(() => null),
      apiGet<MySub>("/account/my-subscription/").catch(() => null),
      apiGet<PaymentRow[]>("/account/payments/").catch(() => []),
    ]).then(([s, m, inv]) => {
      setSub(s);
      setMine(m);
      setPayments(inv);
      setBusy(false);
    });
  }, []);

  if (busy) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        {L("loading")}
      </div>
    );
  }

  if (!sub) {
    // «لا اشتراك» ليست «لا صلاحية»: من لا اشتراك لحسابه سيظنّ
    // أنه ممنوع فيراجع مديره بلا سبب.
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        <div style={{ fontWeight: 500 }}>{L("noSub")}</div>
        <div style={{ fontSize: ".86rem", marginTop: 6 }}>
          {L("noSubHint")}
        </div>
        <Link href="/subscribe" className="btn btn-primary"
              style={{ marginTop: 16 }}>
          {L("browsePlans")}
        </Link>
      </div>
    );
  }

  const over = mine?.overage;

  const payOverage = async () => {
    setPaying(true);
    try {
      setCheckout(await apiPost<Record<string, unknown>>(
        "/account/pay-overage/", {}));
    } catch {
      /* الرسالة تظهر بالشريط نفسه */
    } finally { setPaying(false); }
  };

  return (
    <div className="stack">
      {over && Number(over.amount) > 0 && (
        <div className="card" style={{
          padding: 18, borderColor: "var(--copper)",
          background: "var(--copper-soft)",
        }}>
          <div style={{ fontWeight: 600 }}>{L("overTitle")}</div>
          <div style={{ fontSize: ".88rem", marginTop: 6 }}>
            {L("overBody")
              .replace("{n}", String(over.added))
              .replace("{a}", over.amount)
              .replace("{d}", String(over.days_remaining))}
          </div>
          <button className="btn btn-primary" style={{ marginTop: 12 }}
                  disabled={paying} onClick={payOverage}>
            {paying ? L("overPaying") : L("overPay")}
          </button>
        </div>
      )}

      {checkout != null && (
        <OveragePay data={checkout} L={L}
                    onClose={() => setCheckout(null)} />
      )}

      <div className="card" style={{ padding: 20 }}>
        <Row label={L("plan")}>
          <strong>{sub.plan || L("none")}</strong>
        </Row>
        <Row label={L("state")}>
          <span className={
            sub.state === "active" ? "badge badge-ok"
              : sub.state === "trial" ? "badge badge-teal"
              : "badge badge-warn"
          }>
            {sub.state_label}
          </span>
        </Row>
        <Row label={L("cycle")}>{sub.cycle_label}</Row>
        <Row label={L("periodEnd")}>
          {sub.period_end
            ? <span className="num">{sub.period_end}</span> : "—"}
        </Row>
        {sub.days_left != null && (
          <Row label={L("daysLeft")}>
            <span className="num" style={{
              color: sub.days_left <= 5 ? "var(--copper)" : undefined,
              fontWeight: 600,
            }}>
              {sub.days_left}
            </span>{" "}
            {L("days")}
          </Row>
        )}
        <Row label={L("autoRenew")}>
          <span className={sub.auto_renew ? "badge badge-ok" : "badge"}>
            {sub.auto_renew ? L("yes") : L("no")}
          </span>
        </Row>
        <Row label={L("savedCard")}>
          {sub.saved_card
            ? <span className="num">
                {sub.saved_card.brand} •••• {sub.saved_card.last_four}
              </span>
            : L("none")}
        </Row>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line)" }}>
          <div>
            <h3 style={{ fontSize: "1rem", margin: 0 }}>{L("invoices")}</h3>
            <div className="muted" style={{ fontSize: ".8rem", marginTop: 2 }}>
              {L("invoiceNote")}
            </div>
          </div>
        </div>
        {payments.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>
            {L("empty")}
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th style={{ textAlign: "end" }}>{L("payDate")}</th>
                <th style={{ textAlign: "end" }}>{L("amount")}</th>
                <th style={{ textAlign: "end" }}>{L("payPeriod")}</th>
                <th>{L("payMethod")}</th>
                <th>{L("status")}</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id}>
                  <td style={{ textAlign: "end" }}>
                    <span className="num">{p.date}</span>
                  </td>
                  <td style={{ textAlign: "end", fontWeight: 600 }}>
                    <span className="num">{money(p.amount)}</span>
                  </td>
                  <td style={{ textAlign: "end" }} className="muted">
                    <span className="num">{p.period || "—"}</span>
                  </td>
                  <td className="muted">
                    {p.method ? `${p.method} ••${p.last4}` : "—"}
                  </td>
                  <td>
                    <span className={p.paid ? "badge badge-ok" : "badge"}>
                      {p.status_label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ══ الشاشة ══ */

export default function SettingsPage() {
  const { L } = useT(T);

  // ق-217: ⚠️ **وما لا يملكه لا يراه**: فبندٌ يظهر ثم يُمنع
  // **يوهم بقدرةٍ لا يملكها**.
  const [perms, setPerms] = useState<Set<string>>(new Set());
  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((d) => setPerms(new Set(d.permissions || [])))
      .catch(() => setPerms(new Set()));
  }, []);
  // التبويب في الرابط لا في الحالة: يبقى عند التحديث، ويُفتح
  // مباشرةً من قائمة الحساب (?tab=subscription).
  const params = useSearchParams();
  const router = useRouter();
  const fromUrl = params.get("tab") as Section | null;
  const [section, setSectionState] = useState<Section>(
    fromUrl && SECTIONS.includes(fromUrl) ? fromUrl : "subscription");

  const setSection = (s: Section) => {
    setSectionState(s);
    router.replace(`/settings?tab=${s}`,
                   { scroll: false });
  };

  useEffect(() => {
    if (fromUrl && SECTIONS.includes(fromUrl) && fromUrl !== section) {
      setSectionState(fromUrl);
    }
  }, [fromUrl, section]);

  const ICONS: Record<Section, React.ComponentType<{ size?: number }>> = {
    subscription: IcWallet,
  };

  return (
    <div className="stack">
      <h1>{L("title")}</h1>

      {/* ق-217: **بطاقاتٌ مجمَّعة لا قائمةٌ طويلة** */}
      <div style={{ display: "grid", gap: 16,
                    gridTemplateColumns:
                      "repeat(auto-fill, minmax(290px, 1fr))" }}>
        {GROUPS.map((g) => {
          const items = g.items.filter((it) => perms.has(it.perm));
          // ⚠️ **ومجموعةٌ بلا بندٍ مسموح لا تُعرض** — فبطاقةٌ
          // فارغة **تُوهم بنقصٍ في النظام**.
          if (items.length === 0) return null;
          return (
            <div key={g.key} className="card"
                 style={{ padding: 0, overflow: "hidden" }}>
              <div style={{ padding: "12px 16px",
                            borderBottom: "1px solid var(--line)",
                            fontWeight: 600, fontSize: ".92rem",
                            color: "var(--teal)" }}>
                {L(g.key)}
              </div>
              {items.map((it, i) => (
                <Link key={it.href} href={it.href}
                      style={{
                        display: "block", padding: "11px 16px",
                        color: "var(--ink-2)",
                        borderBottom: i < items.length - 1
                          ? "1px solid var(--line)" : "none",
                      }}>
                  <div style={{ fontWeight: 500, fontSize: ".88rem" }}>
                    {L(it.label)}
                  </div>
                  <div className="muted" style={{ fontSize: ".76rem",
                                                  marginTop: 2 }}>
                    {L(it.hint)}
                  </div>
                </Link>
              ))}
            </div>
          );
        })}
      </div>

      <div className="row" style={{ gap: 4, flexWrap: "wrap" }}>
        {SECTIONS.map((s) => {
          const Icon = ICONS[s];
          return (
            <button key={s}
              className={`btn btn-sm ${section === s ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setSection(s)}>
              <Icon size={16} />
              {L(s)}
            </button>
          );
        })}
      </div>

      {section === "subscription" && <SubscriptionPanel L={L} />}
    </div>
  );
}


/* ══ نافذة دفع الفرق (ق-112) ══ */

function OveragePay({ data, L, onClose }: {
  data: Record<string, unknown>;
  L: (k: string, f?: string) => string;
  onClose: () => void;
}) {
  // نموذج ميسر نفسه: بيانات البطاقة لا تمرّ بخوادمنا (ق-47).
  useEffect(() => {
    const CSS = "https://cdn.moyasar.com/mpf/1.15.0/moyasar.css";
    const JS = "https://cdn.moyasar.com/mpf/1.15.0/moyasar.js";
    if (!document.querySelector(`link[href="${CSS}"]`)) {
      const l = document.createElement("link");
      l.rel = "stylesheet"; l.href = CSS;
      document.head.appendChild(l);
    }
    const init = () => {
      const w = window as unknown as {
        Moyasar?: { init: (o: Record<string, unknown>) => void };
      };
      if (!w.Moyasar) return;
      w.Moyasar.init({
        element: ".mysr-over",
        amount: data.amount_halalas,
        currency: "SAR",
        description: `فرق موظفين — ${data.invoice_no}`,
        publishable_api_key: data.publishable_key,
        callback_url: data.callback_url,
        methods: ["creditcard"],
        metadata: { invoice_id: data.invoice_id },
      });
    };
    const existing = document.querySelector(`script[src="${JS}"]`);
    if (existing) { init(); return; }
    const sc = document.createElement("script");
    sc.src = JS;
    sc.onload = init;
    document.body.appendChild(sc);
  }, [data]);

  return (
    <div onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose();
    }} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.5)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 440,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <div className="spread">
          <h3 style={{ margin: 0 }}>{L("overPay")}</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>×</button>
        </div>
        <div className="spread" style={{ marginTop: 12, fontWeight: 700 }}>
          <span>{L("amount")}</span>
          <span className="num">{String(data.total)}</span>
        </div>
        <div className="mysr-over" style={{ marginTop: 18 }} />
      </div>
    </div>
  );
}
