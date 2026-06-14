CREATE DATABASE IF NOT EXISTS ship_ops DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE ship_ops;

CREATE TABLE IF NOT EXISTS ships (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ship_code VARCHAR(64) NOT NULL UNIQUE COMMENT '船舶编号',
    ship_name VARCHAR(128) NOT NULL COMMENT '船舶名称',
    ship_type VARCHAR(64) COMMENT '船舶类型：散货船、油轮、集装箱船等',
    imo_number VARCHAR(64) COMMENT 'IMO编号',
    gross_tonnage DECIMAL(12, 2) COMMENT '总吨位',
    length_overall DECIMAL(10, 2) COMMENT '总长(米)',
    beam DECIMAL(10, 2) COMMENT '型宽(米)',
    draft DECIMAL(10, 2) COMMENT '吃水(米)',
    build_year INT COMMENT '建造年份',
    status TINYINT DEFAULT 1 COMMENT '状态：1-正常 0-停用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_ship_code (ship_code),
    INDEX idx_ship_name (ship_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='船舶台账表';

CREATE TABLE IF NOT EXISTS measuring_points (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ship_id BIGINT NOT NULL COMMENT '所属船舶ID',
    point_code VARCHAR(64) NOT NULL COMMENT '测点编号',
    point_name VARCHAR(128) NOT NULL COMMENT '测点名称',
    location_desc VARCHAR(256) COMMENT '测点位置描述：主机曲轴、螺旋桨轴等',
    direction VARCHAR(32) COMMENT '测量方向：X/Y/Z轴',
    sensor_type VARCHAR(64) COMMENT '传感器类型：加速度计、速度传感器等',
    sensor_model VARCHAR(128) COMMENT '传感器型号',
    sensitivity DECIMAL(12, 6) COMMENT '传感器灵敏度',
    sample_rate DECIMAL(12, 2) DEFAULT 1024.0 COMMENT '采样率(Hz)',
    range_value DECIMAL(12, 4) COMMENT '量程',
    unit VARCHAR(32) DEFAULT 'mm/s' COMMENT '单位',
    status TINYINT DEFAULT 1 COMMENT '状态：1-正常 0-停用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ship_point (ship_id, point_code),
    INDEX idx_ship_id (ship_id),
    INDEX idx_point_code (point_code),
    FOREIGN KEY (ship_id) REFERENCES ships(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测点台账表';

CREATE TABLE IF NOT EXISTS identification_tasks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ship_id BIGINT NOT NULL COMMENT '船舶ID',
    point_id BIGINT NOT NULL COMMENT '测点ID',
    task_uuid VARCHAR(64) NOT NULL UNIQUE COMMENT '任务唯一标识',
    start_time DATETIME NOT NULL COMMENT '分析起始时间',
    end_time DATETIME NOT NULL COMMENT '分析结束时间',
    status TINYINT DEFAULT 0 COMMENT '状态：0-待处理 1-处理中 2-成功 3-失败',
    sample_count INT DEFAULT 0 COMMENT '样本点数',
    sample_rate DECIMAL(12, 2) COMMENT '采样率',
    error_message TEXT COMMENT '错误信息',
    failed_waveform_path VARCHAR(512) COMMENT '失败波形存储路径',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_ship_point_time (ship_id, point_id, start_time),
    INDEX idx_task_uuid (task_uuid),
    INDEX idx_status (status),
    FOREIGN KEY (ship_id) REFERENCES ships(id),
    FOREIGN KEY (point_id) REFERENCES measuring_points(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模态辨识任务表';

CREATE TABLE IF NOT EXISTS modal_results (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id BIGINT NOT NULL COMMENT '辨识任务ID',
    mode_order INT NOT NULL COMMENT '模态阶次',
    natural_frequency DECIMAL(12, 6) NOT NULL COMMENT '固有频率(Hz)',
    damping_ratio DECIMAL(10, 8) NOT NULL COMMENT '阻尼比',
    amplitude DECIMAL(16, 8) COMMENT '振型幅值',
    phase_angle DECIMAL(10, 6) COMMENT '相位角(度)',
    confidence DECIMAL(6, 4) COMMENT '辨识置信度(0-1)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_frequency (natural_frequency),
    FOREIGN KEY (task_id) REFERENCES identification_tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模态辨识结果表';

CREATE TABLE IF NOT EXISTS fft_spectra (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id BIGINT NOT NULL COMMENT '辨识任务ID',
    frequency DECIMAL(12, 6) NOT NULL COMMENT '频率点(Hz)',
    amplitude DECIMAL(16, 8) NOT NULL COMMENT '频谱幅值',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    FOREIGN KEY (task_id) REFERENCES identification_tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='FFT频谱结果表';

CREATE TABLE IF NOT EXISTS alert_callback_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id BIGINT NOT NULL COMMENT '辨识任务ID',
    ship_id BIGINT NOT NULL COMMENT '船舶ID',
    point_id BIGINT NOT NULL COMMENT '测点ID',
    callback_uuid VARCHAR(64) NOT NULL UNIQUE COMMENT '回调记录唯一标识',
    webhook_url VARCHAR(512) NOT NULL COMMENT '推送地址',
    status TINYINT DEFAULT 0 COMMENT '状态：0-待推送 1-成功 2-失败',
    retry_count INT DEFAULT 0 COMMENT '已重试次数',
    max_retries INT DEFAULT 3 COMMENT '最大重试次数',
    response_status INT COMMENT 'HTTP响应状态码',
    response_body TEXT COMMENT 'HTTP响应体',
    error_message TEXT COMMENT '错误信息',
    dangerous_modes TEXT COMMENT '危险模态参数JSON',
    pushed_at DATETIME COMMENT '推送时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_task_id_callback (task_id),
    INDEX idx_ship_point_callback (ship_id, point_id, created_at),
    INDEX idx_status_callback (status),
    INDEX idx_callback_uuid (callback_uuid),
    FOREIGN KEY (task_id) REFERENCES identification_tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模态告警回调推送记录表';
