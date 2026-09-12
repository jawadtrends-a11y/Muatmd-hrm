"""
حرّاس أنواع الطلبات المخصّصة (ق-142).

**الشركة تُنشئ نوع طلبٍ بحقوله** — فلا تنتظر منّا نوعًا لكل حاجة.

⚠️ **ولا أثر آليًّا له**: يُقدَّم ويُعتمد ويُوثَّق — فالأثر يحتاج
كودًا، وادّعاؤه يبيع وهمًا.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import (
    CustomRequestField, CustomRequestType, FieldKind, Request,
    RequestStatus)
from apps.leaves.services import custom_types as svc

TODAY = date.today()


@pytest.fixture
def env(db):
    from apps.payroll.models import PayComponent

    r = provision_account(slug="crt-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        p, _ = create_person(
            account=acc, first_name_ar="صالح", family_name_ar="البقمي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1022233388", mobile="0502223338")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="T-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("7000"))])

        t = CustomRequestType.objects.create(
            account=acc, company=comp, code="CAR",
            name_ar="طلب سيارة", daily_unique=True)
        for i, (key, label, kind, opts, req) in enumerate((
                ("work_date", "التاريخ", FieldKind.DATE, "", True),
                ("destination", "الوجهة", FieldKind.TEXT, "", True),
                ("car_type", "النوع", FieldKind.SELECT,
                 "سيدان,دفع رباعي", True),
                ("notes", "ملاحظات", FieldKind.TEXTAREA, "", False)), 1):
            CustomRequestField.objects.create(
                account=acc, company=comp, request_type=t,
                key=key, label_ar=label, kind=kind,
                options=opts, is_required=req, sort_order=i * 10)

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "type": t}


def _submit(env, payload, t=None):
    return svc.submit(employment=env["emp"],
                      request_type=t or env["type"], payload=payload)


def _ok(**over):
    return {"work_date": str(TODAY), "destination": "الرياض",
            "car_type": "سيدان", **over}


def test_arabic_key_is_refused(env):
    """
    ⚠️ **مفتاحٌ عربيّ أو بمسافة يكسر الحمولة**.

    فالمفاتيح تُقرأ برمجيًّا لا تُعرض.
    """
    with pytest.raises(svc.CustomTypeError):
        svc.validate_key("الوجهة")
    with pytest.raises(svc.CustomTypeError):
        svc.validate_key("car type")
    assert svc.validate_key("car_type") == "car_type"


def test_reserved_keys_are_refused(env):
    """
    ⚠️ **والمحجوز يصادم حقول الطلب الأساسية** — فيُفسد الحمولة.
    """
    for k in ("status", "request_type", "custom_type_code"):
        with pytest.raises(svc.CustomTypeError):
            svc.validate_key(k)


def test_work_date_is_not_reserved(env):
    """
    ⚠️ **و`work_date` ليس محجوزًا**: فهو المفتاح القياسيّ للتاريخ،
    وخاصّية «مرّة في اليوم» تقرؤه — فحجزُه يجعلها بلا سبيل.
    """
    assert svc.validate_key("work_date") == "work_date"


def test_required_fields_are_enforced(env):
    """والحقول الإلزامية تُطلَب بأسمائها."""
    with account_scope(env["account_id"]):
        with pytest.raises(svc.CustomTypeError) as e:
            _submit(env, {})
        assert "الوجهة" in str(e.value)


def test_select_is_bound_to_its_options(env):
    """
    ⚠️ **والقائمة تُقيَّد بخياراتها** — فقيمةٌ خارجها تُفسد
    التقارير.
    """
    with account_scope(env["account_id"]):
        with pytest.raises(svc.CustomTypeError) as e:
            _submit(env, _ok(car_type="طائرة"))
        assert "خارج الخيارات" in str(e.value)


def test_valid_submission_passes(env):
    """والصحيح يمرّ — ويحمل رمز نوعه."""
    with account_scope(env["account_id"]):
        out = _submit(env, _ok())
        req = out.request
        assert req.payload["custom_type_code"] == "CAR"
        assert req.payload["destination"] == "الرياض"


def test_daily_unique_blocks_a_second(env):
    """
    ⚠️ **ومرّةً في اليوم إن اشترطه النوع** — كقاعدة ق-134.
    """
    with account_scope(env["account_id"]):
        _submit(env, _ok())
        with pytest.raises(svc.CustomTypeError) as e:
            _submit(env, _ok(destination="جدة"))
        assert "بنفس التاريخ" in str(e.value)


def test_rejected_allows_resubmission(env):
    """والمرفوض لا يمنع — فالرفض قد يُصحَّح بعد تفاهم."""
    with account_scope(env["account_id"]):
        first = _submit(env, _ok()).request
        Request.objects.filter(id=first.id).update(
            status=RequestStatus.REJECTED)
        assert _submit(env, _ok(destination="جدة")) is not None


def test_next_day_is_allowed(env):
    """واليوم التالي يُطلب فيه."""
    with account_scope(env["account_id"]):
        _submit(env, _ok())
        assert _submit(env, _ok(
            work_date=str(TODAY - timedelta(days=1)))) is not None


def test_inactive_type_is_refused(env):
    """والمعطَّل لا يُقدَّم."""
    with account_scope(env["account_id"]):
        env["type"].is_active = False
        env["type"].save(update_fields=["is_active"])
        with pytest.raises(svc.CustomTypeError):
            _submit(env, _ok())


def test_attachment_is_enforced_when_required(env):
    """وما يلزمه مرفق لا يمرّ بلاه."""
    with account_scope(env["account_id"]):
        env["type"].requires_attachment = True
        env["type"].save(update_fields=["requires_attachment"])
        with pytest.raises(svc.CustomTypeError) as e:
            _submit(env, _ok())
        assert "مرفق" in str(e.value)
        assert _submit(env, _ok(attachment_url="/f/x.png")) is not None
