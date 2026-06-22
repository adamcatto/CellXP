from cellxp.jobs.queues import RedisJobQueue


class FakeRedis:
    def __init__(self):
        self.messages = []
        self.acked = []
        self.group = None

    def xgroup_create(self, stream, group, id, mkstream):
        self.group = (stream, group, id, mkstream)

    def xadd(self, stream, fields):
        stream_id = f"{len(self.messages) + 1}-0"
        self.messages.append((stream, stream_id, fields))
        return stream_id

    def xreadgroup(self, group, consumer, streams, count, block):
        if not self.messages:
            return []
        stream, stream_id, fields = self.messages.pop(0)
        return [(stream, [(stream_id, fields)])]

    def xack(self, stream, group, stream_id):
        self.acked.append((stream, group, stream_id))

    def xlen(self, stream):
        return len(self.messages)


def test_redis_stream_queue_roundtrip_and_acknowledgement():
    redis = FakeRedis()
    queue = RedisJobQueue(redis, stream="jobs", group="workers")  # type: ignore[arg-type]
    queue.setup()
    job_id = queue.enqueue("structure.predict", {"sequence": "MKT"}, job_id="job-1")
    assert job_id == "job-1"
    assert queue.depth() == 1

    job = queue.reserve("gpu-1", block_ms=1)
    assert job is not None
    assert (job.task, job.payload) == ("structure.predict", {"sequence": "MKT"})
    queue.acknowledge(job)
    assert redis.acked == [("jobs", "workers", "1-0")]
