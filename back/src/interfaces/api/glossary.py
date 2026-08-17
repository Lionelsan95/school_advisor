"""API-10 / F9 — the glossary endpoint.

Pure static content: no database dependency at all, deliberately. A glossary
term does not vary by establishment or by request, and taking a connection
would suggest otherwise to the next reader of this file.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.interfaces.api.schemas import GlossaryOut

router = APIRouter(tags=["glossary"])


@router.get("/glossary", response_model=GlossaryOut)
def get_glossary() -> GlossaryOut:
    return GlossaryOut.of()
