import pytest
from pydantic import ValidationError

from app.schemas.agent_analysis import (
    AnalysisJobCreateRequest,
    AnalysisRecommendationsListData,
    AnalysisRecommendationsListResponse,
    RecommendationReviewRequest,
)


def test_analysis_job_request_accepts_window_in_range() -> None:
    payload = AnalysisJobCreateRequest(window_hours=24)
    assert payload.window_hours == 24

    payload = AnalysisJobCreateRequest(window_hours=168)
    assert payload.window_hours == 168


@pytest.mark.parametrize("bad_window", [1, 23, 169, 999])
def test_analysis_job_request_rejects_out_of_range_window(bad_window: int) -> None:
    with pytest.raises(ValidationError):
        AnalysisJobCreateRequest(window_hours=bad_window)


def test_recommendation_review_request_accepts_legacy_alias() -> None:
    payload = RecommendationReviewRequest.model_validate(
        {"status": "accepted", "reviewer_comment": "looks good"}
    )
    assert payload.review_comment == "looks good"


def test_recommendations_list_response_has_data_wrapper() -> None:
    payload = AnalysisRecommendationsListResponse(
        data=AnalysisRecommendationsListData(items=[], total=0, limit=20, offset=0)
    )
    assert payload.data.limit == 20
