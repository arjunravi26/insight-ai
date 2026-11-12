import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def file_cleanup(upload_dir: Path, max_hr_limit: int = 24):

    try:

        if not upload_dir.exists():
            return 0

        cut_off_hr = time.time() - (max_hr_limit * 60 * 60)
        no_of_deleted_files = 0

        for path in upload_dir.glob(".*.pdf"):
            if path.stat().st_mtime < cut_off_hr:
                path.unlink(missing_ok=True)
                no_of_deleted_files += 1

        logger.exception(f"No of files deleted is: {no_of_deleted_files}")

        return no_of_deleted_files
    except Exception as e:
        logging.exception(f"Failed to delete files. {e}")
