from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..config.yaml_config import yaml_config
from ..logging_config.logger import logger
from .error_codes import ErrorCode
from .exceptions import BusinessException


class ValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length:
                max_size = yaml_config.get(
                    "ingestion", "max_segment_size", 10 * 1024 * 1024
                )
                if int(content_length) > max_size:
                    raise BusinessException(ErrorCode.WAVEFORM_TOO_LARGE)

        ship_code = request.path_params.get("ship_code")
        if ship_code and not self._validate_ship_code(ship_code):
            raise BusinessException(ErrorCode.PARAM_INVALID, "船舶编号格式无效")

        return await call_next(request)

    @staticmethod
    def _validate_ship_code(ship_code: str) -> bool:
        if not ship_code or len(ship_code) > 64:
            return False
        return True
