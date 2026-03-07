import dramatiq
from dramatiq.brokers.redis import RedisBroker
from app.core.config import settings

broker = RedisBroker(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
dramatiq.set_broker(broker)
