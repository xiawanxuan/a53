from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ..database.connection import get_mysql_session
from ..models import ShipCreate, ShipResponse, MeasuringPointCreate, MeasuringPointResponse
from ..repository import ShipRepository, MeasuringPointRepository
from ..middleware.response import api_response
from ..middleware.exceptions import BusinessException
from ..middleware.error_codes import ErrorCode

router = APIRouter(prefix="/api/v1/ships", tags=["船舶与测点管理"])


@router.get("", summary="获取船舶列表")
async def list_ships(
    db: AsyncSession = Depends(get_mysql_session),
):
    repo = ShipRepository(db)
    from sqlalchemy import select
    from ..models import Ship
    result = await db.execute(select(Ship).where(Ship.status == 1))
    ships = list(result.scalars().all())
    data = [ShipResponse.model_validate(s).model_dump() for s in ships]
    return api_response(data=data)


@router.get("/{ship_code}", summary="获取船舶信息")
async def get_ship(
    ship_code: str,
    db: AsyncSession = Depends(get_mysql_session),
):
    repo = ShipRepository(db)
    ship = await repo.get_by_code(ship_code)
    if not ship:
        raise BusinessException(ErrorCode.SHIP_NOT_FOUND)
    return api_response(data=ShipResponse.model_validate(ship).model_dump())


@router.post("", summary="创建船舶")
async def create_ship(
    payload: ShipCreate,
    db: AsyncSession = Depends(get_mysql_session),
):
    repo = ShipRepository(db)
    existing = await repo.get_by_code(payload.ship_code)
    if existing:
        raise BusinessException(ErrorCode.PARAM_INVALID, "船舶编号已存在")
    ship = await repo.create(payload.model_dump())
    await db.commit()
    return api_response(data=ShipResponse.model_validate(ship).model_dump())


@router.get("/{ship_code}/points", summary="获取船舶测点列表")
async def list_points(
    ship_code: str,
    db: AsyncSession = Depends(get_mysql_session),
):
    ship_repo = ShipRepository(db)
    ship = await ship_repo.get_by_code(ship_code)
    if not ship:
        raise BusinessException(ErrorCode.SHIP_NOT_FOUND)

    point_repo = MeasuringPointRepository(db)
    points = await point_repo.list_by_ship(ship.id)
    data = [MeasuringPointResponse.model_validate(p).model_dump() for p in points]
    return api_response(data=data)


@router.get("/{ship_code}/points/{point_code}", summary="获取测点信息")
async def get_point(
    ship_code: str,
    point_code: str,
    db: AsyncSession = Depends(get_mysql_session),
):
    ship_repo = ShipRepository(db)
    ship = await ship_repo.get_by_code(ship_code)
    if not ship:
        raise BusinessException(ErrorCode.SHIP_NOT_FOUND)

    point_repo = MeasuringPointRepository(db)
    point = await point_repo.get_by_code(ship.id, point_code)
    if not point:
        raise BusinessException(ErrorCode.POINT_NOT_FOUND)
    return api_response(data=MeasuringPointResponse.model_validate(point).model_dump())


@router.post("/{ship_code}/points", summary="创建测点")
async def create_point(
    ship_code: str,
    payload: MeasuringPointCreate,
    db: AsyncSession = Depends(get_mysql_session),
):
    ship_repo = ShipRepository(db)
    ship = await ship_repo.get_by_code(ship_code)
    if not ship:
        raise BusinessException(ErrorCode.SHIP_NOT_FOUND)

    point_repo = MeasuringPointRepository(db)
    existing = await point_repo.get_by_code(ship.id, payload.point_code)
    if existing:
        raise BusinessException(ErrorCode.PARAM_INVALID, "测点编号已存在")

    data = payload.model_dump()
    data["ship_id"] = ship.id
    point = await point_repo.create(data)
    await db.commit()
    return api_response(data=MeasuringPointResponse.model_validate(point).model_dump())
