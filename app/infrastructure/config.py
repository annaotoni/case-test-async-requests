from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str  # obrigatório — sem default para não expor credenciais
    kafka_bootstrap_servers: str = "localhost:9092"
    redis_url: str = "redis://localhost:6379/0"
    kafka_topic: str = "requests.created"
    kafka_dlq_topic: str = "requests.created.dlq"
    kafka_group_id: str = "request-consumer"
    cache_ttl: int = 900
    rate_limit_requests: int = 10
    rate_limit_window: int = 60

    model_config = {"env_file": ".env"}


settings = Settings()
