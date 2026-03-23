from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from rank_checker import check_rank

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
