from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from ..database.connection import get_mysql_session, get_timescale_session
from ..models import WaveformQueryRequest, ModalQueryRequest
from ..services import QueryService
from ..middleware.response import api_response

router = APIRouter(prefix="/api/v1/query", tags=["多维度数据查询"])


@router.get("/waveform", summary="按船舶、测点、时间段查询原始波形")
async def query_waveform(
    ship_code: str = Query(..., description="船舶编号"),
    point_code: str = Query(..., description="测点编号"),
    start_time: datetime = Query(..., description="起始时间"),
    end_time: datetime = Query(..., description="结束时间"),
    max_points: Optional[int] = Query(None, gt=0, description="最大返回点数"),
    mysql_db: AsyncSession = Depends(get_mysql_session),
    timescale_db: AsyncSession = Depends(get_timescale_session),
):
    service = QueryService(mysql_db, timescale_db)
    result = await service.query_waveform(
        ship_code=ship_code,
        point_code=point_code,
        start_time=start_time,
        end_time=end_time,
        max_points=max_points,
    )
    return api_response(data=result.model_dump())


@router.get("/modal/tasks", summary="按船舶、测点、时间段查询辨识任务列表")
async def list_modal_tasks(
    ship_code: Optional[str] = Query(None, description="船舶编号"),
    point_code: Optional[str] = Query(None, description="测点编号"),
    start_time: Optional[datetime] = Query(None, description="起始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    mysql_db: AsyncSession = Depends(get_mysql_session),
    timescale_db: AsyncSession = Depends(get_timescale_session),
):
    service = QueryService(mysql_db, timescale_db)
    result = await service.list_modal_tasks(
        ship_code=ship_code,
        point_code=point_code,
        start_time=start_time,
        end_time=end_time,
    )
    return api_response(data=result)


@router.get("/modal/tasks/{task_uuid}", summary="按任务UUID查询模态辨识结果详情")
async def get_modal_result(
    task_uuid: str,
    mysql_db: AsyncSession = Depends(get_mysql_session),
    timescale_db: AsyncSession = Depends(get_timescale_session),
):
    service = QueryService(mysql_db, timescale_db)
    result = await service.get_modal_result(task_uuid)
    return api_response(data=result.model_dump() if result else None)
