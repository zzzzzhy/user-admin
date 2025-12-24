from __future__ import annotations

from typing import Any
import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)


class SMSRetryableError(Exception):
    """Raised when an error is transient and the send should be retried."""


class SMSPermanentError(Exception):
    """Raised when an error is permanent and should not be retried."""



class BaseSMSProvider:
    def send(self, phone: str, template: str, params: dict[str, Any]) -> bool:
        raise NotImplementedError()


class MockSMSProvider(BaseSMSProvider):
    def send(self, phone: str, template: str, params: dict[str, Any]) -> bool:
        # For local/dev: log and pretend success
        logger.info("[MockSMS] send to %s template=%s params=%s", phone, template, params)
        return True


class AliyunSMSProvider(BaseSMSProvider):
    """Aliyun SMS provider using alibabacloud_dysmsapi20180501 SDK.

    Expects settings.ALIYUN_ACCESS_KEY_ID and ALIYUN_ACCESS_KEY_SECRET to be set.
    Official docs: https://github.com/aliyun/alibabacloud-python-sdk/blob/master/dysmsapi-20180501/
    """

    def __init__(self) -> None:
        self.access_key = settings.ALIYUN_ACCESS_KEY_ID
        self.access_secret = settings.ALIYUN_ACCESS_KEY_SECRET
        self.sign_name = settings.ALIYUN_SMS_SIGN_NAME
        self.template_code = settings.ALIYUN_SMS_TEMPLATE_CODE

        if not (self.access_key and self.access_secret and self.sign_name and self.template_code):
            logger.warning("Aliyun SMS credentials or config missing; provider will fail until configured")

        # Lazy import to avoid requiring SDK at import-time when not used
        try:
            from alibabacloud_tea_openapi import models as open_api_models  # type: ignore
            from alibabacloud_dysmsapi20180501.client import Client  # type: ignore
            from alibabacloud_dysmsapi20180501 import models as dysmsapi_models  # type: ignore
        except Exception:  # pragma: no cover - import may fail in environments without SDK
            open_api_models = None  # type: ignore
            Client = None  # type: ignore
            dysmsapi_models = None  # type: ignore

        self._open_api_models = open_api_models
        self._Client = Client
        self._dysmsapi_models = dysmsapi_models

    def send(self, phone: str, template: str, params: dict[str, Any]) -> bool:
        if not (self.access_key and self.access_secret):
            logger.error("Aliyun credentials not configured")
            return False
        if not (self._open_api_models and self._Client and self._dysmsapi_models):
            logger.error("Aliyun SDK not installed (alibabacloud_dysmsapi20180501 required)")
            return False

        @retry(
            stop=stop_after_attempt(settings.SMS_SEND_MAX_RETRIES),
            wait=wait_exponential(multiplier=settings.SMS_SEND_BACKOFF_SECONDS, min=1, max=30),
            retry=retry_if_exception_type(SMSRetryableError),
            reraise=True,
        )
        def _do_send():
            try:
                # Initialize client with config
                config = self._open_api_models.Config(
                    access_key_id=self.access_key,
                    access_key_secret=self.access_secret,
                )
                config.endpoint = "dysmsapi.aliyuncs.com"
                client = self._Client(config)

                # Build SendSms request
                send_sms_request = self._dysmsapi_models.SendSmsRequest(
                    phone_numbers=phone,
                    sign_name=self.sign_name,
                    template_code=template or self.template_code,
                    template_param=json.dumps(params, ensure_ascii=False),
                )

                # Execute request
                resp = client.send_sms(send_sms_request)

                # Parse response
                code = resp.code if resp else None
                msg = resp.message if resp else None

                # Try to interpret provider response
                if code and str(code).upper() != "OK":
                    # Aliyun uses transient error codes like isv.BUSINESS_LIMIT_CONTROL
                    if str(code).startswith("isv") or "LIMIT" in str(code).upper() or "THROTTLE" in str(code).upper():
                        raise SMSRetryableError(f"Aliyun transient error: {code} - {msg}")
                    raise SMSPermanentError(f"Aliyun permanent error: {code} - {msg}")
                logger.debug("Aliyun SMS response: code=%s message=%s", code, msg)
                return True
            except SMSPermanentError:
                raise
            except Exception as exc:  # pragma: no cover - runtime error handling
                # treat network/unknown errors as retryable
                logger.exception("Aliyun SMS send failed (will be retried if attempts remain): %s", exc)
                raise SMSRetryableError(str(exc))

        try:
            return _do_send()
        except RetryError as re:  # tenacity's wrapper when all retries failed
            logger.error("Aliyun SMS send ultimately failed after retries: %s", re)
            return False
        except SMSPermanentError as pe:
            logger.error("Aliyun SMS permanent failure: %s", pe)
            return False


class TencentSMSProvider(BaseSMSProvider):
    """Tencent Cloud SMS provider using tencentcloud-sdk-python.

    Expects TENCENT_SECRET_ID, TENCENT_SECRET_KEY, TENCENT_SMS_SDK_APP_ID,
    TENCENT_SMS_SIGN_NAME and TENCENT_SMS_TEMPLATE_ID to be set.
    Uses SMS API v20210111.
    Official docs: https://www.tencentcloud.com/zh/document/product/382/40606
    """

    def __init__(self) -> None:
        self.secret_id = settings.TENCENT_SECRET_ID
        self.secret_key = settings.TENCENT_SECRET_KEY
        self.sdk_app_id = settings.TENCENT_SMS_SDK_APP_ID
        self.sign_name = settings.TENCENT_SMS_SIGN_NAME
        self.template_id = settings.TENCENT_SMS_TEMPLATE_ID

        if not (self.secret_id and self.secret_key and self.sdk_app_id and self.sign_name and self.template_id):
            logger.warning("Tencent SMS credentials or config missing; provider will fail until configured")

        try:
            from tencentcloud.common import credential  # type: ignore
            from tencentcloud.sms.v20210111 import sms_client, models  # type: ignore
            from tencentcloud.common.profile.client_profile import ClientProfile  # type: ignore
            from tencentcloud.common.profile.http_profile import HttpProfile  # type: ignore
        except Exception:  # pragma: no cover
            credential = None  # type: ignore
            sms_client = None  # type: ignore
            models = None  # type: ignore
            ClientProfile = None  # type: ignore
            HttpProfile = None  # type: ignore

        self._credential = credential
        self._sms_client_module = sms_client
        self._models = models
        self._ClientProfile = ClientProfile
        self._HttpProfile = HttpProfile

    def send(self, phone: str, template: str, params: dict[str, Any]) -> bool:
        if not (self.secret_id and self.secret_key and self.sdk_app_id and self.sign_name):
            logger.error("Tencent credentials not configured")
            return False
        if not (self._credential and self._sms_client_module and self._models):
            logger.error("Tencent SDK not installed (tencentcloud-sdk-python required)")
            return False

        @retry(
            stop=stop_after_attempt(settings.SMS_SEND_MAX_RETRIES),
            wait=wait_exponential(multiplier=settings.SMS_SEND_BACKOFF_SECONDS, min=1, max=30),
            retry=retry_if_exception_type(SMSRetryableError),
            reraise=True,
        )
        def _do_send():
            try:
                # Initialize credential
                cred = self._credential.Credential(self.secret_id, self.secret_key)

                # Optional: Configure HTTP profile for custom settings
                http_profile = self._HttpProfile() if self._HttpProfile else None
                client_profile = self._ClientProfile() if self._ClientProfile else None
                if http_profile and client_profile:
                    http_profile.endpoint = "sms.tencentcloudapi.com"
                    client_profile.http_profile = http_profile

                # Initialize SMS client (region: ap-guangzhou for mainland China)
                if client_profile:
                    client = self._sms_client_module.SmsClient(cred, "ap-guangzhou", client_profile)
                else:
                    client = self._sms_client_module.SmsClient(cred, "ap-guangzhou")

                # Build SendSms request
                req = self._models.SendSmsRequest()
                req.PhoneNumberSet = [phone]
                req.SmsSdkAppId = str(self.sdk_app_id)
                req.SignName = self.sign_name
                req.TemplateId = template or self.template_id
                # TemplateParamSet expects a list of strings
                if isinstance(params, dict) and "code" in params:
                    req.TemplateParamSet = [str(params["code"])]
                else:
                    req.TemplateParamSet = [json.dumps(params, ensure_ascii=False)]

                # Execute request
                resp = client.SendSms(req)
                logger.debug("Tencent SMS request: %s", resp)
                # Parse response
                if resp and resp.SendStatusSet:
                    send_status = resp.SendStatusSet[0]
                    code = send_status.Code
                    msg = send_status.Message if hasattr(send_status, "Message") else None

                    # Interpret provider response
                    if code and str(code).upper() not in ("OK", "Success", "000000"):
                        # Transient errors: limit exceeded, service throttled, etc.
                        if str(code).startswith("isv") or "LIMIT" in str(code).upper() or "THROTTLE" in str(code).upper():
                            raise SMSRetryableError(f"Tencent transient error: {code} - {msg}")
                        raise SMSPermanentError(f"Tencent permanent error: {code} - {msg}")

                logger.debug("Tencent SMS response: RequestId=%s", resp.RequestId if resp else None)
                return True
            except SMSPermanentError:
                raise
            except Exception as exc:  # pragma: no cover
                logger.exception("Tencent SMS send failed (will be retried if attempts remain): %s", exc)
                raise SMSRetryableError(str(exc))

        try:
            return _do_send()
        except RetryError as re:
            logger.error("Tencent SMS send ultimately failed after retries: %s", re)
            return False
        except SMSPermanentError as pe:
            logger.error("Tencent SMS permanent failure: %s", pe)
            return False


def get_provider() -> BaseSMSProvider:
    if settings.SMS_PROVIDER == "aliyun":
        return AliyunSMSProvider()
    if settings.SMS_PROVIDER == "tencent":
        return TencentSMSProvider()
    return MockSMSProvider()
