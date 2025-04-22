import pika
from pika.adapters.blocking_connection import BlockingConnection, BlockingChannel
from app.config.settings import get_settings

class RabbitMQProvider:
    _conn: BlockingConnection | None = None
    _ch: BlockingChannel | None = None

    @classmethod
    def get_channel(cls) -> BlockingChannel:
        """
        Returns a single shared channel, declaring the queue with:
         - durable=True
         - x-dead-letter-exchange: ''  (the default exchange)
         - x-dead-letter-routing-key: <same queue name>
         - x-message-ttl: 300000      (retry every 5 minutes)
        """
        settings = get_settings()

        if cls._ch is None or cls._conn is None or getattr(cls._conn, "is_closed", True):
            params = pika.URLParameters(settings.rabbit_uri)
            cls._conn = pika.BlockingConnection(params)
            ch: BlockingChannel = cls._conn.channel()

            args = {
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": settings.rabbit_queue_name,
                "x-message-ttl": 300_000,
            }
            ch.queue_declare(
                queue=settings.rabbit_queue_name,
                durable=True,
                arguments=args,
            )

            cls._ch = ch

        return cls._ch

    @classmethod
    def close(cls) -> None:
        if cls._conn:
            cls._conn.close()
            cls._conn = None
            cls._ch = None
