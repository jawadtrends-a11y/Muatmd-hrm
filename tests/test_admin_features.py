"""
حرّاس إدارة المزايا من اللوحة (ق-125).

⚠️ **الحراسة من الكود لا من اللوحة**: ميزةٌ بلا حارس لا تصير
محروسة بضغطة زرّ، وادّعاؤها يبيع وهمًا.
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError, InternalError, ProgrammingError, transaction

from apps.accounts.models_billing import Feature, Plan, PlanFeature
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope


@pytest.mark.django_db
def test_catalog_seeds_guard_flags():
    """
    الكتالوج يزرع **الحراسة** — والقاعدة تحكم الباقي.

    فالاسم والوصف يُعدَّلان من اللوحة، والحراسة حقيقةٌ تقنية.
    """
    from apps.accounts.services.plans import sync_feature_registry

    f = Feature.objects.filter(feature_key="req_leave").first()
    assert f is not None
    assert f.is_implemented, "طلب الإجازة محروس في الكود"
    assert f.guarded_at, "وموضع حراسته موثَّق"

    # تعديل من اللوحة لا يُداس بالمزامنة
    f.name_ar = "اسمٌ من اللوحة"
    f.save(update_fields=["name_ar"])
    sync_feature_registry()
    f.refresh_from_db()
    assert f.name_ar == "اسمٌ من اللوحة", "المزامنة داست تعديل المشغّل"


@pytest.mark.django_db
def test_unguarded_features_are_known():
    """
    وما لا حارس له **معلومٌ لا مخفيّ** — فيُبنى أو يُحذف.

    وبقاؤه مجهولًا هو ما يجعل الباقة تبيع وهمًا.
    """
    unguarded = Feature.objects.filter(is_implemented=False)
    for f in unguarded:
        assert not f.guarded_at, (
            f"{f.feature_key}: بلا حراسة لكن له موضع — تناقض")


@pytest.mark.django_db(transaction=True)
def test_customer_cannot_write_features(rls_enforced_late):
    """
    ⚠️ العميل لا يكتب المزايا — ولو نادى المسار.

    فهي كتالوج المنصّة: يقرؤها الجميع، ويكتبها من لا سياق حساب له.
    """
    r = provision_account(slug="feat-w", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    rls_enforced_late()

    with account_scope(r.account_id):
        with pytest.raises((ProgrammingError, InternalError, IntegrityError)):
            with transaction.atomic():
                Feature.objects.create(
                    feature_key="sneaky_feature", module="x",
                    name_ar="مدسوسة", value_type="bool")

    assert not Feature.objects.filter(feature_key="sneaky_feature").exists()


@pytest.mark.django_db(transaction=True)
def test_platform_can_write_features(rls_enforced_late):
    """والمنصّة تكتبها — فبلا ذلك لا تُدار المزايا أصلًا."""
    rls_enforced_late()
    f = Feature.objects.create(
        feature_key="from_platform", module="other",
        name_ar="من اللوحة", value_type="bool")
    assert Feature.objects.filter(id=f.id).exists()


@pytest.mark.django_db
def test_every_plan_feature_key_is_registered():
    """
    ⚠️ **لا باقة تبيع مفتاحًا غير مسجّل**.

    فمفتاحٌ في باقةٍ بلا ميزةٍ تقابله يُباع ولا يُفحص — ويصير
    مجّانيًّا بالسهو.
    """
    known = set(Feature.objects.values_list("feature_key", flat=True))
    used = set(PlanFeature.objects.values_list("feature_key", flat=True))
    unknown = used - known
    assert not unknown, f"مفاتيح تُباع بلا ميزة: {sorted(unknown)}"
