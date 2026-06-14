from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Ship, MeasuringPoint
from ..middleware.exceptions import BusinessException
from ..middleware.error_codes import ErrorCode
from ..logging_config.logger import logger


class ShipRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_code(self, ship_code: str) -> Optional[Ship]:
        result = await self.db.execute(
            select(Ship).where(Ship.ship_code == ship_code, Ship.status == 1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, ship_id: int) -> Optional[Ship]:
        result = await self.db.execute(
            select(Ship).where(Ship.id == ship_id)
        )
        return result.scalar_one_or_none()

    async def create(self, ship_data: dict) -> Ship:
        ship = Ship(**ship_data)
        self.db.add(ship)
        await self.db.flush()
        logger.info(f"Created ship: {ship.ship_code}")
        return ship


class MeasuringPointRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_code(self, ship_id: int, point_code: str) -> Optional[MeasuringPoint]:
        result = await self.db.execute(
            select(MeasuringPoint).where(
                MeasuringPoint.ship_id == ship_id,
                MeasuringPoint.point_code == point_code,
                MeasuringPoint.status == 1,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, point_id: int) -> Optional[MeasuringPoint]:
        result = await self.db.execute(
            select(MeasuringPoint).where(MeasuringPoint.id == point_id)
        )
        return result.scalar_one_or_none()

    async def list_by_ship(self, ship_id: int) -> list:
        result = await self.db.execute(
            select(MeasuringPoint).where(
                MeasuringPoint.ship_id == ship_id,
                MeasuringPoint.status == 1,
            )
        )
        return list(result.scalars().all())

    async def create(self, point_data: dict) -> MeasuringPoint:
        point = MeasuringPoint(**point_data)
        self.db.add(point)
        await self.db.flush()
        logger.info(f"Created measuring point: {point.point_code} for ship_id={point.ship_id}")
        return point


async def resolve_ship_and_point(
    mysql_db: AsyncSession,
    ship_code: str,
    point_code: str,
) -> Tuple[Ship, MeasuringPoint]:
    ship_repo = ShipRepository(mysql_db)
    ship = await ship_repo.get_by_code(ship_code)
    if not ship:
        raise BusinessException(ErrorCode.SHIP_NOT_FOUND)

    point_repo = MeasuringPointRepository(mysql_db)
    point = await point_repo.get_by_code(ship.id, point_code)
    if not point:
        raise BusinessException(ErrorCode.POINT_NOT_FOUND)

    return ship, point
