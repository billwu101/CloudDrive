from typing import Literal

from fastapi import FastAPI


def create_app() -> FastAPI:
    application = FastAPI(title="Cloud Drive API")

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, Literal["ok"]]:
        return {"status": "ok"}

    return application


app = create_app()
