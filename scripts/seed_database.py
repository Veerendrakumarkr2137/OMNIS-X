"""Initialize an empty database using the same code path as application startup."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import create_app


async def initialize():
    app = create_app()
    async with app.router.lifespan_context(app):
        print("OMNIS-X database is ready.")


if __name__ == "__main__":
    asyncio.run(initialize())
