"""
تسجيل جهاز الجوال وإلغاؤه (ق-232).

POST   /api/me/devices/  {token, platform, app_version} — عند الدخول
DELETE /api/me/devices/  {token}                        — عند الخروج

⚠️ **والخروج يُعطّل لا يحذف**: فلا تصل إشعارات موظفٍ لجوالٍ خرج منه.
⚠️ **والجهاز ينتقل لمن دخل به**: جوالٌ سلّمه موظفٌ لزميله يصل صاحبَه الجديد.
"""
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notifications.models_push import DevicePlatform, PushDevice
from apps.notifications.services.push import valid_token


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def my_devices(request):
    person = getattr(request.user, "person", None)
    if person is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)
    token = str(request.data.get("token") or "").strip()
    if not valid_token(token):
        return Response({"detail": "رمز الجهاز غير صالح"}, status=400)
    now = timezone.now()

    if request.method == "DELETE":
        n = PushDevice.objects.filter(token=token, person_id=person.id,
                                      is_active=True).update(
            is_active=False, deactivated_reason="خروج من التطبيق",
            updated_at=now)
        return Response({"deactivated": n})

    platform = request.data.get("platform")
    if platform not in DevicePlatform.values:
        return Response({"detail": "المنصّة غير معروفة"}, status=400)
    version = str(request.data.get("app_version") or "")[:20]

    dev = PushDevice.objects.filter(account_id=person.account_id,
                                    token=token).first()
    if dev is None:
        dev = PushDevice.objects.create(
            account_id=person.account_id, person_id=person.id, token=token,
            platform=platform, app_version=version, last_seen_at=now)
        return Response({"device_id": dev.id}, status=201)

    dev.person_id = person.id
    dev.platform, dev.app_version = platform, version
    dev.is_active, dev.deactivated_reason = True, ""
    dev.last_seen_at = now
    dev.save()
    return Response({"device_id": dev.id})
