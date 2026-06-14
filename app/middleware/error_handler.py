import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..logging_config.logger import logger
from .error_codes import ErrorCode, get_error_message
from .exceptions import BusinessException
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError


class RequestContext:
    def __init__(self, request_id: str, start_time: float):
        self.request_id = request_id
        self.start_time = start_time


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start_time = time.time()
        request.state.context = RequestContext(request_id, start_time)

        try:
            response = await call_next(request)
            duration = (time.time() - start_time) * 1000
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration:.2f}ms"
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} "
                f"- {response.status_code} - {duration:.2f}ms"
            )
            return response
        except BusinessException as be:
            duration = (time.time() - start_time) * 1000
            logger.warning(
                f"[{request_id}] BusinessException: code={be.code.value}, "
                f"msg={be.message}, duration={duration:.2f}ms"
            )
            return JSONResponse(
                status_code=400,
                content={
                    "code": be.code.value,
                    "message": be.message,
                    "data": be.data,
                    "request_id": request_id,
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-Response-Time": f"{duration:.2f}ms",
                },
            )
        except RequestValidationError as ve:
            duration = (time.time() - start_time) * 1000
            errors = []
            for err in ve.errors():
                errors.append({
                    "field": ".".join(str(loc) for loc in err["loc"]),
                    "message": err["msg"],
                    "type": err["type"],
                })
            logger.warning(
                f"[{request_id}] ValidationError: {errors}, duration={duration:.2f}ms"
            )
            return JSONResponse(
                status_code=422,
                content={
                    "code": ErrorCode.PARAM_INVALID.value,
                    "message": "参数校验失败",
                    "data": {"errors": errors},
                    "request_id": request_id,
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-Response-Time": f"{duration:.2f}ms",
                },
            )
        except SQLAlchemyError as dbe:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[{request_id}] DatabaseError: {dbe}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "code": ErrorCode.DB_OPERATION_FAILED.value,
                    "message": get_error_message(ErrorCode.DB_OPERATION_FAILED),
                    "data": None,
                    "request_id": request_id,
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-Response-Time": f"{duration:.2f}ms",
                },
            )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"[{request_id}] UnhandledException: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "code": ErrorCode.INTERNAL_SERVER_ERROR.value,
                    "message": get_error_message(ErrorCode.INTERNAL_SERVER_ERROR),
                    "data": None,
                    "request_id": request_id,
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-Response-Time": f"{duration:.2f}ms",
                },
            )
