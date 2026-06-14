from fastapi import APIRouter, Depends, File, UploadFile, Form, Header
from fastapi.params import Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from ..database.connection import get_mysql_session, get_timescale_session
from ..models import WaveformUploadInit, WaveformUploadStatus
from ..services import WaveformIngestionService
from ..middleware.response import api_response

router = APIRouter(prefix="/api/v1/ingestion", tags=["波形数据接入"])


@router.post("/init", summary="初始化分段上传会话")
async def init_upload(
    payload: WaveformUploadInit,
    mysql_db: AsyncSession = Depends(get_mysql_session),
    timescale_db: AsyncSession = Depends(get_timescale_session),
):
    service = WaveformIngestionService(mysql_db, timescale_db)
    result = await service.init_upload_session(
        ship_code=payload.ship_code,
        point_code=payload.point_code,
        batch_id=payload.batch_id,
        total_segments=payload.total_segments,
        total_samples=payload.total_samples,
        sample_rate=payload.sample_rate,
        start_time=payload.start_time,
    )
    return api_response(data=result)


@router.post("/segment/{ship_code}/{point_code}", summary="上传单个波形分段二进制数据")
async def upload_segment(
    ship_code: str,
    point_code: str,
    batch_id: str = Form(..., description="上传批次ID"),
    segment_index: int = Form(..., ge=0, description="分段序号(从0开始)"),
    total_segments: int = Form(..., ge=1, description="总分段数"),
    sample_offset: int = Form(..., ge=0, description="该段第一个样本的全局偏移"),
    sample_count: int = Form(..., gt=0, description="该段样本数量"),
    start_time: datetime = Form(..., description="该段第一个样本时间戳"),
    sample_rate: float = Form(..., gt=0, description="采样率(Hz)"),
    byte_order: str = Form("little", description="字节序: little/big"),
    dtype: str = Form("float32", description="数据类型: float32/float64"),
    file: UploadFile = File(..., description="二进制波形数据文件"),
    mysql_db: AsyncSession = Depends(get_mysql_session),
    timescale_db: AsyncSession = Depends(get_timescale_session),
):
    binary_data = await file.read()
    service = WaveformIngestionService(mysql_db, timescale_db)
    result = await service.ingest_segment(
        ship_code=ship_code,
        point_code=point_code,
        batch_id=batch_id,
        segment_index=segment_index,
        total_segments=total_segments,
        sample_offset=sample_offset,
        sample_count=sample_count,
        start_time=start_time,
        sample_rate=sample_rate,
        binary_data=binary_data,
        byte_order=byte_order,
        dtype=dtype,
    )
    return api_response(data=result)


@router.get("/status/{batch_id}", summary="查询上传状态")
async def get_upload_status(
    batch_id: str,
    mysql_db: AsyncSession = Depends(get_mysql_session),
    timescale_db: AsyncSession = Depends(get_timescale_session),
):
    service = WaveformIngestionService(mysql_db, timescale_db)
    status: WaveformUploadStatus = await service.get_upload_status(batch_id)
    return api_response(data=status.model_dump())
