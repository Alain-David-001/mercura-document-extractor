"""Run separately: python server/worker.py. No worker runs in the API process."""
import asyncio
import contextlib
import logging
import signal
import tempfile
from uuid import uuid4

from dotenv import load_dotenv
from pathlib import Path

import db
from config import Settings
from processing import ExtractionError, GeminiExtractor, merge_metadata, prepare_chunks

logger = logging.getLogger('mercura.worker')


async def process_job(settings, job, extractor):
    async def heartbeat():
        while True:
            await asyncio.sleep(settings.lease_seconds / 3)
            await asyncio.to_thread(db.renew, settings, job)

    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        with tempfile.TemporaryDirectory(prefix='job-', dir=settings.data_dir) as directory:
            chunks = await asyncio.to_thread(prepare_chunks, settings.uploads / job['storage_key'], Path(directory), settings)
            await asyncio.to_thread(db.progress, settings, job, 'extracting', 0, len(chunks))
            results = []
            for index, (path, first, last) in enumerate(chunks):
                # An expired owner must not send another provider request.
                await asyncio.to_thread(db.progress, settings, job, 'extracting')
                result = await asyncio.wait_for(extractor.extract(path, first, last), timeout=180)
                results.append(result)
                await asyncio.to_thread(db.progress, settings, job, 'extracting', index + 1, len(chunks))
            metadata, warning = merge_metadata(results)
            await asyncio.to_thread(db.finish, settings, job, metadata, warning)
            logger.info('job_completed document=%s attempt=%s chunks=%s', job['document_id'], job['attempts'], len(chunks))
    except db.LostClaim:
        logger.warning('job_claim_lost document=%s', job['document_id'])
    except Exception as exc:
        error = (exc if isinstance(exc, ExtractionError) else
                 ExtractionError('The extraction request timed out. Please retry.', transient=True) if isinstance(exc, TimeoutError) else
                 ExtractionError('Document processing failed. Check the PDF or retry.'))
        try:
            await asyncio.to_thread(db.fail, settings, job, str(error), error.transient)
        except db.LostClaim:
            pass
        logger.warning('job_failed document=%s attempt=%s category=%s', job['document_id'], job['attempts'], type(exc).__name__)
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, db.LostClaim):
            await heartbeat_task


async def run(settings, extractor, stop):
    async def loop():
        while not stop.is_set():
            try:
                job = await asyncio.to_thread(db.claim, settings)
                if job:
                    await process_job(settings, job, extractor)
                else:
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=settings.poll_seconds)
                    except TimeoutError:
                        pass
            except Exception as exc:
                logger.error('worker_loop_failed category=%s', type(exc).__name__)
                await asyncio.sleep(settings.poll_seconds)

    worker_id = str(uuid4())
    await asyncio.to_thread(db.register_worker, settings, worker_id)

    async def report_heartbeat():
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_heartbeat_seconds)
            except TimeoutError:
                try:
                    await asyncio.to_thread(db.pulse_worker, settings, worker_id)
                except Exception as exc:
                    logger.warning('worker_heartbeat_failed category=%s', type(exc).__name__)

    tasks = [asyncio.create_task(loop()) for _ in range(settings.concurrency)]
    tasks.append(asyncio.create_task(report_heartbeat()))
    try:
        await stop.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await asyncio.to_thread(db.unregister_worker, settings, worker_id)
        except Exception as exc:
            # If storage is unavailable, the registration expires naturally.
            logger.warning('worker_unregister_failed category=%s', type(exc).__name__)


async def main():
    load_dotenv(Path(__file__).parent / '.env')
    settings = Settings.from_env()
    db.initialize(settings)
    extractor = GeminiExtractor(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    logger.info('worker_started concurrency=%s', settings.concurrency)
    try:
        await run(settings, extractor, stop)
    finally:
        await extractor.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('google_genai').setLevel(logging.WARNING)
    asyncio.run(main())
