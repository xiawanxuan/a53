import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .config.settings import settings
from .middleware.error_handler import ErrorHandlerMiddleware
from .middleware.validation import ValidationMiddleware
from .routers import (
    ship_router,
    ingestion_router,
    analysis_router,
    query_router,
    system_router,
)
from .logging_config.logger import setup_logger

load_dotenv()
setup_logger()

app = FastAPI(
    title="船舶运维平台 - 振动分析服务",
    description="""
船舶机舱多路振动传感器数据采集与分析后端服务。

## 功能特性
- **波形数据接入**: 分段上传二进制振动波形，高并发批量写入TimescaleDB时序库
- **FFT频域分析**: Welch方法功率谱密度估计，支持多种窗函数
- **模态辨识算法**: 自动共振峰检测，半功率带宽法/洛伦兹曲线拟合估计阻尼比
- **多维度查询**: 按船舶编号、测点、航行时间段查询原始波形与模态结果
- **异常留存**: 辨识失败时自动保存原始波形用于复现调试
- **统一错误码**: 所有接口返回标准化响应格式

## 数据存储
- **TimescaleDB**: 振动波形时序数据
- **MySQL**: 船舶、测点台账与辨识任务/结果
    """,
    version="1.0.0",
    contact={"name": "船舶运维平台团队"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(ValidationMiddleware)

app.include_router(ship_router)
app.include_router(ingestion_router)
app.include_router(analysis_router)
app.include_router(query_router)
app.include_router(system_router)


@app.get("/", tags=["根路径"])
async def root():
    return {
        "service": "船舶运维平台 - 振动分析服务",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.env == "development",
        log_level=settings.app.log_level.lower(),
    )
