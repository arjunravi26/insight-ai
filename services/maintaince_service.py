import asyncio
import logging
import time

from pathlib import Path

from services.cleaning_service import file_cleanup

from observability.metrics import (
    MAINTENANCE_RUNS,
    MAINTENANCE_DURATION,
    FILES_CLEANED,
    record_error,
)

logger = logging.getLogger(__name__)


async def maintenance_service(
    upload_dir: Path,
    interval_hrs: int = 24,
    max_hr_limit: int = 24
):

    interval_seconds = interval_hrs * 60 * 60

    while True:

        start_time = time.perf_counter()
        outcome = "failure"

        try:

            deleted_count = await asyncio.to_thread(
                file_cleanup,
                upload_dir=upload_dir,
                max_hr_limit=max_hr_limit
            )

            FILES_CLEANED.inc(
                deleted_count
            )

            outcome = "success"

            logger.info(
                "Periodic cleanup completed. Deleted: %s",
                deleted_count
            )

        except Exception as exc:

            record_error(
                "maintenance",
                exc
            )

            logger.exception(
                "Periodic cleanup failed"
            )

        finally:

            duration = time.perf_counter() - start_time

            MAINTENANCE_DURATION.observe(
                duration
            )

            MAINTENANCE_RUNS.labels(
                outcome=outcome
            ).inc()

        await asyncio.sleep(interval_seconds)