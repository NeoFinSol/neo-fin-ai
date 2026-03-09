import contextlib
import logging
from collections.abc import AsyncGenerator

from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker, AsyncEngine


session: tuple[AsyncEngine, async_sessionmaker] | None = None
Base = declarative_base()


async def initialize_db(
		user: str,
		password: str,
		ip: str,
		database_name: str,
		ssl: dict | None = None) -> None:
	global session

	logging.info(f"Connecting to database '{database_name}'")

	connect_args: dict = {}
	use_ssl: bool = ssl is not None
	if use_ssl:
		connect_args["ssl"] = ssl

	url: str = f"postgresql+asyncpg://{user}:{password}@{ip}/{database_name}?charset=utf8mb4"
	if use_ssl and "verify_cert" in ssl and not ssl["verify_cert"]:
		url += "&ssl_verify_cert=false"

	engine = create_async_engine(url, connect_args=connect_args)
	session_maker: async_sessionmaker = async_sessionmaker(engine, class_=AsyncSession, autocommit=False, autoflush=False)

	session = (engine, session_maker)

	if use_ssl:
		logging.info(f"Connected to database '{database_name}' with SSL")
	else:
		logging.info(f"Connected to database '{database_name}' without SSL")


@contextlib.asynccontextmanager
async def database_session() -> AsyncGenerator[AsyncSession, None]:
	global session

	session_maker = session[1]
	async with session_maker() as s:
		yield s
