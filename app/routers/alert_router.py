from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from ..database.connection import get_mysql_session
from ..models import AlertCallbackRecordResponse
from ..services import AlertCallbackService
from ..repository import (
    AlertCallbackRepository,
    ShipRepository,
    MeasuringPointRepository,
)
from ..middleware.response import api_response
from ..middleware.exceptions import BusinessException
from ..middleware.error_codes import ErrorCode

router = APIRouter(prefix="/api/v1/alerts", tags=["模态告警回调"])


@router.get("/callbacks", summary="查询回调推送记录")
async def list_callback_records(
    ship_code: Optional[str] = Query(None, description="船舶编号"),
    point_code: Optional[str] = Query(None, description="测点编号"),
    task_uuid: Optional[str] = Query(None, description="辨识任务UUID"),
    status: Optional[int] = Query(None, description="推送状态：0-待推送 1-成功 2-失败"),
    start_time: Optional[datetime] = Query(None, description="起始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    limit: int = Query(100, ge=1, le=1000, description="返回条数"),
    db: AsyncSession = Depends(get_mysql_session),
):
    repo = AlertCallbackRepository(db)

    ship_id = None
    point_id = None
    task_id = None

    if ship_code:
        ship_repo = ShipRepository(db)
        ship = await ship_repo.get_by_code(ship_code)
        if not ship:
            raise BusinessException(ErrorCode.SHIP_NOT_FOUND)
        ship_id = ship.id

        if point_code:
            point_repo = MeasuringPointRepository(db)
            point = await point_repo.get_by_code(ship.id, point_code)
            if not point:
                raise BusinessException(ErrorCode.POINT_NOT_FOUND)
            point_id = point.id

    if task_uuid:
        from ..repository import TaskRepository
        task_repo = TaskRepository(db)
        task = await task_repo.get_by_uuid(task_uuid)
        if not task:
            raise BusinessException(ErrorCode.TASK_NOT_FOUND)
        task_id = task.id

    records = await repo.list_records(
        ship_id=ship_id,
        point_id=point_id,
        task_id=task_id,
        status=status,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

    data = [
        AlertCallbackRecordResponse.model_validate(r).model_dump()
        for r in records
    ]
    return api_response(data=data)


@router.get("/callbacks/{callback_uuid}", summary="按UUID查询单条回调记录详情")
async def get_callback_record(
    callback_uuid: str,
    db: AsyncSession = Depends(get_mysql_session),
):
    repo = AlertCallbackRepository(db)
    record = await repo.get_by_uuid(callback_uuid)
    if not record:
        raise BusinessException(ErrorCode.PARAM_INVALID, "回调记录不存在")
    return api_response(
        data=AlertCallbackRecordResponse.model_validate(record).model_dump()
    )


@router.get("/config", summary="查看告警回调配置和阈值")
async def get_alert_config(
    db: AsyncSession = Depends(get_mysql_session),
):
    service = AlertCallbackService(db)
    return api_response(data=service.get_config())
