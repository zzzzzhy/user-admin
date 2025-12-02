from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.sms import send_verification_code, verify_code

router = APIRouter(prefix="/auth", tags=["sms"])


class SendSMSBody(BaseModel):
    phone: str


class VerifySMSBody(BaseModel):
    phone: str
    code: str


@router.post("/send_sms_code")
def send_sms_code(body: SendSMSBody):
    # phone format validation is handled elsewhere
    res = send_verification_code(body.phone)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("reason", "failed"))
    return {"message": "Code sent"}


# @router.post("/verify_sms_code")
# def verify_sms_code(body: VerifySMSBody):
#     ok = verify_code(body.phone, body.code)
#     if not ok:
#         raise HTTPException(status_code=400, detail="Invalid or expired code")
#     return {"message": "Phone verified"}
