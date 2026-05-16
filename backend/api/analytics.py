"""Analytics endpoints — profit analysis powered by Azure OpenAI."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.azure_openai import AzureOpenAIService
from backend.services.azure_openai_service import analyze_sku, generate_seller_insights
from backend.services.search import SearchService
from backend.processors.profit_calculator import compute_profit_summary

router = APIRouter()


class AnalyticsQuery(BaseModel):
    """Request body for the natural-language analytics endpoint."""

    query: str
    upload_id: int | None = None


class AnalyticsResponse(BaseModel):
    answer: str
    profit_summary: dict | None = None


@router.post("/query", response_model=AnalyticsResponse)
async def query_analytics(
    body: AnalyticsQuery,
    db: Session = Depends(get_db),
):
    """Answer a seller's natural-language question about their data."""
    # 1. Semantic search for relevant data chunks
    search_svc = SearchService()
    context_docs = search_svc.search(body.query)

    # 2. Optionally compute a profit summary from DB
    profit_summary = None
    if body.upload_id:
        profit_summary = compute_profit_summary(db, body.upload_id)

    # 3. Ask Azure OpenAI with retrieved context
    openai_svc = AzureOpenAIService()
    answer = openai_svc.chat(
        user_query=body.query,
        context_documents=context_docs,
        profit_summary=profit_summary,
    )

    return AnalyticsResponse(answer=answer, profit_summary=profit_summary)


@router.get("/summary/{upload_id}")
async def get_profit_summary(
    upload_id: int,
    db: Session = Depends(get_db),
):
    """Return a pre-computed profit summary for a given upload."""
    summary = compute_profit_summary(db, upload_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Upload not found")
    return summary


class InsightsRequest(BaseModel):
    """Settlement-data payload for the AI insight engine."""

    summary: dict
    skus: list[dict] = []
    ads_total_spend: float = 0.0


@router.post("/insights")
async def insights_endpoint(body: InsightsRequest):
    """Generate the 5-insight + health-score AI report for a parsed settlement."""
    return generate_seller_insights(body.model_dump())


@router.post("/sku-analysis")
async def sku_analysis_endpoint(sku: dict, ad_spend: float = 0.0):
    """Per-SKU verdict, pricing & ad-spend recommendation."""
    return analyze_sku(sku, ad_spend_for_sku=ad_spend)
