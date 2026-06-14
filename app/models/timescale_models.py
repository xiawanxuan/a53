from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Float, DateTime, Text, SmallInteger, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP

from ..database.connection import BaseTimescale


class VibrationWaveform(BaseTimescale):
    __tablename__ = "vibration_waveforms"

    ship_id = Column(BigInteger, primary_key=True, nullable=False)
    point_id = Column(BigInteger, primary_key=True, nullable=False)
    time = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)
    amplitude = Column(Float, nullable=False)
    sample_index = Column(BigInteger, primary_key=True, nullable=False)
    upload_batch_id = Column(String(64), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_ship_point_time", "ship_id", "point_id", "time"),
        Index("idx_upload_batch", "upload_batch_id"),
    )


class WaveformUploadSession(BaseTimescale):
    __tablename__ = "waveform_upload_sessions"

    batch_id = Column(String(64), primary_key=True)
    ship_id = Column(BigInteger, nullable=False)
    point_id = Column(BigInteger, nullable=False)
    total_segments = Column(Integer, nullable=False, default=0)
    received_segments = Column(Integer, nullable=False, default=0)
    total_samples = Column(BigInteger, nullable=False, default=0)
    sample_rate = Column(Float, default=1024.0)
    start_time = Column(TIMESTAMP(timezone=True))
    end_time = Column(TIMESTAMP(timezone=True))
    status = Column(SmallInteger, default=0, comment="0-上传中 1-完成 2-失败")
    error_message = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_session_ship_point", "ship_id", "point_id", "created_at"),
        Index("idx_session_status", "status"),
    )
