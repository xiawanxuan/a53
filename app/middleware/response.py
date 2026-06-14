from typing import Any, Optional
from fastapi.responses import JSONResponse
from .error_codes import ErrorCode, get_error_message


def api_response(
    data: Optional[Any] = None,
    code: ErrorCode = ErrorCode.SUCCESS,
    message: Optional[str] = None,
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code.value,
            "message": message or get_error_message(code),
            "data": data,
        },
    )
