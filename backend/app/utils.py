import asyncio
import base64
import hashlib
import logging
import os
import random
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from typing import Any

import emails  # type: ignore
import httpx
import jwt
from jinja2 import Template
from jwt.exceptions import InvalidTokenError

from app.core import security
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EmailData:
    html_content: str
    subject: str


def render_email_template(*, template_name: str, context: dict[str, Any]) -> str:
    template_str = (
        Path(__file__).parent / "email-templates" / "build" / template_name
    ).read_text()
    html_content = Template(template_str).render(context)
    return html_content


def send_email(
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    assert settings.emails_enabled, "no provided configuration for email variables"
    message = emails.Message(
        subject=subject,
        html=html_content,
        mail_from=(settings.EMAILS_FROM_NAME, settings.EMAILS_FROM_EMAIL),
    )
    smtp_options = {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT}
    if settings.SMTP_TLS:
        smtp_options["tls"] = True
    elif settings.SMTP_SSL:
        smtp_options["ssl"] = True
    if settings.SMTP_USER:
        smtp_options["user"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        smtp_options["password"] = settings.SMTP_PASSWORD
    response = message.send(to=email_to, smtp=smtp_options)
    logger.info(f"send email result: {response}")


def generate_test_email(email_to: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Test email"
    html_content = render_email_template(
        template_name="test_email.html",
        context={"project_name": settings.PROJECT_NAME, "email": email_to},
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_reset_password_email(email_to: str, email: str, token: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Password recovery for user {email}"
    link = f"{settings.FRONTEND_HOST}/reset-password?token={token}"
    html_content = render_email_template(
        template_name="reset_password.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email_to,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_new_account_email(
    email_to: str, username: str, password: str
) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - New account for user {username}"
    html_content = render_email_template(
        template_name="new_account.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": username,
            "password": password,
            "email": email_to,
            "link": settings.FRONTEND_HOST,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_password_reset_token(email: str) -> str:
    delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.now(timezone.utc)
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email},
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )
    return encoded_jwt


def verify_password_reset_token(token: str) -> str | None:
    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        return str(decoded_token["sub"])
    except InvalidTokenError:
        return None


def generate_saas_email(  saasUrl: str, user: str, password: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - email for SaaS Test signup"
    emailText = f"""
    saas网址: {saasUrl}
    用户名: {user}
    密码: {password}
    """
    html_content = render_email_template(
        template_name="saas_signup.html",
        context={
            "emailText": emailText,
            "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_app_key() -> str:
    """
    生成 APP_KEY

    生成 32 字节的随机数据，并转换为 base64 格式

    Returns:
        以 'base64:' 前缀开头的 base64 编码字符串
    """
    try:
        # 生成 32 字节的随机数据
        random_bytes = secrets.token_bytes(32)
        # 转换为 base64 格式
        return "base64:" + base64.b64encode(random_bytes).decode("utf-8")
    except Exception as error:
        logger.error(f"Error generating APP_KEY: {error}")
        raise

def send_deploy_request(email: str, phone: str, password: str) -> dict[str, str]:
    """
    处理 Kubernetes 部署

    Args:
        email: 用户邮箱
        custom_app_id: 自定义的应用 ID

    Returns:
        包含部署信息的字典
    """
    try:
        access_token = os.getenv("TOKEN")
        combined_string = email + phone
        app_id = hashlib.md5(combined_string.encode()).hexdigest()[:8]
        namespace_name = f"dootask-{app_id}"

        # 生成 APP_KEY
        app_key = generate_app_key()

        db_password = password
        db_root_password = password

        ks_api_server = os.getenv("KS_API_SERVER")

        for index in range(3):
            try:
                run_response = httpx.post(
                    f"{ks_api_server}/api/v1/workflows/argo-workflows/submit",
                    json={
                        "namespace": "argo-workflows",
                        "resourceKind": "WorkflowTemplate",
                        "resourceName": "dootask-k8s-test-deploy",
                        "submitOptions": {
                            "entryPoint": "dootask-auto-deploy",
                            "parameters": [
                                "git-url=https://github.com/innet8/dootask-k8s.git",
                                "git-branch=main",
                                "tag=pro",
                                f"db-password={db_password}",
                                f"db-root-password={db_root_password}",
                                f"app-key={app_key}",
                                f"app-id={app_id}",
                                f"namespace={namespace_name}",
                            ],
                            "labels": "submit-from-ui=false",
                        },
                    },
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=5.0,
                )

                if run_response.status_code == 200:
                    break
                else:
                    time.sleep(3)
            except httpx.RequestError as exc:
                logger.error(f"Kubernetes deployment request error: {exc}")
                if index < 2:
                    time.sleep(3)
                else:
                    raise
        email_data = generate_saas_email(
            saasUrl=f"https://{app_id}.dootask.top", user="admin@dootask.com", password=password
        )
        send_email(
            email_to=email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
        return {
            "dbPassword": db_password,
            "dbRootPassword": db_root_password,
            "appId": app_id,
            "appKey": app_key,
            "namespaceName": namespace_name,
        }
    except Exception as error:
        logger.error(f"Kubernetes deployment error: {error}")
        raise
