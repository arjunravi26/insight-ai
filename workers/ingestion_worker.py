import asyncio
import logging
from services.ingestion_service import IngestionService
from services.ingestion_job_service import (
    IngestionJobService,
    LeaseLostError
)
from schemas.ingestion_job import IngestionJobPayload


logger = logging.getLogger(__name__)


async def wait_for_work(
    stop_event: asyncio.Event,
    timeout: int = 1
):
    try:
        await asyncio.wait_for(
            stop_event.wait(),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        pass


async def ingest_with_heartbeat(
    ingestion_service: IngestionService,
    job_service: IngestionJobService,
    payload: IngestionJobPayload
):

    ingestion_task = asyncio.create_task(
        asyncio.to_thread(
            ingestion_service.ingest_pdf,
            payload.file_path,
            payload.document_id,
            payload.user_id,
            payload.filename
        )
    )

    heartbeat_interval = max(
        1,
        job_service.lease_seconds // 3
    )

    while True:

        done, _ = await asyncio.wait(
            {ingestion_task},
            timeout=heartbeat_interval
        )

        if done:
            return await ingestion_task

        try:

            renewed = await asyncio.to_thread(
                job_service.renew_lease,
                payload
            )

        except Exception:

            # A database error does not necessarily mean lease loss.
            logger.exception(
                "Could not renew lease for job %s",
                payload.job_id
            )

            # Try again on the next heartbeat interval.
            continue

        if renewed:
            logger.debug(
                "Lease renewed for job %s",
                payload.job_id
            )
            continue

        # A False result means ownership was not renewed.
        logger.warning(
            "Lease lost for job %s",
            payload.job_id
        )

        # asyncio cannot forcibly stop a function running in a thread.
        # Wait for it to finish so its exception is retrieved.
        try:
            await asyncio.shield(ingestion_task)
        except Exception:
            logger.exception(
                "Ingestion thread failed after lease loss for job %s",
                payload.job_id
            )

        raise LeaseLostError(
            f"Worker lost ownership of job {payload.job_id}"
        )


async def worker(
    ingestion_service: IngestionService,
    job_service: IngestionJobService,
    stop_event: asyncio.Event
):

    logger.info("Ingestion worker started")

    while not stop_event.is_set():

        try:

            # 1. Claim the next job.
            payload = await asyncio.to_thread(
                job_service.claim_next_job
            )

            if payload is None:
                await wait_for_work(stop_event)
                continue

            logger.info(
                "Claimed ingestion job %s for document %s",
                payload.job_id,
                payload.document_id
            )

            # 2. Process the PDF and renew the lease.
            try:

                await ingest_with_heartbeat(
                    ingestion_service,
                    job_service,
                    payload
                )

            except LeaseLostError:

                logger.warning(
                    "Not updating job %s because its lease was lost",
                    payload.job_id
                )

                continue

            except Exception as exc:

                logger.exception(
                    "Ingestion failed for job %s",
                    payload.job_id
                )

                # 3. Handle ingestion failure.
                try:

                    await asyncio.to_thread(
                        job_service.mark_job_failed,
                        payload,
                        str(exc)
                    )

                except LeaseLostError:

                    logger.warning(
                        "Cannot mark job %s failed: lease lost",
                        payload.job_id
                    )

                continue

            # 4. Handle successful ingestion.
            try:

                await asyncio.to_thread(
                    job_service.mark_job_success,
                    payload
                )

                logger.info(
                    "Ingestion completed for job %s",
                    payload.job_id
                )

            except LeaseLostError:

                logger.warning(
                    "Cannot mark job %s successful: lease lost",
                    payload.job_id
                )

        except asyncio.CancelledError:
            raise

        except Exception:

            logger.exception(
                "Unexpected ingestion worker error"
            )

            await asyncio.sleep(1)

    logger.info("Ingestion worker stopped")