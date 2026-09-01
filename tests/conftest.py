import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.persistence.models import Base


@pytest.fixture
def sqlite_session():
    # StaticPool garante que todas as conexões compartilham o mesmo banco em memória.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
