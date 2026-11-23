"""Fon vazifalari: Celery yoqilgan bo'lsa worker'da, aks holda FastAPI fon oqimida."""
from __future__ import annotations

from app.config import get_settings
from app.labengine import orchestrator

try:
    from celery import Celery

    celery_app = Celery("clpe", broker=get_settings().redis_url, backend=get_settings().redis_url)
    celery_app.conf.beat_schedule = {
        "cleanup-expired-labs": {"task": "clpe.cleanup_expired", "schedule": 60.0},
    }

    @celery_app.task(name="clpe.start_lab")
    def start_lab_task(instance_id: str) -> None:
        orchestrator.start_instance(_uuid(instance_id))

    @celery_app.task(name="clpe.stop_lab")
    def stop_lab_task(instance_id: str, reason: str = "user") -> None:
        orchestrator.stop_instance(_uuid(instance_id), reason)

    @celery_app.task(name="clpe.restore_lab")
    def restore_lab_task(instance_id: str, name: str = "initial") -> None:
        orchestrator.restore_instance(_uuid(instance_id), name)

    @celery_app.task(name="clpe.cleanup_expired")
    def cleanup_expired_task() -> int:
        return orchestrator.cleanup_expired()
except ImportError:  # pragma: no cover
    celery_app = None


def _uuid(v):
    import uuid
    return uuid.UUID(str(v))


def dispatch(name: str, background, *args) -> None:
    """name: start | stop | restore. background — FastAPI BackgroundTasks."""
    if get_settings().use_celery and celery_app is not None:
        {"start": start_lab_task, "stop": stop_lab_task, "restore": restore_lab_task}[name].delay(
            *[str(a) for a in args])
        return
    fn = {"start": orchestrator.start_instance, "stop": orchestrator.stop_instance,
          "restore": orchestrator.restore_instance}[name]
    background.add_task(fn, *args)
