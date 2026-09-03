"""
القوالب الافتراضية بالثلاث لغات.

⚠️ مسودة تحتاج مراجعة: النصوص العربية من صياغة النظام، والإنجليزية
والأوردو ترجمة أولية. يجب أن يراجعها ناطق أصلي يعمل في الموارد
البشرية بالخليج قبل الإطلاق — العمالة تفهم المصطلحات المعرّبة
(اقامہ، نطاقات) أكثر من ترجمتها الحرفية.

المتغيرات المتاحة موثّقة مع كل قالب.
"""
from django.db import transaction

from apps.notifications.catalog import EVENTS
from apps.notifications.models import Channel, NotificationTemplate

# (subject_ar, body_ar, subject_en, body_en, subject_ur, body_ur)
TEMPLATES = {
    "employee.hired": (
        "موظف جديد: {{employee_name}}",
        "انضم {{employee_name}} إلى {{company_name}} بتاريخ {{join_date}} بمسمى {{job_title}}.",
        "New employee: {{employee_name}}",
        "{{employee_name}} joined {{company_name}} on {{join_date}} as {{job_title}}.",
        "نیا ملازم: {{employee_name}}",
        "{{employee_name}} نے {{join_date}} کو {{company_name}} میں {{job_title}} کے طور پر شمولیت اختیار کی۔",
    ),
    "employee.document_expiring": (
        "تنبيه: {{document_type}} تنتهي خلال {{days_left}} يومًا",
        "{{document_type}} الخاصة بـ{{employee_name}} تنتهي بتاريخ {{expiry_date}}. يرجى التجديد.",
        "Alert: {{document_type}} expires in {{days_left}} days",
        "{{employee_name}}'s {{document_type}} expires on {{expiry_date}}. Please renew.",
        "انتباہ: {{document_type}} {{days_left}} دن میں ختم ہو رہا ہے",
        "{{employee_name}} کا {{document_type}} {{expiry_date}} کو ختم ہو رہا ہے۔ براہ کرم تجدید کریں۔",
    ),
    "employee.terminated": (
        "إنهاء خدمة: {{employee_name}}",
        "أُنهيت خدمة {{employee_name}} بتاريخ {{end_date}}. السبب: {{reason}}.",
        "Termination: {{employee_name}}",
        "{{employee_name}}'s service ended on {{end_date}}. Reason: {{reason}}.",
        "ملازمت کا خاتمہ: {{employee_name}}",
        "{{employee_name}} کی ملازمت {{end_date}} کو ختم ہوئی۔ وجہ: {{reason}}۔",
    ),
    "attendance.absent": (
        "غياب بلا إذن",
        "لم يُسجَّل حضور {{employee_name}} بتاريخ {{work_date}}.",
        "Unexcused absence",
        "No attendance recorded for {{employee_name}} on {{work_date}}.",
        "غیر حاضری",
        "{{work_date}} کو {{employee_name}} کی حاضری درج نہیں ہوئی۔",
    ),
    "attendance.missing_punch": (
        "نسيت تسجيل الانصراف",
        "لم يُسجَّل انصرافك بتاريخ {{work_date}}. يرجى مراجعة الموارد البشرية.",
        "Missing check-out",
        "Your check-out on {{work_date}} was not recorded. Please contact HR.",
        "چھٹی کا وقت درج نہیں ہوا",
        "{{work_date}} کو آپ کا اخراج درج نہیں ہوا۔ براہ کرم HR سے رابطہ کریں۔",
    ),
    "leave.submitted": (
        "طلب إجازة جديد",
        "قدّم {{employee_name}} طلب {{leave_type}} من {{start_date}} إلى {{end_date}} ({{days}} أيام).",
        "New leave request",
        "{{employee_name}} requested {{leave_type}} from {{start_date}} to {{end_date}} ({{days}} days).",
        "چھٹی کی نئی درخواست",
        "{{employee_name}} نے {{start_date}} سے {{end_date}} تک {{leave_type}} کی درخواست دی ({{days}} دن)۔",
    ),
    "leave.approved": (
        "اعتُمدت إجازتك",
        "اعتُمد طلب {{leave_type}} من {{start_date}} إلى {{end_date}}. رصيدك المتبقي: {{balance}} يومًا.",
        "Leave approved",
        "Your {{leave_type}} from {{start_date}} to {{end_date}} is approved. Remaining balance: {{balance}} days.",
        "آپ کی چھٹی منظور ہوئی",
        "{{start_date}} سے {{end_date}} تک آپ کی {{leave_type}} منظور ہو گئی۔ باقی بیلنس: {{balance}} دن۔",
    ),
    "leave.rejected": (
        "رُفض طلب الإجازة",
        "رُفض طلب {{leave_type}} من {{start_date}}. السبب: {{reason}}.",
        "Leave rejected",
        "Your {{leave_type}} request from {{start_date}} was rejected. Reason: {{reason}}.",
        "چھٹی کی درخواست مسترد",
        "{{start_date}} سے آپ کی {{leave_type}} درخواست مسترد ہوئی۔ وجہ: {{reason}}۔",
    ),
    "leave.balance_low": (
        "رصيد إجازاتك منخفض",
        "رصيدك المتبقي من {{leave_type}}: {{balance}} يومًا.",
        "Low leave balance",
        "Your remaining {{leave_type}} balance: {{balance}} days.",
        "چھٹیوں کا بیلنس کم ہے",
        "آپ کا باقی {{leave_type}} بیلنس: {{balance}} دن۔",
    ),
    "request.submitted": (
        "طلب جديد: {{request_type}}",
        "قدّم {{employee_name}} طلب {{request_type}} رقم {{request_no}}.",
        "New request: {{request_type}}",
        "{{employee_name}} submitted {{request_type}} request #{{request_no}}.",
        "نئی درخواست: {{request_type}}",
        "{{employee_name}} نے {{request_type}} درخواست نمبر {{request_no}} جمع کرائی۔",
    ),
    "request.pending_approval": (
        "طلب بانتظار اعتمادك",
        "طلب {{request_type}} من {{employee_name}} بانتظار اعتمادك.",
        "Request awaiting your approval",
        "{{request_type}} request from {{employee_name}} awaits your approval.",
        "درخواست آپ کی منظوری کی منتظر",
        "{{employee_name}} کی {{request_type}} درخواست آپ کی منظوری کی منتظر ہے۔",
    ),
    # الإنابة أثناء الغياب (ق-75)
    "delegation.requested": (
        "طلب إنابة",
        "طلب منك {{absentee}} أن تنوب عنه من {{starts_on}} إلى "
        "{{ends_on}} — بانتظار قبولك.",
        "Delegation request",
        "{{absentee}} asked you to cover from {{starts_on}} to "
        "{{ends_on}} — awaiting your acceptance.",
        "نیابت کی درخواست",
        "{{absentee}} نے آپ سے {{starts_on}} سے {{ends_on}} تک نیابت "
        "کی درخواست کی ہے۔",
    ),
    "delegation.accepted": (
        "قُبلت الإنابة",
        "قبِل {{deputy}} أن ينوب عنك من {{starts_on}} إلى {{ends_on}}.",
        "Delegation accepted",
        "{{deputy}} accepted to cover for you from {{starts_on}} to "
        "{{ends_on}}.",
        "نیابت قبول کر لی گئی",
        "{{deputy}} نے {{starts_on}} سے {{ends_on}} تک نیابت قبول کر لی۔",
    ),
    "delegation.declined": (
        "اعتذر النائب",
        "اعتذر {{deputy}} عن الإنابة — وإجازتك ماضية، وتصعد مهامك "
        "لمدير إدارتك.",
        "Delegation declined",
        "{{deputy}} declined the delegation — your leave stands, and "
        "your tasks go to your department manager.",
        "نیابت سے معذرت",
        "{{deputy}} نے نیابت سے معذرت کی — آپ کی چھٹی برقرار ہے۔",
    ),
    "request.approved": (
        "اعتُمد طلبك",
        "اعتُمد طلب {{request_type}} رقم {{request_no}}.",
        "Request approved",
        "Your {{request_type}} request #{{request_no}} is approved.",
        "آپ کی درخواست منظور",
        "آپ کی {{request_type}} درخواست نمبر {{request_no}} منظور ہوئی۔",
    ),
    "request.rejected": (
        "رُفض طلبك",
        "رُفض طلب {{request_type}} رقم {{request_no}}. السبب: {{reason}}.",
        "Request rejected",
        "Your {{request_type}} request #{{request_no}} was rejected. Reason: {{reason}}.",
        "آپ کی درخواست مسترد",
        "آپ کی {{request_type}} درخواست نمبر {{request_no}} مسترد ہوئی۔ وجہ: {{reason}}۔",
    ),
    "request.sla_breached": (
        "تأخر اعتماد طلب",
        "طلب {{request_type}} رقم {{request_no}} تجاوز مدة الاعتماد المحددة.",
        "Approval overdue",
        "{{request_type}} request #{{request_no}} exceeded the approval deadline.",
        "منظوری میں تاخیر",
        "{{request_type}} درخواست نمبر {{request_no}} منظوری کی مقررہ مدت سے تجاوز کر گئی۔",
    ),
    "payroll.calculation_started": (
        "بدء احتساب المسير",
        "بدأ احتساب مسير {{period}} لـ{{employee_count}} موظفًا.",
        "Payroll calculation started",
        "Payroll calculation for {{period}} started for {{employee_count}} employees.",
        "تنخواہ کا حساب شروع",
        "{{period}} کی تنخواہ کا حساب {{employee_count}} ملازمین کے لیے شروع ہوا۔",
    ),
    "payroll.calculation_completed": (
        "اكتمل احتساب المسير",
        "اكتمل مسير {{period}}. الإجمالي: {{total_net}} ريال لـ{{employee_count}} موظفًا.",
        "Payroll calculation completed",
        "Payroll for {{period}} completed. Total: SAR {{total_net}} for {{employee_count}} employees.",
        "تنخواہ کا حساب مکمل",
        "{{period}} کی تنخواہ مکمل۔ کل: {{total_net}} ریال، {{employee_count}} ملازمین۔",
    ),
    "payroll.variance_detected": (
        "فروقات في المسير تحتاج مراجعة",
        "{{variance_count}} موظفًا تغيّر صافي راتبهم بأكثر من {{threshold}}% عن الشهر السابق.",
        "Payroll variances need review",
        "{{variance_count}} employees had net pay change over {{threshold}}% from last month.",
        "تنخواہ میں فرق، جائزہ درکار",
        "{{variance_count}} ملازمین کی خالص تنخواہ پچھلے ماہ سے {{threshold}}% سے زیادہ تبدیل ہوئی۔",
    ),
    "payroll.submitted": (
        "مسير بانتظار الاعتماد",
        "رُفع مسير {{period}} للاعتماد. الإجمالي: {{total_net}} ريال.",
        "Payroll awaiting approval",
        "Payroll for {{period}} submitted for approval. Total: SAR {{total_net}}.",
        "تنخواہ منظوری کی منتظر",
        "{{period}} کی تنخواہ منظوری کے لیے پیش کی گئی۔ کل: {{total_net}} ریال۔",
    ),
    "payroll.approved": (
        "اعتُمد المسير",
        "اعتُمد مسير {{period}} بواسطة {{approver_name}}. الإجمالي: {{total_net}} ريال.",
        "Payroll approved",
        "Payroll for {{period}} approved by {{approver_name}}. Total: SAR {{total_net}}.",
        "تنخواہ منظور",
        "{{period}} کی تنخواہ {{approver_name}} نے منظور کی۔ کل: {{total_net}} ریال۔",
    ),
    # ══ الاشتراك والفوترة (ق-48) ══
    "subscription.renewal_due": (
        "تجديد الاشتراك قريبًا",
        "ينتهي اشتراكك في {{end_date}} — بعد {{days_left}} أيام. جدّد لتفادي انقطاع الخدمة.",
        "Subscription renewal due",
        "Your subscription ends on {{end_date}} in {{days_left}} days. Renew to avoid interruption.",
        "سبسکرپشن کی تجدید",
        "آپ کی سبسکرپشن {{end_date}} کو ختم ہو رہی ہے۔ {{days_left}} دن باقی ہیں۔",
    ),
    "subscription.renewal_failed": (
        "تعذّر التجديد التلقائي",
        "لم ينجح تجديد الاشتراك بعد {{attempts}} محاولات. الفاتورة {{invoice_no}} بمبلغ {{amount}} ريال بانتظار السداد.",
        "Auto-renewal failed",
        "Renewal failed after {{attempts}} attempts. Invoice {{invoice_no}} for SAR {{amount}} is pending.",
        "خودکار تجدید ناکام",
        "{{attempts}} کوششوں کے بعد تجدید ناکام۔ انوائس {{invoice_no}} زیر التوا ہے۔",
    ),
    "subscription.expired": (
        "انتهى الاشتراك",
        "انتهى اشتراكك. الحساب للقراءة فقط وبياناتك محفوظة — جدّد لاستعادة الوصول الكامل.",
        "Subscription expired",
        "Your subscription expired. The account is read-only and your data is safe — renew to restore full access.",
        "سبسکرپشن ختم",
        "آپ کی سبسکرپشن ختم ہو گئی۔ اکاؤنٹ صرف پڑھنے کے لیے ہے، ڈیٹا محفوظ ہے۔",
    ),
    "payslip.available": (
        "قسيمة راتب {{period}}",
        "قسيمة راتبك لشهر {{period}} متاحة الآن. الصافي: {{net_pay}} ريال.",
        "Payslip for {{period}}",
        "Your payslip for {{period}} is available. Net pay: SAR {{net_pay}}.",
        "{{period}} کی تنخواہ کی پرچی",
        "{{period}} کی آپ کی تنخواہ کی پرچی دستیاب ہے۔ خالص: {{net_pay}} ریال۔",
    ),
    "nitaqat.band_changed": (
        "تغيّر نطاق المنشأة",
        "انتقلت {{company_name}} من النطاق {{old_band}} إلى {{new_band}}. نسبة التوطين: {{percentage}}%.",
        "Nitaqat band changed",
        "{{company_name}} moved from {{old_band}} to {{new_band}}. Saudization: {{percentage}}%.",
        "نطاقات کا درجہ تبدیل",
        "{{company_name}} {{old_band}} سے {{new_band}} میں منتقل ہوئی۔ سعودائزیشن: {{percentage}}%۔",
    ),
    "nitaqat.at_risk": (
        "تحذير: اقتراب من نطاق أدنى",
        "{{company_name}} على بعد {{margin}} من الهبوط إلى النطاق {{lower_band}}.",
        "Warning: approaching lower band",
        "{{company_name}} is {{margin}} away from dropping to {{lower_band}}.",
        "انتباہ: کم درجے کے قریب",
        "{{company_name}} {{lower_band}} میں گرنے سے {{margin}} کے فاصلے پر ہے۔",
    ),
    "subscription.trial_ending": (
        "قرب انتهاء الفترة التجريبية",
        "تنتهي تجربة {{company_name}} بتاريخ {{end_date}}. اشترك للاستمرار.",
        "Trial ending soon",
        "{{company_name}}'s trial ends on {{end_date}}. Subscribe to continue.",
        "آزمائشی مدت ختم ہو رہی ہے",
        "{{company_name}} کی آزمائشی مدت {{end_date}} کو ختم ہو رہی ہے۔",
    ),
    "subscription.past_due": (
        "تأخر السداد",
        "اشتراك {{company_name}} متأخر السداد. المبلغ: {{amount}} ريال.",
        "Payment past due",
        "{{company_name}}'s subscription is past due. Amount: SAR {{amount}}.",
        "ادائیگی میں تاخیر",
        "{{company_name}} کی سبسکرپشن کی ادائیگی باقی ہے۔ رقم: {{amount}} ریال۔",
    ),
    "subscription.downgraded": (
        "تنزيل الباقة",
        "نُزّلت باقة {{company_name}} من {{old_plan}} إلى {{new_plan}}. بياناتك محفوظة بالكامل.",
        "Plan downgraded",
        "{{company_name}} downgraded from {{old_plan}} to {{new_plan}}. All data preserved.",
        "پیکج کم کر دیا گیا",
        "{{company_name}} کا پیکج {{old_plan}} سے {{new_plan}} کر دیا گیا۔ تمام ڈیٹا محفوظ ہے۔",
    ),
    "access.role_changed": (
        "تغيّرت صلاحياتك",
        "تغيّر دورك في {{company_name}} إلى {{role_name}}.",
        "Your permissions changed",
        "Your role in {{company_name}} changed to {{role_name}}.",
        "آپ کے اختیارات تبدیل",
        "{{company_name}} میں آپ کا کردار {{role_name}} میں تبدیل ہوا۔",
    ),
}


@transaction.atomic
def sync_default_templates():
    """يزامن القوالب الافتراضية بالثلاث لغات. آمن للتكرار."""
    created = 0
    for spec in EVENTS:
        t = TEMPLATES.get(spec.key)
        if t is None:
            continue
        s_ar, b_ar, s_en, b_en, s_ur, b_ur = t
        for locale, subject, body in (
            ("ar", s_ar, b_ar), ("en", s_en, b_en), ("ur", s_ur, b_ur),
        ):
            for channel in spec.channels:
                _, is_new = NotificationTemplate.objects.update_or_create(
                    account=None, event_key=spec.key,
                    channel=channel, locale=locale,
                    defaults={"subject": subject, "body": body},
                )
                created += int(is_new)
    return {"templates": NotificationTemplate.objects.filter(
        account__isnull=True).count(), "created": created}
