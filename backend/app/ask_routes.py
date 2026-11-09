from typing import Annotated

from fastapi import APIRouter, Depends, Request

from .ask_schemas import (AskRequest, AskResponse, ConfirmRequest, ConfirmResponse,
                          SwapRequest, SwapResponse)
from .planning import PlanningService
from .rate_limit import limit_ask
from .routes import User


def get_planner(request: Request) -> PlanningService:
    return request.app.state.planning_service


Planner = Annotated[PlanningService, Depends(get_planner)]
ask_router = APIRouter(prefix="/ask", tags=["Ask"])


@ask_router.post("", response_model=AskResponse, dependencies=[Depends(limit_ask)])
def ask(body: AskRequest, planner: Planner, x_user_id: User = "demo-user"):
    return planner.ask(body, x_user_id)


@ask_router.post("/plans/{plan_id}/confirm", response_model=ConfirmResponse)
def confirm(plan_id: str, planner: Planner, body: ConfirmRequest = ConfirmRequest(),
            x_user_id: User = "demo-user"):
    return planner.confirm(plan_id, body, x_user_id)


@ask_router.post("/plans/{plan_id}/swap", response_model=SwapResponse)
def swap(plan_id: str, body: SwapRequest, planner: Planner, x_user_id: User = "demo-user"):
    return planner.swap(plan_id, body, x_user_id)
