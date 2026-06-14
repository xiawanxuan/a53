from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DECIMAL, DateTime, Text, Integer, SmallInteger, ForeignKey, Index
from sqlalchemy.orm import relationship

from ..database.connection import BaseMySQL


class Ship(BaseMySQL):
    __tablename__ = "ships"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ship_code = Column(String(64), nullable=False, unique=True, comment="船舶编号")
    ship_name = Column(String(128), nullable=False, comment="船舶名称")
    ship_type = Column(String(64), comment="船舶类型")
    imo_number = Column(String(64), comment="IMO编号")
    gross_tonnage = Column(DECIMAL(12, 2), comment="总吨位")
    length_overall = Column(DECIMAL(10, 2), comment="总长(米)")
    beam = Column(DECIMAL(10, 2), comment="型宽(米)")
    draft = Column(DECIMAL(10, 2), comment="吃水(米)")
    build_year = Column(Integer, comment="建造年份")
    status = Column(SmallInteger, default=1, comment="状态")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    measuring_points = relationship("MeasuringPoint", back_populates="ship", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_ship_code", "ship_code"),
        Index("idx_ship_name", "ship_name"),
    )


class MeasuringPoint(BaseMySQL):
    __tablename__ = "measuring_points"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ship_id = Column(BigInteger, ForeignKey("ships.id", ondelete="CASCADE"), nullable=False)
    point_code = Column(String(64), nullable=False, comment="测点编号")
    point_name = Column(String(128), nullable=False, comment="测点名称")
    location_desc = Column(String(256), comment="位置描述")
    direction = Column(String(32), comment="测量方向")
    sensor_type = Column(String(64), comment="传感器类型")
    sensor_model = Column(String(128), comment="传感器型号")
    sensitivity = Column(DECIMAL(12, 6), comment="灵敏度")
    sample_rate = Column(DECIMAL(12, 2), default=1024.0, comment="采样率")
    range_value = Column(DECIMAL(12, 4), comment="量程")
    unit = Column(String(32), default="mm/s", comment="单位")
    status = Column(SmallInteger, default=1, comment="状态")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ship = relationship("Ship", back_populates="measuring_points")

    __table_args__ = (
        Index("uk_ship_point", "ship_id", "point_code", unique=True),
        Index("idx_ship_id", "ship_id"),
        Index("idx_point_code", "point_code"),
    )


class IdentificationTask(BaseMySQL):
    __tablename__ = "identification_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ship_id = Column(BigInteger, ForeignKey("ships.id"), nullable=False)
    point_id = Column(BigInteger, ForeignKey("measuring_points.id"), nullable=False)
    task_uuid = Column(String(64), nullable=False, unique=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(SmallInteger, default=0, comment="0-待处理 1-处理中 2-成功 3-失败")
    sample_count = Column(Integer, default=0)
    sample_rate = Column(DECIMAL(12, 2))
    error_message = Column(Text)
    failed_waveform_path = Column(String(512))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    modal_results = relationship("ModalResult", back_populates="task", cascade="all, delete-orphan")
    fft_spectra = relationship("FFTSpectrum", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_ship_point_time", "ship_id", "point_id", "start_time"),
        Index("idx_task_uuid", "task_uuid"),
        Index("idx_status", "status"),
    )


class ModalResult(BaseMySQL):
    __tablename__ = "modal_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("identification_tasks.id", ondelete="CASCADE"), nullable=False)
    mode_order = Column(Integer, nullable=False, comment="模态阶次")
    natural_frequency = Column(DECIMAL(12, 6), nullable=False, comment="固有频率(Hz)")
    damping_ratio = Column(DECIMAL(10, 8), nullable=False, comment="阻尼比")
    amplitude = Column(DECIMAL(16, 8), comment="振型幅值")
    phase_angle = Column(DECIMAL(10, 6), comment="相位角")
    confidence = Column(DECIMAL(6, 4), comment="置信度")
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("IdentificationTask", back_populates="modal_results")

    __table_args__ = (
        Index("idx_task_id", "task_id"),
        Index("idx_frequency", "natural_frequency"),
    )


class FFTSpectrum(BaseMySQL):
    __tablename__ = "fft_spectra"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("identification_tasks.id", ondelete="CASCADE"), nullable=False)
    frequency = Column(DECIMAL(12, 6), nullable=False, comment="频率点(Hz)")
    amplitude = Column(DECIMAL(16, 8), nullable=False, comment="频谱幅值")
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("IdentificationTask", back_populates="fft_spectra")

    __table_args__ = (
        Index("idx_task_id_spectrum", "task_id"),
    )


class AlertCallbackRecord(BaseMySQL):
    __tablename__ = "alert_callback_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("identification_tasks.id", ondelete="CASCADE"), nullable=False)
    ship_id = Column(BigInteger, nullable=False)
    point_id = Column(BigInteger, nullable=False)
    callback_uuid = Column(String(64), nullable=False, unique=True)
    webhook_url = Column(String(512), nullable=False)
    status = Column(SmallInteger, default=0, comment="0-待推送 1-成功 2-失败")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    response_status = Column(Integer, comment="HTTP响应状态码")
    response_body = Column(Text, comment="HTTP响应体")
    error_message = Column(Text, comment="错误信息")
    dangerous_modes = Column(Text, comment="危险模态参数JSON")
    pushed_at = Column(DateTime, comment="推送时间")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_task_id_callback", "task_id"),
        Index("idx_ship_point_callback", "ship_id", "point_id", "created_at"),
        Index("idx_status_callback", "status"),
        Index("idx_callback_uuid", "callback_uuid"),
    )
