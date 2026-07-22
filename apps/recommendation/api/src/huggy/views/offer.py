import typing as t

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from huggy.database.session import get_db
from huggy.schemas.model_selection.model_configuration import RetrievalModelChoices
from huggy.views.common import check_token, get_call_id, setup_trace

offer_router = r = APIRouter(tags=["offer"])


@r.get(
    "/similar_offers/{offer_id}",
    dependencies=[Depends(setup_trace), Depends(check_token)],
)
async def get_similar_offers(
    offer_id: str,
    token: t.Optional[str] = None,
    latitude: t.Optional[float] = None,
    longitude: t.Optional[float] = None,
    user_id: t.Optional[str] = None,
    categories: t.Optional[list[str]] = Query(None),
    subcategories: t.Optional[list[str]] = Query(None),
    search_group_names: t.Optional[list[str]] = Query(None),
    retrieval_model: t.Optional[
        RetrievalModelChoices
    ] = RetrievalModelChoices.CORESERVATION,
    db: AsyncSession = Depends(get_db),
    call_id: str = Depends(get_call_id),
):
    return jsonable_encoder(
        {
            "results": [],
            "params": {
                "reco_origin": None,
                "model_origin": None,
                "call_id": call_id,
            },
        }
    )
