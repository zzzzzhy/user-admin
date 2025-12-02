from __future__ import annotations

import random
import re
import time
from typing import Optional

from app.core.config import settings
from app.core.redis import get_redis
from app.core.sms_providers import get_provider


def _gen_code(length: int = 6) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def _phone_key(phone: str, suffix: str) -> str:
    return f"sms:{phone}:{suffix}"


def send_verification_code(phone: str) -> dict:
    # basic China phone validation: accept 11-digit mainland numbers or +86 prefixed
    def _normalize(p: str) -> str:
        p = p.replace(" ", "")
        if p.startswith("+86"):
            p = p[3:]
        if p.startswith("86") and len(p) > 11:
            p = p[2:]
        return p

    pnorm = _normalize(phone)
    if not re.match(r"^1[3-9]\d{9}$", pnorm):
        return {"ok": False, "reason": "Invalid China phone number"}

    # reject virtual numbers - common Chinese virtual number prefixes
    # 170, 171: China Unicom virtual numbers
    # 162, 165, 167: China Mobile virtual numbers
    # 166: China Unicom virtual numbers
    virtual_prefixes = {"170", "171", "162", "165", "167", "166"}
    if pnorm[:3] in virtual_prefixes:
        return {"ok": False, "reason": "Virtual numbers are not allowed"}
    r = get_redis()
    last_sent = r.get(_phone_key(pnorm, "last_sent"))
    now = int(time.time())
    if last_sent:
        last = int(last_sent)
        if now - last < settings.SMS_RATE_LIMIT_SECONDS:
            return {"ok": False, "reason": "Too many requests"}

    # hourly limit
    hour_key = _phone_key(pnorm, "hour_count")
    hour_count = r.get(hour_key)
    if hour_count and int(hour_count) >= settings.SMS_RATE_LIMIT_PER_HOUR:
        return {"ok": False, "reason": "Hourly limit exceeded"}

    code = _gen_code(settings.SMS_CODE_LENGTH)
    code_key = _phone_key(pnorm, "code")
    r.set(code_key, code, ex=settings.SMS_CODE_TTL_SECONDS)
    r.set(_phone_key(pnorm, "last_sent"), now)
    r.incr(hour_key)
    r.expire(hour_key, 3600)

    provider = get_provider()
    template = settings.ALIYUN_SMS_TEMPLATE_CODE or settings.TENCENT_SMS_TEMPLATE_ID or "default"
    sent = provider.send(phone=pnorm, template=template, params={"code": code})
    if not sent:
        return {"ok": False, "reason": "provider_failed"}
    return {"ok": True}


def verify_code(phone: str, code: str) -> bool:
    r = get_redis()
    # normalize like send
    if phone.startswith("+86"):
        phone = phone[3:]
    elif phone.startswith("86") and len(phone) > 11:
        phone = phone[2:]
    code_key = _phone_key(phone, "code")
    real = r.get(code_key)
    if not real:
        return False
    if real.decode() != code:
        r.delete(code_key)
        return False
    # mark verified for short time
    r.set(_phone_key(phone, "verified"), "1", ex=600)
    # delete code
    r.delete(code_key)
    return True


def is_verified(phone: str) -> bool:
    r = get_redis()
    v = r.get(_phone_key(phone, "verified"))
    return bool(v)
