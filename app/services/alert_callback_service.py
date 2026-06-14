from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import json
import uuid
import asyncio
import httpx

from ..config.yaml_config import yaml_config
from ..logging_config.logger import logger
from ..repository import AlertCallbackRepository


class ModalAlertJudge:
    def __init__(self):
        cfg = yaml_config.get("alert_callback")
        self.freq_min = cfg.get("danger_frequency_min", 10.0)
        self.freq_max = cfg.get("danger_frequency_max", 100.0)
        self.amplitude_threshold = cfg.get("danger_amplitude_threshold", 50.0)
        self.damping_max = cfg.get("danger_damping_max", 0.02)
        self.confidence_min = cfg.get("danger_confidence_min", 0.7)

    def check_danger_mode(self, modal_param: Dict[str, Any]) -> bool:
        freq = float(modal_param.get("natural_frequency", 0))
        amp = float(modal_param.get("amplitude") or 0)
        damping = float(modal_param.get("damping_ratio", 0))
        confidence = float(modal_param.get("confidence") or 0)

        if freq < self.freq_min or freq > self.freq_max:
            return False
        if amp < self.amplitude_threshold:
            return False
        if damping > self.damping_max:
            return False
        if confidence < self.confidence_min:
            return False
        return True

    def filter_dangerous_modes(
        self, modal_params: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        dangerous = []
        for mp in modal_params:
            if self.check_danger_mode(mp):
                dangerous.append(mp)
        return dangerous

    def get_thresholds(self) -> Dict[str, Any]:
        return {
            "danger_frequency_min": self.freq_min,
            "danger_frequency_max": self.freq_max,
            "danger_amplitude_threshold": self.amplitude_threshold,
            "danger_damping_max": self.damping_max,
            "danger_confidence_min": self.confidence_min,
        }


class AlertCallbackService:
    def __init__(self, mysql_db):
        self.mysql_db = mysql_db
        self.callback_repo = AlertCallbackRepository(mysql_db)
        self.judge = ModalAlertJudge()
        cfg = yaml_config.get("alert_callback")
        self.enabled = cfg.get("enabled", True)
        self.webhook_url = cfg.get("webhook_url", "")
        self.auth_header = cfg.get("auth_header", "X-API-Key")
        self.auth_token = cfg.get("auth_token", "")
        self.timeout = cfg.get("timeout_seconds", 10)
        self.max_retries = cfg.get("retry_count", 3)
        self.retry_delay = cfg.get("retry_delay_seconds", 2)

    def _build_payload(
        self,
        ship_code: str,
        point_code: str,
        task_uuid: str,
        start_time: datetime,
        end_time: datetime,
        sample_rate: float,
        modal_params: List[Dict[str, Any]],
        ship_info: Optional[Dict[str, Any]] = None,
        point_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "alert_type": "dangerous_resonance",
            "timestamp": datetime.utcnow().isoformat(),
            "task_uuid": task_uuid,
            "ship": {
                "ship_code": ship_code,
                "ship_name": ship_info.get("ship_name") if ship_info else None,
                "ship_type": ship_info.get("ship_type") if ship_info else None,
            },
            "measuring_point": {
                "point_code": point_code,
                "point_name": point_info.get("point_name") if point_info else None,
                "location_desc": point_info.get("location_desc") if point_info else None,
                "direction": point_info.get("direction") if point_info else None,
            },
            "analysis_period": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "sample_rate": sample_rate,
            },
            "modal_parameters": [
                {
                    "mode_order": mp.get("mode_order"),
                    "natural_frequency": mp.get("natural_frequency"),
                    "damping_ratio": mp.get("damping_ratio"),
                    "amplitude": mp.get("amplitude"),
                    "phase_angle": mp.get("phase_angle"),
                    "confidence": mp.get("confidence"),
                }
                for mp in modal_params
            ],
            "danger_count": len(modal_params),
        }

    async def _do_push(self, url: str, payload: Dict[str, Any]) -> Tuple[int, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers[self.auth_header] = self.auth_token

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            return response.status_code, response.text

    async def push_alert(
        self,
        ship_code: str,
        point_code: str,
        ship_id: int,
        point_id: int,
        task_id: int,
        task_uuid: str,
        start_time: datetime,
        end_time: datetime,
        sample_rate: float,
        modal_params: List[Dict[str, Any]],
        ship_info: Optional[Dict[str, Any]] = None,
        point_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self.enabled or not self.webhook_url:
            logger.info("Alert callback is disabled, skip push")
            return None

        dangerous_modes = self.judge.filter_dangerous_modes(modal_params)
        if not dangerous_modes:
            logger.info(
                f"No dangerous modes detected for task {task_uuid}, skip callback"
            )
            return None

        callback_uuid = str(uuid.uuid4())
        dangerous_json = json.dumps(
            dangerous_modes, ensure_ascii=False, default=str
        )

        record = await self.callback_repo.create_record(
            task_id=task_id,
            ship_id=ship_id,
            point_id=point_id,
            callback_uuid=callback_uuid,
            webhook_url=self.webhook_url,
            dangerous_modes_json=dangerous_json,
            max_retries=self.max_retries,
        )
        await self.mysql_db.commit()

        payload = self._build_payload(
            ship_code=ship_code,
            point_code=point_code,
            task_uuid=task_uuid,
            start_time=start_time,
            end_time=end_time,
            sample_rate=sample_rate,
            modal_params=dangerous_modes,
            ship_info=ship_info,
            point_info=point_info,
        )

        last_error = None
        last_status = None
        last_body = None

        for attempt in range(self.max_retries + 1):
            try:
                status, body = await self._do_push(self.webhook_url, payload)
                last_status = status
                last_body = body

                if 200 <= status < 300:
                    await self.callback_repo.update_record(
                        callback_uuid=callback_uuid,
                        status=1,
                        retry_count=attempt,
                        response_status=status,
                        response_body=body,
                        pushed_at=datetime.utcnow(),
                    )
                    await self.mysql_db.commit()
                    logger.info(
                        f"Alert callback success: callback_uuid={callback_uuid}, "
                        f"task_uuid={task_uuid}, status={status}"
                    )
                    return callback_uuid
                else:
                    last_error = f"HTTP {status}"
                    logger.warning(
                        f"Alert callback attempt {attempt + 1}/{self.max_retries + 1} "
                        f"failed: status={status}, body={body[:200]}"
                    )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Alert callback attempt {attempt + 1}/{self.max_retries + 1} "
                    f"exception: {e}"
                )

            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay)

        await self.callback_repo.update_record(
            callback_uuid=callback_uuid,
            status=2,
            retry_count=self.max_retries,
            response_status=last_status,
            response_body=last_body,
            error_message=last_error,
            pushed_at=datetime.utcnow(),
        )
        await self.mysql_db.commit()
        logger.error(
            f"Alert callback all retries failed: callback_uuid={callback_uuid}, "
            f"task_uuid={task_uuid}, error={last_error}"
        )
        return callback_uuid

    def is_enabled(self) -> bool:
        return self.enabled and bool(self.webhook_url)

    def get_config(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "webhook_url": self.webhook_url,
            "timeout_seconds": self.timeout,
            "retry_count": self.max_retries,
            "retry_delay_seconds": self.retry_delay,
            **self.judge.get_thresholds(),
        }
