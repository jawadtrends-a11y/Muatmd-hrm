"""
مُرسِل إشعارات الجوال عبر Expo (ق-232).

- ⚠️ **دفعاتٌ من مئة** — حدّ Expo، ويوم المسير يُشعر الجميع معًا
- ⚠️ **انقطاع Expo عابر ← `PushTransient`** فتُعيد المهمّة المحاولة؛
  **ورفض الجهاز نهائيّ ← يُعطَّل** فلا يُعاد لجهازٍ حُذف منه التطبيق
- `EXPO_ACCESS_TOKEN` اختياريّ — يلزم إن فُعّل «أمان الدفع المعزَّز» في Expo
"""
import logging
import os
from dataclasses import dataclass, field

import requests
from django.utils import timezone

from apps.notifications.models_push import PushDevice

logger = logging.getLogger(__name__)

EXPO_URL = "https://exp.host/--/api/v2/push/send"
BATCH = 100
TOKEN_PREFIXES = ("ExponentPushToken[", "ExpoPushToken[")


class PushTransient(Exception):
    """عطلٌ عابر — تُعاد المحاولة."""


@dataclass
class PushResult:
    sent: int = 0
    failed: int = 0
    no_devices: bool = False
    ticket_ids: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def valid_token(token: str) -> bool:
    return bool(token) and len(token) <= 200 and token.startswith(TOKEN_PREFIXES)


def _post(messages):
    headers = {"Accept": "application/json",
               "Content-Type": "application/json"}
    tok = os.environ.get("EXPO_ACCESS_TOKEN", "")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    try:
        r = requests.post(EXPO_URL, json=messages, headers=headers, timeout=10)
    except requests.RequestException as e:
        raise PushTransient(str(e)) from e
    if r.status_code >= 500 or r.status_code == 429:
        raise PushTransient(f"Expo {r.status_code}")
    if r.status_code >= 400:
        return None, f"Expo {r.status_code}: {r.text[:200]}"
    return (r.json() or {}).get("data") or [], ""


def send_to_person(*, person_id, title, body, data=None) -> PushResult:
    res = PushResult()
    devices = list(PushDevice.objects.filter(person_id=person_id, is_active=True))
    if not devices:
        res.no_devices = True
        return res

    for i in range(0, len(devices), BATCH):
        chunk = devices[i:i + BATCH]
        messages = [{"to": d.token, "title": title[:120], "body": body[:500],
                     "data": data or {}, "sound": "default",
                     "priority": "high", "channelId": "default"}
                    for d in chunk]
        tickets, err = _post(messages)
        if tickets is None:
            res.failed += len(chunk)
            res.errors.append(err)
            continue
        for d, t in zip(chunk, tickets):
            if t.get("status") == "ok":
                res.sent += 1
                res.ticket_ids.append(t.get("id", ""))
                continue
            res.failed += 1
            code = (t.get("details") or {}).get("error", "")
            res.errors.append(code or t.get("message", "")[:120])
            if code == "DeviceNotRegistered":
                PushDevice.objects.filter(id=d.id).update(
                    is_active=False, deactivated_reason="رفضه Expo — حُذف التطبيق",
                    updated_at=timezone.now())
    return res
