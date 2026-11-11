import asyncio
import logging
from services.cleaning_service import file_cleanup
from pathlib import Path

logger = logging.getLogger(__name__)


async def maintance_service(upload_dir: Path, interval_hrs: int = 24, max_hr_limit: int = 24):
    interval_seconds = interval_hrs * 60 * 60

    while True:
        try:
            deleted_count = await asyncio.to_thread(
                file_cleanup,
                upload_dir=upload_dir,
                max_hr_limit=max_hr_limit
            )
            logger.info(
                "Periodic cleanup finished. Deleted: %s",
                deleted_count
            )
        except Exception as e:
            logger.exception(f"Exception occured: {e}")
            pass

        await asyncio.sleep(interval_seconds)
