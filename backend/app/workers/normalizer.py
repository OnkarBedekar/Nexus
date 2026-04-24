"""Redis stream consumer that normalizes raw TinyFish payloads."""

from __future__ import annotations

import asyncio
import json
import logging

from ..config import get_settings
from ..redis_client import (
    ensure_stream_group,
    ack_raw_message,
    move_to_dlq,
    read_raw_batch,
)
from ..tinyfish_runner import _ingest_raw_locally

log = logging.getLogger(__name__)


async def run_normalizer_loop() -> None:
    settings = get_settings()
    stream = settings.redis_raw_stream
    group = settings.redis_stream_group
    consumer = settings.redis_stream_consumer
    await ensure_stream_group(stream, group)

    while True:
        batch = await read_raw_batch(
            stream=stream,
            group=group,
            consumer=consumer,
            count=settings.redis_stream_batch_size,
            block_ms=settings.redis_stream_block_ms,
        )
        if not batch:
            await asyncio.sleep(0.2)
            continue
        for msg_id, fields in batch:
            try:
                session_id = fields["sessionId"]
                source_url = fields["sourceUrl"]
                payload = json.loads(fields["payload"])
                await _ingest_raw_locally(session_id, source_url, payload, seq_start=0)
                await ack_raw_message(stream, group, msg_id)
            except Exception as exc:
                log.exception("Normalizer failed for stream message %s", msg_id)
                await move_to_dlq(settings.redis_dlq_stream, msg_id, str(exc), fields)
                await ack_raw_message(stream, group, msg_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run_normalizer_loop())


if __name__ == "__main__":
    main()
