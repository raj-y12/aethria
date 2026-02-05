"""
Router for web-front-end (public site): early access waitlist via Resend.
Included in main backend so one API serves both app and web frontends on a single domain.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import resend

# Load .env from project root (parent of backend/)
_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_root / ".env")

router = APIRouter(prefix="/api", tags=["web"])


class WaitlistRequest(BaseModel):
    name: str
    email: EmailStr
    role: str
    firm: str
    linkedin: str


@router.post("/waitlist")
def submit_waitlist(req: WaitlistRequest):
    """Submit early access form; sends notification via Resend."""
    api_key = os.getenv("RESEND_API_KEY")
    notify_to = os.getenv("AETHRIA_WAITLIST_NOTIFY_EMAIL", "delivered@resend.dev")
    if not api_key:
        raise HTTPException(status_code=503, detail="Email service not configured")

    resend.api_key = api_key
    linkedin_line = f'<li>LinkedIn: <a href="{req.linkedin}">{req.linkedin}</a></li>'
    html = (
        f"<p><strong>New early access signup</strong></p>"
        f"<ul>"
        f"<li>Name: {req.name}</li>"
        f"<li>Email: {req.email}</li>"
        f"<li>Role: {req.role}</li>"
        f"<li>Firm: {req.firm}</li>"
        f"{linkedin_line}"
        f"</ul>"
    )
    try:
        resend.Emails.send({
            "from": "Aethria <onboarding@resend.dev>",
            "to": [notify_to],
            "subject": f"Early access request: {req.name} ({req.firm})",
            "html": html,
        })
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {str(e)}")
    return {"ok": True}
