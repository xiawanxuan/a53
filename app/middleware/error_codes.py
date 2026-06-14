from enum import IntEnum


class ErrorCode(IntEnum):
    SUCCESS = 0

    PARAM_INVALID = 10001
    PARAM_MISSING = 10002
    PARAM_TYPE_ERROR = 10003

    SHIP_NOT_FOUND = 20001
    POINT_NOT_FOUND = 20002
    SHIP_POINT_MISMATCH = 20003

    WAVEFORM_EMPTY = 30001
    WAVEFORM_TOO_LARGE = 30002
    SEGMENT_INVALID = 30003
    BATCH_NOT_FOUND = 30004
    INGESTION_FAILED = 30005
    BINARY_PARSE_FAILED = 30006

    FFT_FAILED = 40001
    SAMPLE_RATE_INVALID = 40002
    WAVEFORM_TOO_SHORT = 40003

    MODAL_IDENTIFICATION_FAILED = 50001
    NO_PEAKS_DETECTED = 50002
    DAMPING_FIT_FAILED = 50003
    TASK_NOT_FOUND = 50004
    TASK_ALREADY_EXISTS = 50005

    QUERY_TIME_RANGE_INVALID = 60001
    QUERY_RESULT_TOO_LARGE = 60002
    DATA_NOT_FOUND = 60003

    DB_CONNECTION_ERROR = 70001
    DB_OPERATION_FAILED = 70002

    INTERNAL_SERVER_ERROR = 99999


ERROR_MESSAGES = {
    ErrorCode.SUCCESS: "success",
    ErrorCode.PARAM_INVALID: "参数无效",
    ErrorCode.PARAM_MISSING: "缺少必要参数",
    ErrorCode.PARAM_TYPE_ERROR: "参数类型错误",
    ErrorCode.SHIP_NOT_FOUND: "船舶不存在",
    ErrorCode.POINT_NOT_FOUND: "测点不存在",
    ErrorCode.SHIP_POINT_MISMATCH: "船舶与测点不匹配",
    ErrorCode.WAVEFORM_EMPTY: "波形数据为空",
    ErrorCode.WAVEFORM_TOO_LARGE: "波形数据过大",
    ErrorCode.SEGMENT_INVALID: "分段数据无效",
    ErrorCode.BATCH_NOT_FOUND: "上传批次不存在",
    ErrorCode.INGESTION_FAILED: "数据写入失败",
    ErrorCode.BINARY_PARSE_FAILED: "二进制数据解析失败",
    ErrorCode.FFT_FAILED: "FFT分析失败",
    ErrorCode.SAMPLE_RATE_INVALID: "采样率无效",
    ErrorCode.WAVEFORM_TOO_SHORT: "波形数据过短",
    ErrorCode.MODAL_IDENTIFICATION_FAILED: "模态辨识失败",
    ErrorCode.NO_PEAKS_DETECTED: "未检测到共振峰值",
    ErrorCode.DAMPING_FIT_FAILED: "阻尼比拟合失败",
    ErrorCode.TASK_NOT_FOUND: "辨识任务不存在",
    ErrorCode.TASK_ALREADY_EXISTS: "辨识任务已存在",
    ErrorCode.QUERY_TIME_RANGE_INVALID: "查询时间范围无效",
    ErrorCode.QUERY_RESULT_TOO_LARGE: "查询结果数量超限",
    ErrorCode.DATA_NOT_FOUND: "查询数据不存在",
    ErrorCode.DB_CONNECTION_ERROR: "数据库连接失败",
    ErrorCode.DB_OPERATION_FAILED: "数据库操作失败",
    ErrorCode.INTERNAL_SERVER_ERROR: "服务器内部错误",
}


def get_error_message(code: ErrorCode) -> str:
    return ERROR_MESSAGES.get(code, "未知错误")
