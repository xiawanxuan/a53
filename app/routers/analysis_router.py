from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.connection import get_mysql_session, get_timescale_session
from ..models import (
    ModalIdentificationTaskCreate,
    ModalIdentificationResponse,
)
from ..services import ModalIdentificationService
from ..middleware.response import api_response
from ..middleware.exceptions import BusinessException
from ..middleware.error_codes import ErrorCode

router = APIRouter(prefix="/api/v1/analysis", tags=["频域分析与模态辨识"])


@router.post("/modal", summary="执行模态辨识：FFT+峰检测+阻尼比拟合")
async def identify_modal(
    payload: ModalIdentificationTaskCreate,
    mysql_db: AsyncSession = Depends(get_mysql_session),
    timescale_db: AsyncSession = Depends(get_timescale_session),
):
    service = ModalIdentificationService(mysql_db, timescale_db)
    result: ModalIdentificationResponse = await service.identify_modal(
        ship_code=payload.ship_code,
        point_code=payload.point_code,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    return api_response(data=result.model_dump())


@router.get("/modal/{task_uuid}", summary="按任务UUID查询模态辨识结果")
async def get_modal_task(
    task_uuid: str,
    mysql_db: AsyncSession = Depends(get_mysql_session),
    timescale_db: AsyncSession = Depends(get_timescale_session),
):
    service = ModalIdentificationService(mysql_db, timescale_db)
    result = await service.get_task_result(task_uuid)
    if result is None:
        raise BusinessException(ErrorCode.TASK_NOT_FOUND)
    return api_response(data=result.model_dump())
