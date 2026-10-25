import asyncio
from app.core.database import async_session
from app.services import user_service
async def main():
    async with async_session() as db:
        u = await user_service.create_user(db, email="teste@teste.com", password="senha123")
        print("created", u.id)
asyncio.run(main())
