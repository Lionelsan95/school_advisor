"""Version token for static editorial content that can affect responses."""

from __future__ import annotations

from hashlib import sha256

from src.domain import assistant_content, explanatory_content


def editorial_content_version() -> str:
    """Change whenever approved response content or its versions change."""

    explanatory_versions = ",".join(
        f"{content_id}:{content.version}"
        for content_id, content in sorted(explanatory_content.CONTENT_BY_ID.items())
    )
    scope_digest = sha256(explanatory_content.SCOPE_DISCLAIMER.encode()).hexdigest()
    return (
        f"assistant:{assistant_content.ASSISTANT_CONTENT_VERSION}|"
        f"explanatory:{explanatory_versions}|scope:{scope_digest}"
    )
