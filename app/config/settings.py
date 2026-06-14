from pydantic_settings import BaseSettings
from typing import Optional


class MySQLSettings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = "root"
    database: str = "ship_ops"

    class Config:
        env_prefix = "MYSQL_"


class TimescaleSettings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    database: str = "vibration_ts"

    class Config:
        env_prefix = "TIMESCALE_"


class AppSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    env: str = "development"
    log_level: str = "INFO"
    batch_insert_size: int = 1000

    class Config:
        env_prefix = "APP_"


class Settings:
    def __init__(self):
        self.mysql = MySQLSettings()
        self.timescale = TimescaleSettings()
        self.app = AppSettings()

    def get_mysql_url(self, async_mode: bool = True) -> str:
        if async_mode:
            return f"mysql+aiomysql://{self.mysql.user}:{self.mysql.password}@{self.mysql.host}:{self.mysql.port}/{self.mysql.database}"
        return f"mysql+pymysql://{self.mysql.user}:{self.mysql.password}@{self.mysql.host}:{self.mysql.port}/{self.mysql.database}"

    def get_timescale_url(self, async_mode: bool = True) -> str:
        if async_mode:
            return f"postgresql+asyncpg://{self.timescale.user}:{self.timescale.password}@{self.timescale.host}:{self.timescale.port}/{self.timescale.database}"
        return f"postgresql+psycopg2://{self.timescale.user}:{self.timescale.password}@{self.timescale.host}:{self.timescale.port}/{self.timescale.database}"


settings = Settings()
