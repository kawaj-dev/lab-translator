import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from labtranslator.models import Base
from labtranslator.seed import seed


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session)
        session.commit()
        yield session
    engine.dispose()
