"""Redis Streams job transport with durable acknowledgement and retry metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

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

    def enqueue(self, task: str, payload: dict[str, Any], *, job_id: str | None = None) -> str:
        job_id = job_id or new_id()
        self.client.xadd(self.stream, {
            "job_id": job_id, "task": task,
            "payload": json.dumps(payload, separators=(",", ":")), "attempts": "0",
        })
        return job_id

    def reserve(self, consumer: str, *, block_ms: int = 5000) -> Job | None:
        rows = self.client.xreadgroup(
            self.group, consumer, {self.stream: ">"}, count=1, block=block_ms,
        )
        if not rows:
            return None
        _, messages = rows[0]
        stream_id, fields = messages[0]
        return Job(
            id=fields["job_id"], stream_id=stream_id, task=fields["task"],
            payload=json.loads(fields["payload"]), attempts=int(fields.get("attempts", 0)),
        )

    def acknowledge(self, job: Job) -> None:
        self.client.xack(self.stream, self.group, job.stream_id)

    def depth(self) -> int:
        return int(self.client.xlen(self.stream))
