import os
import httpx

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://zbjionhaoaplyappyxcn.supabase.co"
)
SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY", "sb_publishable_zinyGplWTkRQZ6yuPUcamA_txNc8fRo"
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def _url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"


async def add_shop(keyword: str, place_name: str, place_id: str, email: str = "") -> dict:
    async with httpx.AsyncClient(headers=HEADERS, timeout=10) as c:
        resp = await c.post(
            _url("shops"),
            json={"keyword": keyword, "place_name": place_name, "place_id": place_id, "email": email},
        )
        resp.raise_for_status()
        return resp.json()[0]


async def get_shops() -> list[dict]:
    async with httpx.AsyncClient(headers=HEADERS, timeout=10) as c:
        resp = await c.get(_url("shops"), params={"select": "*", "order": "created_at.desc"})
        resp.raise_for_status()
        return resp.json()


async def get_shop(shop_id: int) -> dict | None:
    async with httpx.AsyncClient(headers=HEADERS, timeout=10) as c:
        resp = await c.get(
            _url("shops"),
            params={"select": "*", "id": f"eq.{shop_id}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else None


async def delete_shop(shop_id: int):
    async with httpx.AsyncClient(headers=HEADERS, timeout=10) as c:
        await c.delete(_url("shops"), params={"id": f"eq.{shop_id}"})


async def add_rank_record(shop_id: int, rank: int | None, save_count: str, visitor_review: str, blog_review: str):
    async with httpx.AsyncClient(headers=HEADERS, timeout=10) as c:
        resp = await c.post(
            _url("rank_history"),
            json={
                "shop_id": shop_id,
                "rank": rank,
                "save_count": save_count,
                "visitor_review": visitor_review,
                "blog_review": blog_review,
            },
        )
        resp.raise_for_status()


async def get_rank_history(shop_id: int, days: int = 30) -> list[dict]:
    async with httpx.AsyncClient(headers=HEADERS, timeout=10) as c:
        resp = await c.get(
            _url("rank_history"),
            params={
                "select": "*",
                "shop_id": f"eq.{shop_id}",
                "order": "checked_at.asc",
                "checked_at": f"gte.now()-{days}d",
            },
        )
        # fallback: Supabase doesn't support now()-Nd, use a different approach
        if resp.status_code != 200:
            from datetime import datetime, timedelta, timezone
            since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            resp = await c.get(
                _url("rank_history"),
                params={
                    "select": "*",
                    "shop_id": f"eq.{shop_id}",
                    "order": "checked_at.asc",
                    "checked_at": f"gte.{since}",
                },
            )
        resp.raise_for_status()
        return resp.json()
