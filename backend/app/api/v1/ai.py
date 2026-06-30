from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ValidationFailed
from app.models.user import User
from app.schemas.ai import AISearchRequest
from app.services.ai_search_service import AISearchService
from app.services.llm_client import LLMCallError, LLMNotConfiguredError
from app.utils.response import success

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/search")
def ai_search(
    payload: AISearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = AISearchService(db).ask(
            current_user=current_user,
            dataset_id=payload.dataset_id,
            index_id=payload.index_id,
            question=payload.question,
        )
    except LLMNotConfiguredError as exc:
        raise ValidationFailed("AI 服务未配置 API Key，请联系管理员") from exc
    except LLMCallError as exc:
        raise ValidationFailed(f"AI 服务调用失败：{exc}") from exc
    return success(result)
