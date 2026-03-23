from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from rank_checker import check_rank
from db import add_shop, get_shops, get_shop, delete_shop, add_rank_record, get_rank_history

app = FastAPI(title="네이버 플레이스 순위 조회")
templates = Jinja2Templates(directory="templates")


@app.head("/")
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/check")
async def check(
    keyword: str = Form(...),
    place_name: str = Form(""),
    place_id: str = Form(""),
):
    keyword = keyword.strip()
    place_name = place_name.strip()
    place_id = place_id.strip()

    if not keyword or (not place_name and not place_id):
        return JSONResponse(
            {"rank": None, "message": "키워드와 업체명 또는 플레이스 ID를 입력해주세요."},
            status_code=400,
        )

    result = await check_rank(keyword, place_name=place_name, place_id=place_id)
    return JSONResponse(result)


# --- 업체 등록/관리 ---

@app.get("/manage", response_class=HTMLResponse)
async def manage_page(request: Request):
    shops = await get_shops()
    return templates.TemplateResponse("manage.html", {"request": request, "shops": shops})


@app.post("/register")
async def register_shop(
    keyword: str = Form(...),
    place_name: str = Form(""),
    place_id: str = Form(""),
):
    keyword = keyword.strip()
    place_name = place_name.strip()
    place_id = place_id.strip()

    if not keyword or (not place_name and not place_id):
        return RedirectResponse("/manage", status_code=303)

    await add_shop(keyword, place_name, place_id)
    return RedirectResponse("/manage", status_code=303)


@app.post("/unregister/{shop_id}")
async def unregister_shop(shop_id: int):
    await delete_shop(shop_id)
    return RedirectResponse("/manage", status_code=303)


# --- 리포트 ---

@app.get("/report/{shop_id}", response_class=HTMLResponse)
async def report_page(request: Request, shop_id: int):
    shop = await get_shop(shop_id)
    if not shop:
        return HTMLResponse("업체를 찾을 수 없습니다.", status_code=404)

    history = await get_rank_history(shop_id, days=30)

    # 주차별 그룹핑
    from datetime import datetime, timezone
    weeks = {1: [], 2: [], 3: [], 4: []}
    now = datetime.now(timezone.utc)
    for record in history:
        checked = datetime.fromisoformat(record["checked_at"].replace("Z", "+00:00"))
        days_ago = (now - checked).days
        if days_ago < 7:
            weeks[4].append(record)
        elif days_ago < 14:
            weeks[3].append(record)
        elif days_ago < 21:
            weeks[2].append(record)
        else:
            weeks[1].append(record)

    # 주차별 평균 순위
    weekly_avg = {}
    for week, records in weeks.items():
        ranks = [r["rank"] for r in records if r["rank"] is not None]
        weekly_avg[week] = round(sum(ranks) / len(ranks)) if ranks else None

    return templates.TemplateResponse("report.html", {
        "request": request,
        "shop": shop,
        "history": history,
        "weekly_avg": weekly_avg,
    })


# --- 크론 API (매일 자동 순위 체크) ---

@app.get("/cron/check-all")
async def cron_check_all():
    shops = await get_shops()
    results = []

    for shop in shops:
        result = await check_rank(
            shop["keyword"],
            place_name=shop.get("place_name", ""),
            place_id=shop.get("place_id", ""),
        )
        await add_rank_record(
            shop_id=shop["id"],
            rank=result.get("rank"),
            save_count=result.get("save_count", ""),
            visitor_review=result.get("visitor_review", ""),
            blog_review=result.get("blog_review", ""),
        )
        results.append({
            "shop_id": shop["id"],
            "keyword": shop["keyword"],
            "rank": result.get("rank"),
        })

    return JSONResponse({"checked": len(results), "results": results})
