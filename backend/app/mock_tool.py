from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Tool")


class EchoRequest(BaseModel):
    text: str = Field(min_length=1)


class SumRequest(BaseModel):
    a: float
    b: float


@app.post("/echo")
async def echo(payload: EchoRequest) -> dict[str, str]:
    return {"text": payload.text}


@app.post("/sum")
async def sum_numbers(payload: SumRequest) -> dict[str, float]:
    return {"result": payload.a + payload.b}
