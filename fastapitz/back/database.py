from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn
from sqlalchemy import select, Integer, String

from fastapi import Depends
from typing import Annotated

engine = create_async_engine('sqlite+aiosqlite:///resume.db', echo=True)
new_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_session():
    async with new_session() as session:
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Базовый класс для моделей
class Base(DeclarativeBase):
    pass

class ResumeModel(Base):
    __tablename__ = 'resumes'
    
    id: Mapped[int] = MappedColumn(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = MappedColumn(String)
    context: Mapped[str] = MappedColumn(String)
    user_id: Mapped[int] = MappedColumn(Integer)  # для связи с пользователем

class UsersModel(Base):
    __tablename__ = 'users'
    
    id: Mapped[int] = MappedColumn(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = MappedColumn(String, unique=True)
    password: Mapped[str] = MappedColumn(String)

async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)