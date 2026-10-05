import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    dbs = await conn.fetch("SELECT datname FROM pg_database WHERE datname = 'personalized_newspaper'")
    if not dbs:
        print("Creating database personalized_newspaper...")
        await conn.execute("CREATE DATABASE personalized_newspaper;")
        print("Database created successfully!")
    else:
        print("Database personalized_newspaper already exists.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
