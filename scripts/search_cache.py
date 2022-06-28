"""
Script to expire TADB cache entries. Can be adapted for other cache expiration tasks as needed.
"""

import asyncio
import pickle

import asyncpg

HOST = "127.0.0.1"
PORT = 5432
USER = ""
PASSWORD = ""
DB = "lm_cache_db"


def decode_value(v):
    return pickle.loads(v)


def contains_tadb(v):
    return any("theaudiodb.com" in i["Url"] for i in v.get("images", []))


async def main():
    conn = await asyncpg.connect(f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB}")

    results = conn.fetch(
        """
    SELECT key, value FROM artist;
    """
    )

    to_expire = []
    for r in await results:
        decoded = decode_value(r["value"])
        if contains_tadb(decoded):
            to_expire.append(r["key"])

    print(len(to_expire), "entries to expire")

    # WHERE IN evidently isn't supported, which is why the ANY($1::text[]) is needed
    # https://stackoverflow.com/questions/57926778/asyncpg-select-where-in-gives-postgressyntaxerror
    deleted = await conn.execute(
        """
    DELETE FROM artist WHERE key = ANY($1::text[])
    """,
        to_expire,
    )

    print("Expired", deleted)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
