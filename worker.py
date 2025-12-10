from redis import from_url
from rq import Worker, Queue, Connection
import config
import logging

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    redis_conn = from_url(config.REDIS_URL)
    with Connection(redis_conn):
        qs = [Queue(config.RQ_QUEUE)]
        w = Worker(qs)
        w.work()