from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.connection import get_mysql_session, get_timescale_session
from ..services import FFTAnalyzer, ModalIdentifier
from ..middleware.response import api_response

router = APIRouter(prefix="/api/v1/system", tags=["系统信息"])


@router.get("/health", summary="健康检查")
async def health_check():
    return api_response(data={"status": "ok"})


@router.get("/config/fft", summary="查看FFT分析超参数")
async def get_fft_config():
    analyzer = FFTAnalyzer()
    return api_response(data=analyzer.get_config())


@router.get("/config/modal", summary="查看模态辨识超参数")
async def get_modal_config():
    identifier = ModalIdentifier()
    return api_response(data=identifier.get_config())
