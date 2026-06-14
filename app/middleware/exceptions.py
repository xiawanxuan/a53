from .error_codes import ErrorCode, get_error_message
from typing import Any, Optional


class BusinessException(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: Optional[str] = None,
        data: Optional[Any] = None,
    ):
        self.code = code
        self.message = message or get_error_message(code)
        self.data = data
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "code": self.code.value,
            "message": self.message,
            "data": self.data,
        }


class ParameterValidationException(BusinessException):
    def __init__(self, message: str = None, data: Any = None):
        super().__init__(ErrorCode.PARAM_INVALID, message, data)


class DatabaseOperationException(BusinessException):
    def __init__(self, message: str = None, data: Any = None):
        super().__init__(ErrorCode.DB_OPERATION_FAILED, message, data)


class WaveformIngestionException(BusinessException):
    def __init__(self, code: ErrorCode, message: str = None, data: Any = None):
        super().__init__(code, message, data)


class AnalysisException(BusinessException):
    def __init__(self, code: ErrorCode, message: str = None, data: Any = None):
        super().__init__(code, message, data)
