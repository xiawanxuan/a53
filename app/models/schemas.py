from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ShipBase(BaseModel):
    ship_code: str = Field(..., max_length=64, description="船舶编号")
    ship_name: str = Field(..., max_length=128, description="船舶名称")
    ship_type: Optional[str] = Field(None, max_length=64, description="船舶类型")
    imo_number: Optional[str] = Field(None, max_length=64, description="IMO编号")
    gross_tonnage: Optional[float] = Field(None, description="总吨位")
    length_overall: Optional[float] = Field(None, description="总长(米)")
    beam: Optional[float] = Field(None, description="型宽(米)")
    draft: Optional[float] = Field(None, description="吃水(米)")
    build_year: Optional[int] = Field(None, description="建造年份")


class ShipCreate(ShipBase):
    pass


class ShipResponse(ShipBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: int
    created_at: datetime
    updated_at: datetime


class MeasuringPointBase(BaseModel):
    point_code: str = Field(..., max_length=64, description="测点编号")
    point_name: str = Field(..., max_length=128, description="测点名称")
    location_desc: Optional[str] = Field(None, max_length=256, description="位置描述")
    direction: Optional[str] = Field(None, max_length=32, description="测量方向")
    sensor_type: Optional[str] = Field(None, max_length=64, description="传感器类型")
    sensor_model: Optional[str] = Field(None, max_length=128, description="传感器型号")
    sensitivity: Optional[float] = Field(None, description="灵敏度")
    sample_rate: Optional[float] = Field(1024.0, description="采样率(Hz)")
    range_value: Optional[float] = Field(None, description="量程")
    unit: Optional[str] = Field("mm/s", max_length=32, description="单位")


class MeasuringPointCreate(MeasuringPointBase):
    ship_id: int


class MeasuringPointResponse(MeasuringPointBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ship_id: int
    status: int
    created_at: datetime
    updated_at: datetime


class WaveformSegmentUpload(BaseModel):
    batch_id: str = Field(..., max_length=64, description="上传批次ID")
    segment_index: int = Field(..., ge=0, description="分段序号(从0开始)")
    total_segments: int = Field(..., ge=1, description="总分段数")
    sample_offset: int = Field(..., ge=0, description="该段第一个样本的全局偏移")
    sample_count: int = Field(..., gt=0, description="该段样本数量")
    start_time: datetime = Field(..., description="该段第一个样本时间戳")
    sample_rate: float = Field(..., gt=0, description="采样率(Hz)")
    byte_order: str = Field("little", description="字节序: little/big")
    dtype: str = Field("float32", description="数据类型: float32/float64")


class WaveformUploadInit(BaseModel):
    ship_code: str = Field(..., max_length=64, description="船舶编号")
    point_code: str = Field(..., max_length=64, description="测点编号")
    batch_id: str = Field(..., max_length=64, description="上传批次ID")
    total_segments: int = Field(..., ge=1, description="总分段数")
    total_samples: int = Field(..., gt=0, description="总样本数")
    sample_rate: float = Field(..., gt=0, description="采样率(Hz)")
    start_time: datetime = Field(..., description="起始时间")


class WaveformUploadStatus(BaseModel):
    batch_id: str
    received_segments: int
    total_segments: int
    received_samples: int
    total_samples: int
    status: int
    error_message: Optional[str] = None


class FFTResult(BaseModel):
    frequencies: List[float] = Field(..., description="频率数组(Hz)")
    amplitudes: List[float] = Field(..., description="幅值数组")
    sample_rate: float = Field(..., description="采样率(Hz)")
    nfft: int = Field(..., description="FFT点数")


class ModalParameter(BaseModel):
    mode_order: int = Field(..., description="模态阶次")
    natural_frequency: float = Field(..., description="固有频率(Hz)")
    damping_ratio: float = Field(..., description="阻尼比")
    amplitude: Optional[float] = Field(None, description="振型幅值")
    phase_angle: Optional[float] = Field(None, description="相位角(度)")
    confidence: Optional[float] = Field(None, description="辨识置信度")


class ModalIdentificationResponse(BaseModel):
    task_uuid: str = Field(..., description="任务唯一标识")
    ship_code: str
    point_code: str
    start_time: datetime
    end_time: datetime
    sample_count: int
    sample_rate: float
    modal_parameters: List[ModalParameter] = Field(..., description="辨识出的模态参数列表")
    fft: Optional[FFTResult] = Field(None, description="FFT频域结果")


class ModalIdentificationTaskCreate(BaseModel):
    ship_code: str = Field(..., max_length=64, description="船舶编号")
    point_code: str = Field(..., max_length=64, description="测点编号")
    start_time: datetime = Field(..., description="起始时间")
    end_time: datetime = Field(..., description="结束时间")


class WaveformQueryRequest(BaseModel):
    ship_code: str = Field(..., max_length=64, description="船舶编号")
    point_code: str = Field(..., max_length=64, description="测点编号")
    start_time: datetime = Field(..., description="起始时间")
    end_time: datetime = Field(..., description="结束时间")
    max_points: Optional[int] = Field(None, gt=0, description="最大返回点数")


class WaveformQueryResponse(BaseModel):
    ship_code: str
    point_code: str
    start_time: datetime
    end_time: datetime
    sample_rate: float
    total_points: int
    timestamps: List[datetime] = Field(..., description="时间戳数组")
    amplitudes: List[float] = Field(..., description="幅值数组")


class ModalQueryRequest(BaseModel):
    ship_code: Optional[str] = Field(None, max_length=64, description="船舶编号")
    point_code: Optional[str] = Field(None, max_length=64, description="测点编号")
    start_time: Optional[datetime] = Field(None, description="起始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    task_uuid: Optional[str] = Field(None, max_length=64, description="任务UUID")
