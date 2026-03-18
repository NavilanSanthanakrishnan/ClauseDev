from collections.abc import Generator
from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from clauseai_backend.core.config import settings

user_engine = create_engine(settings.user_database_url, future=True, pool_pre_ping=True)
openstates_engine = create_engine(settings.openstates_database_url, future=True, pool_pre_ping=True)
california_code_engine = create_engine(settings.california_code_database_url, future=True, pool_pre_ping=True)
legal_index_engine = create_engine(settings.legal_index_database_url, future=True, pool_pre_ping=True)
uscode_engine = create_engine(settings.uscode_database_url, future=True, pool_pre_ping=True)

UserSessionLocal = sessionmaker(bind=user_engine, autoflush=False, autocommit=False, expire_on_commit=False)
OpenStatesSessionLocal = sessionmaker(bind=openstates_engine, autoflush=False, autocommit=False, expire_on_commit=False)
CaliforniaCodeSessionLocal = sessionmaker(
    bind=california_code_engine, autoflush=False, autocommit=False, expire_on_commit=False
)
LegalIndexSessionLocal = sessionmaker(bind=legal_index_engine, autoflush=False, autocommit=False, expire_on_commit=False)
USCodeSessionLocal = sessionmaker(bind=uscode_engine, autoflush=False, autocommit=False, expire_on_commit=False)


@dataclass
class ReferenceDatabases:
    openstates: Session
    california_code: Session
    legal_index: Session
    uscode: Session

    def close(self) -> None:
        self.openstates.close()
        self.california_code.close()
        self.legal_index.close()
        self.uscode.close()


def get_user_db_session() -> Generator[Session, None, None]:
    session = UserSessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_reference_db_session() -> Generator[ReferenceDatabases, None, None]:
    session = ReferenceDatabases(
        openstates=OpenStatesSessionLocal(),
        california_code=CaliforniaCodeSessionLocal(),
        legal_index=LegalIndexSessionLocal(),
        uscode=USCodeSessionLocal(),
    )
    try:
        yield session
    finally:
        session.close()
