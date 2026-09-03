"""حرّاس محرك الإشعارات."""
import pytest

from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.notifications.catalog import (
    EVENTS, EVENT_KEYS, MANDATORY_KEYS, validate_event_key,
)
from apps.notifications.models import (
    Channel, DeliveryStatus, Notification, NotificationDelivery,
    NotificationPreference, NotificationTemplate,
)
from apps.notifications.renderer import TemplateNotFound, render


LOCALES = ("ar", "en", "ur")


@pytest.fixture
def acct(db):
    return provision_account(
        slug="notif-test", display_name_ar="حساب إشعارات",
        company_name_ar="شركة إشعارات", is_sandbox=True,
    )


@pytest.mark.django_db
def test_unknown_event_rejected():
    with pytest.raises(ValueError):
        validate_event_key("not.a.real.event")


@pytest.mark.django_db
def test_all_events_registered():
    assert len(EVENT_KEYS) == len(EVENTS), "مفاتيح أحداث مكررة"


@pytest.mark.django_db
def test_critical_events_are_mandatory():
    """أحداث لها أثر مالي أو نظامي لا يستطيع المستخدم إيقافها."""
    for key in ("payroll.approved", "nitaqat.at_risk", "access.role_changed",
                "employee.document_expiring", "subscription.past_due"):
        assert key in MANDATORY_KEYS, f"{key} يجب أن يكون إلزاميًا"


@pytest.mark.django_db(transaction=True)
def test_renderer_substitutes_variables(acct):
    with account_scope(acct.account_id):
        NotificationTemplate.objects.create(
            account_id=acct.account_id, event_key="leave.approved",
            channel=Channel.IN_APP, locale="ar",
            subject="اعتماد إجازة", body="تم اعتماد إجازة {{name}} لمدة {{days}} أيام",
        )
        out = render("leave.approved", Channel.IN_APP, "ar",
                     {"name": "محمد", "days": 3}, acct.account_id)
        assert out["body"] == "تم اعتماد إجازة محمد لمدة 3 أيام"


@pytest.mark.django_db(transaction=True)
def test_renderer_falls_back_to_arabic(acct):
    """لا قالب بالأوردو → يرجع للعربية بدل الفشل الصامت."""
    with account_scope(acct.account_id):
        NotificationTemplate.objects.create(
            account_id=acct.account_id, event_key="leave.approved",
            channel=Channel.IN_APP, locale="ar",
            subject="اعتماد", body="نص عربي",
        )
        out = render("leave.approved", Channel.IN_APP, "ur", {}, acct.account_id)
        assert out["locale"] == "ar"


@pytest.mark.django_db(transaction=True)
def test_renderer_raises_when_no_template(acct):
    """
    قالب مفقود يرفع خطأً — لا فشل صامت.

    والحدث المعرَّف في الكود لم يعد يرفعه: العارض يرجع للتعريف
    هناك حين تخلو القاعدة، فقاعدة جديدة بلا بذر لا تُصمت النظام.
    فالخطأ لمن لا نصّ له أصلًا — لا مكتوبًا ولا مبذورًا.
    """
    with account_scope(acct.account_id):
        with pytest.raises(TemplateNotFound):
            render("no.such.event", Channel.IN_APP, "ar", {},
                   acct.account_id)


@pytest.mark.django_db(transaction=True)
def test_renderer_falls_back_to_code(acct):
    """
    الحدث المعرَّف في الكود يُعرض ولو خلت القاعدة.

    فالقاعدة للتخصيص لا للأساس — والبذر خطوة يدوية تُنسى.
    """
    with account_scope(acct.account_id):
        out = render("payroll.approved", Channel.IN_APP, "ar", {},
                     acct.account_id)
    assert out["subject"], "لا عنوان — العارض لم يرجع للكود"


@pytest.mark.django_db(transaction=True)
def test_account_template_overrides_default(acct):
    """قالب الحساب يفوز على القالب الافتراضي."""
    NotificationTemplate.objects.create(
        account=None, event_key="leave.approved",
        channel=Channel.IN_APP, locale="ar", subject="افتراضي", body="نص افتراضي",
    )
    with account_scope(acct.account_id):
        NotificationTemplate.objects.create(
            account_id=acct.account_id, event_key="leave.approved",
            channel=Channel.IN_APP, locale="ar", subject="مخصص", body="نص مخصص",
        )
        out = render("leave.approved", Channel.IN_APP, "ar", {}, acct.account_id)
        assert out["subject"] == "مخصص"


@pytest.mark.django_db(transaction=True)
def test_dispatch_creates_notification_and_deliveries(acct):
    from apps.notifications.bus import emit

    NotificationTemplate.objects.create(
        account=None, event_key="leave.approved",
        channel=Channel.IN_APP, locale="ar",
        subject="إجازة معتمدة", body="اعتُمدت إجازتك",
    )
    result = emit("leave.approved", account_id=acct.account_id,
                  company_id=acct.company_id, recipients=[101, 102],
                  context={"recipient_locale": "ar"}, sync=True)
    assert result["recipients"] == 2
    with account_scope(acct.account_id):
        assert Notification.objects.count() == 2
        # leave.approved له قناتان: in_app + whatsapp
        assert NotificationDelivery.objects.count() == 4


@pytest.mark.django_db(transaction=True)
def test_mandatory_event_ignores_user_preference(acct):
    """الأحداث الإلزامية لا تُوقف بتفضيلات المستخدم."""
    from apps.notifications.bus import emit

    NotificationTemplate.objects.create(
        account=None, event_key="payroll.approved",
        channel=Channel.IN_APP, locale="ar", subject="مسير معتمد", body="اعتُمد",
    )
    with account_scope(acct.account_id):
        NotificationPreference.objects.create(
            account_id=acct.account_id, person_id=201,
            event_key="payroll.approved", channel=Channel.EMAIL,
            is_enabled=False,
        )
    emit("payroll.approved", account_id=acct.account_id,
         recipients=[201], sync=True)
    with account_scope(acct.account_id):
        skipped = NotificationDelivery.objects.filter(
            status=DeliveryStatus.SKIPPED).count()
        assert skipped == 0, "حدث إلزامي تأثر بتفضيل المستخدم"


@pytest.mark.django_db(transaction=True)
def test_optional_event_respects_preference(acct):
    """الأحداث غير الإلزامية تحترم تفضيلات المستخدم."""
    from apps.notifications.bus import emit

    NotificationTemplate.objects.create(
        account=None, event_key="leave.approved",
        channel=Channel.IN_APP, locale="ar", subject="إجازة", body="معتمدة",
    )
    with account_scope(acct.account_id):
        NotificationPreference.objects.create(
            account_id=acct.account_id, person_id=301,
            event_key="leave.approved", channel=Channel.WHATSAPP,
            is_enabled=False,
        )
    emit("leave.approved", account_id=acct.account_id,
         recipients=[301], sync=True)
    with account_scope(acct.account_id):
        skipped = NotificationDelivery.objects.filter(
            status=DeliveryStatus.SKIPPED).count()
        assert skipped == 1, "التفضيل لم يُحترم"


@pytest.mark.django_db(transaction=True)
def test_notifications_isolated_between_accounts(acct, rls_enforced_late):
    """
    العزل يُفحص بدور التشغيل لا بالمالك — وإلا مرّ الاختبار بأمان
    زائف لأن hrm_app يتجاوز RLS.
    """
    from apps.notifications.bus import emit

    other = provision_account(
        slug="notif-other", display_name_ar="آخر",
        company_name_ar="شركة أخرى", is_sandbox=True,
    )
    NotificationTemplate.objects.create(
        account=None, event_key="leave.approved",
        channel=Channel.IN_APP, locale="ar", subject="س", body="ص",
    )
    emit("leave.approved", account_id=acct.account_id,
         recipients=[401], sync=True)

    rls_enforced_late()          # نبدّل الدور بعد التهيئة
    with account_scope(other.account_id):
        assert Notification.objects.count() == 0, "تسريب إشعارات بين الحسابات"


@pytest.mark.django_db(transaction=True)
def test_every_event_has_templates_in_all_locales():
    """كل حدث له قوالب بالثلاث لغات لكل قناة — وإلا إشعار بلا نص."""
    from apps.notifications.services.templates import (
        TEMPLATES, sync_default_templates,
    )
    sync_default_templates()
    missing = []
    for spec in EVENTS:
        if spec.key not in TEMPLATES:
            missing.append(f"{spec.key}: لا قالب إطلاقًا")
            continue
        for locale in LOCALES:
            for channel in spec.channels:
                if not NotificationTemplate.objects.filter(
                    account__isnull=True, event_key=spec.key,
                    channel=channel, locale=locale,
                ).exists():
                    missing.append(f"{spec.key}/{channel}/{locale}")
    assert not missing, "قوالب ناقصة:\n" + "\n".join(missing[:15])


@pytest.mark.django_db(transaction=True)
def test_templates_have_no_empty_bodies():
    """قالب بنص فارغ = إشعار بلا محتوى."""
    from apps.notifications.services.templates import sync_default_templates
    sync_default_templates()
    empty = list(NotificationTemplate.objects.filter(
        account__isnull=True, body="").values_list("event_key", flat=True))
    assert not empty, f"قوالب بلا نص: {empty}"
