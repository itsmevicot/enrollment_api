import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pika.exceptions import AMQPConnectionError

from app.config.settings import get_settings
from app.queue.provider import RabbitMQProvider
from app.routers.health_router import router as health_router
from app.routers.enrollment_router import router as enrollment_router

settings = get_settings()

async def _connect_rabbitmq_with_retry(
    max_attempts: int = 5, base_delay: int = 3
):
    for attempt in range(1, max_attempts + 1):
        try:
            RabbitMQProvider.get_channel()
            print("Connected to RabbitMQ")
            return
        except AMQPConnectionError:
            if attempt < max_attempts:
                delay = attempt * base_delay
                print(
                    f"RabbitMQ not ready (attempt {attempt}/{max_attempts}), "
                    f"retrying in {delay}s…"
                )
                await asyncio.sleep(delay)
            else:
                print(
                    f"Could not connect to RabbitMQ after "
                    f"{max_attempts} attempts; giving up for now."
                )

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_connect_rabbitmq_with_retry())
    yield
    RabbitMQProvider.close()
    print("Shutting down Enrollment API")

app = FastAPI(
    title="Enrollment API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(enrollment_router)
