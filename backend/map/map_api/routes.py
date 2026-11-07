from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request

from .schemas import (CheckinRequest, CheckinResponse, CreateQuestRequest,
                      CreateQuestResponse, PlacesResponse, QuestsResponse)
from .seed import CAMPUS
from .services import MapService


def get_service(request: Request) -> MapService:
    return request.app.state.map_service


Service = Annotated[MapService, Depends(get_service)]
Latitude = Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)]
User = Annotated[str, Header(alias="X-User-Id", min_length=1, max_length=100)]

map_router = APIRouter(prefix="/map", tags=["Map"])
merchant_router = APIRouter(prefix="/merchant", tags=["Merchant"])


@map_router.get("/places", response_model=PlacesResponse)
def places(service: Service, lat: Latitude = CAMPUS["lat"], lng: Longitude = CAMPUS["lng"],
           walk_min: Annotated[int, Query(json_schema_extra={"enum": [5, 10, 15]})] = 10,
           categories: str = "coffee,lunch,groceries,free"):
    return service.places(lat, lng, walk_min, categories)


@map_router.get("/community-quests", response_model=QuestsResponse)
def community_quests(service: Service, lat: Latitude = CAMPUS["lat"], lng: Longitude = CAMPUS["lng"],
                     x_user_id: User = "demo-user"):
    return service.community_quests(lat, lng, x_user_id)


@map_router.post("/checkin", response_model=CheckinResponse)
def checkin(body: CheckinRequest, service: Service, x_user_id: User = "demo-user"):
    return service.checkin(body, x_user_id)


@merchant_router.post("/community-quests", status_code=201, response_model=CreateQuestResponse)
def create_quest(body: CreateQuestRequest, service: Service,
                 x_merchant_id: Annotated[str, Header(alias="X-Merchant-Id")] = "m_mamalin"):
    return service.create_quest(body, x_merchant_id)
