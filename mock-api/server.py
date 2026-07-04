#!/usr/bin/env python3
"""世界主要都市の月平均気温を返すモック API (FastAPI) — 正規化版。

ローカル単体検証と、Konnect Code Mode MCP の実証テストの両方で
「大量レコードを返す上流 API」として使う。データは cities / temperatures の
2 エンティティに正規化されている（temperatures.city_id → cities.id）。

エンドポイント:
    GET /cities              都市の一覧（id と都市名のみ、100 件）
    GET /cities/{city_id}    1 都市の詳細（id, city, country, latitude, longitude）
    GET /temperatures        気温レコード。city_id (必須) で 1 都市分を返す（120 件）
    GET /health              ヘルスチェック

起動:
    pip install -r requirements.txt
    uvicorn server:app --host 0.0.0.0 --port 8000
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

DATA_DIR = Path(__file__).parent / "data"


def _load(name: str) -> list[dict]:
    path = DATA_DIR / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    # ファイルが無ければ決定論的に生成（同じ値が再現される）
    from generate_data import generate

    cities, temperatures = generate()
    return cities if name == "cities.json" else temperatures


CITIES = _load("cities.json")
TEMPERATURES = _load("temperatures.json")
_CITY_IDS = {c["id"] for c in CITIES}

app = FastAPI(
    title="World City Monthly Temperatures API",
    description="世界主要 100 都市の月平均気温 (摂氏) を 10 年分返すモック API（正規化版）。",
    version="2.0.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "cities": len(CITIES), "temperatures": len(TEMPERATURES)}


@app.get("/cities")
def list_cities() -> list[dict]:
    """都市の一覧（id と都市名のみ）を返す。"""
    return [{"id": c["id"], "city": c["city"]} for c in CITIES]


@app.get("/cities/{city_id}")
def get_city(city_id: int) -> dict:
    """1 都市の詳細（id, city, country, latitude, longitude）を返す。"""
    for c in CITIES:
        if c["id"] == city_id:
            return c
    raise HTTPException(status_code=404, detail=f"city_id {city_id} not found")


@app.get("/temperatures")
def get_temperatures(
    city_id: int = Query(..., description="対象都市の id（必須）"),
    month: Optional[int] = Query(None, ge=1, le=12, description="月 (1-12) で絞り込み"),
    year: Optional[int] = Query(None, description="年で絞り込み"),
) -> list[dict]:
    """指定した city_id の気温レコードを返す（既定で 120 件 = 12 か月 × 10 年）。"""
    if city_id not in _CITY_IDS:
        raise HTTPException(status_code=404, detail=f"city_id {city_id} not found")
    result = [t for t in TEMPERATURES if t["city_id"] == city_id]
    if month is not None:
        result = [t for t in result if t["month"] == month]
    if year is not None:
        result = [t for t in result if t["year"] == year]
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
