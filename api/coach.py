from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
import html

try:
    import markdown
    import bleach
except Exception:
    markdown = None
    bleach = None

try:
    from src.agents.agents_factory import run_agent_flow
except ImportError:
    run_agent_flow = None

router = APIRouter()

class CoachRequest(BaseModel):
    query: str

class CoachResponse(BaseModel):
    risk: str
    retrieved_count: int
    draft: str
    final: str
    details: Dict[str, Any] | None = None

@router.post("/", response_model=CoachResponse)
async def coach_endpoint(request: CoachRequest):
    if run_agent_flow is None:
        raise HTTPException(status_code=500, detail="run_agent_flow no disponible")
    try:
        out = run_agent_flow(request.query)
        # Convertir posible Markdown en HTML seguro para el frontend.
        def render_markdown_to_safe_html(text: str) -> str:
            if not text:
                return ''
            # Si disponemos de markdown, convertir; si no, usar texto tal cual.
            md_html = markdown.markdown(text, extensions=['extra']) if markdown else html.escape(text)
            # Si disponemos de bleach, sanitizar y linkify; si no, devolver HTML escapado
            if bleach:
                allowed_tags = set(bleach.sanitizer.ALLOWED_TAGS) | { 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'p', 'ul', 'ol', 'li', 'strong', 'em', 'del', 'code', 'pre', 'blockquote' }
                allowed_attrs = { 'a': ['href', 'title', 'rel'], 'img': ['src', 'alt'], 'code': ['class'] }
                cleaned = bleach.clean(md_html, tags=allowed_tags, attributes=allowed_attrs)
                cleaned = bleach.linkify(cleaned)
                return cleaned
            return md_html

        final_html = render_markdown_to_safe_html(out.get('final', ''))
        draft_text = out.get('draft', '') or ''
        return CoachResponse(
            risk=out.get('risk', 'medio'),
            retrieved_count=len(out.get('retrieved', [])),
            draft=draft_text,
            final=final_html,
            details={k: v for k, v in out.items() if k not in ('draft', 'final')}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
