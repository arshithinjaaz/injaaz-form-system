#!/usr/bin/env python3
import os
from redis import Redis
from rq import Queue

url = os.environ.get("REDIS_URL")
if not url:
    raise SystemExit("No REDIS_URL provided")

conn = Redis.from_url(url)
q = Queue('default', connection=conn)
job = q.enqueue('builtins.print', 'hello from enqueue-test-job workflow')
print("Enqueued job id:", job.id)
