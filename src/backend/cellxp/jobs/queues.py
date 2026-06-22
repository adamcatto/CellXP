"""Redis Streams job transport with durable acknowledgement and retry metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast

from redis import Redis
from redis.exceptions import ResponseError

from cellxp.domain.ids import new_id


@dataclass(frozen=True)
class Job:
    id: str
    stream_id: str
    task: str
    payload: dict[str, Any]
    attempts: int = 0
    max_attempts: int = 3


class RedisJobQueue:
    """Producer/consumer facade over one Redis Stream and consumer group."""

    def __init__(self, client: Redis, *, stream: str = "cellxp:jobs", group: str = "cellxp-workers"):
        self.client = client
        self.stream = stream
        self.group = group

    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> "RedisJobQueue":
        return cls(Redis.from_url(url, decode_responses=True), **kwargs)

    def setup(self) -> None:
        try:
            self.client.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def enqueue(
        self, task: str, payload: dict[str, Any], *, job_id: str | None = None,
        attempts: int = 0, max_attempts: int = 3,
    ) -> str:
        job_id = job_id or new_id()
        # A stable command id is the dispatch fence across API retries and outbox recovery.
        dedupe_key = f"{self.stream}:dedupe:{job_id}"
        if hasattr(self.client, "set") and not self.client.set(
            dedupe_key, "1", nx=True, ex=7 * 24 * 60 * 60
        ):
            return job_id
        self.client.xadd(self.stream, {
            "job_id": job_id, "task": task,
            "payload": json.dumps(payload, separators=(",", ":")),
            "attempts": str(attempts), "max_attempts": str(max_attempts),
        })
        return job_id

    def reserve(self, consumer: str, *, block_ms: int = 5000) -> Job | None:
        # redis-py's return annotation is a union covering several command shapes. This call's
        # concrete shape is fixed by XREADGROUP with one stream: [(stream, [(id, fields)])].
        rows = cast(
            list[tuple[str, list[tuple[str, dict[str, str]]]]],
            self.client.xreadgroup(
                self.group, consumer, {self.stream: ">"}, count=1, block=block_ms,
            ),
        )
        if not rows:
            return None
        _, messages = rows[0]
        stream_id, fields = messages[0]
        return self._job(stream_id, fields)

    def reclaim(self, consumer: str, *, min_idle_ms: int = 60_000) -> Job | None:
        """Claim one command abandoned by a crashed consumer."""
        rows = self.client.xautoclaim(
            self.stream, self.group, consumer, min_idle_ms, "0-0", count=1
        )
        messages = rows[1] if rows else []
        if not messages:
            return None
        stream_id, fields = messages[0]
        return self._job(stream_id, fields)

    @staticmethod
    def _job(stream_id: str, fields: dict[str, str]) -> Job:
        return Job(
            id=fields["job_id"], stream_id=stream_id, task=fields["task"],
            payload=json.loads(fields["payload"]), attempts=int(fields.get("attempts", 0)),
            max_attempts=int(fields.get("max_attempts", 3)),
        )

    def acknowledge(self, job: Job) -> None:
        self.client.xack(self.stream, self.group, job.stream_id)

    def retry(self, job: Job) -> bool:
        """Acknowledge and redeliver a failed command while its retry budget remains."""
        self.acknowledge(job)
        if job.attempts + 1 >= job.max_attempts:
            self.client.xadd(f"{self.stream}:dead", {
                "job_id": job.id, "task": job.task,
                "payload": json.dumps(job.payload, separators=(",", ":")),
                "attempts": str(job.attempts + 1),
            })
            return False
        # A retry is a distinct delivery but preserves the logical job id in its payload.
        retry_id = f"{job.id}:retry:{job.attempts + 1}"
        self.enqueue(
            job.task, job.payload, job_id=retry_id,
            attempts=job.attempts + 1, max_attempts=job.max_attempts,
        )
        return True

    def depth(self) -> int:
        return int(self.client.xlen(self.stream))
