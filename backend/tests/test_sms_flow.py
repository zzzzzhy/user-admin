import time

import pytest

from app.core import sms as sms_core
from app.core.sms_providers import MockSMSProvider, get_provider


def test_mock_provider_is_default():
    provider = get_provider()
    assert isinstance(provider, MockSMSProvider)


def test_send_and_verify(tmp_path, monkeypatch):
    # Use a real Redis instance if available; otherwise, monkeypatch get_redis to a fake dict-like
    store = {}

    class FakeRedis:
        def __init__(self):
            self._s = store

        def get(self, k):
            v = self._s.get(k)
            if v is None:
                return None
            if isinstance(v, int):
                return str(v).encode()
            return v.encode() if isinstance(v, str) else v

        def set(self, k, v, ex=None):
            self._s[k] = v

        def incr(self, k):
            self._s[k] = int(self._s.get(k, 0)) + 1

        def expire(self, k, t):
            pass

        def delete(self, k):
            self._s.pop(k, None)

    monkeypatch.setattr("app.core.redis.get_redis", lambda: FakeRedis())

    phone = "+8613711112222"
    # send code
    res = sms_core.send_verification_code(phone)
    assert res["ok"]

    # attempt to send again immediately -> rate limited
    res2 = sms_core.send_verification_code(phone)
    assert not res2["ok"]

    # simulate time passing for rate limit
    time.sleep(1)

    # read code from fake store
    # the code is stored under sms:{phone}:code normalized
    normalized = "13711112222"
    code_key = f"sms:{normalized}:code"
    code = store.get(code_key)
    assert code is not None

    # verify
    ok = sms_core.verify_code(phone, code)
    assert ok

    # verify again should fail (code deleted)
    ok2 = sms_core.verify_code(phone, code)
    assert not ok2


@pytest.mark.parametrize("bad_phone", ["123", "+8617012345678", "8617012345678"])
def test_bad_numbers(bad_phone, monkeypatch):
    # ensure redis is faked
    monkeypatch.setattr("app.core.redis.get_redis", lambda: type("F", (), {"get": lambda *_: None, "set": lambda *_: None, "incr": lambda *_: None, "expire": lambda *_: None, "delete": lambda *_: None})())
    res = sms_core.send_verification_code(bad_phone)
    assert not res["ok"]
