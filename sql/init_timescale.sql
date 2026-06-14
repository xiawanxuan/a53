CREATE DATABASE vibration_ts;

\c vibration_ts

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS vibration_waveforms (
    ship_id BIGINT NOT NULL,
    point_id BIGINT NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    amplitude DOUBLE PRECISION NOT NULL,
    sample_index BIGINT NOT NULL,
    upload_batch_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ship_id, point_id, time, sample_index)
);

SELECT create_hypertable('vibration_waveforms', 'time', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 hour');

CREATE INDEX IF NOT EXISTS idx_ship_point_time ON vibration_waveforms (ship_id, point_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_upload_batch ON vibration_waveforms (upload_batch_id);

CREATE TABLE IF NOT EXISTS waveform_upload_sessions (
    batch_id VARCHAR(64) PRIMARY KEY,
    ship_id BIGINT NOT NULL,
    point_id BIGINT NOT NULL,
    total_segments INT NOT NULL DEFAULT 0,
    received_segments INT NOT NULL DEFAULT 0,
    total_samples BIGINT NOT NULL DEFAULT 0,
    sample_rate DOUBLE PRECISION DEFAULT 1024.0,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    status SMALLINT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_ship_point ON waveform_upload_sessions (ship_id, point_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_status ON waveform_upload_sessions (status);

COMMENT ON TABLE vibration_waveforms IS '振动波形时序数据表';
COMMENT ON COLUMN vibration_waveforms.ship_id IS '船舶ID，关联MySQL船舶台账';
COMMENT ON COLUMN vibration_waveforms.point_id IS '测点ID，关联MySQL测点台账';
COMMENT ON COLUMN vibration_waveforms.time IS '采样时间戳';
COMMENT ON COLUMN vibration_waveforms.amplitude IS '振动幅值';
COMMENT ON COLUMN vibration_waveforms.sample_index IS '该批次内样本序号';
COMMENT ON COLUMN vibration_waveforms.upload_batch_id IS '上传批次ID';

COMMENT ON TABLE waveform_upload_sessions IS '分段上传会话记录表';
COMMENT ON COLUMN waveform_upload_sessions.batch_id IS '批次ID，客户端生成的UUID';
COMMENT ON COLUMN waveform_upload_sessions.status IS '状态：0-上传中 1-完成 2-失败';
