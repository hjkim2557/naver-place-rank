import logging
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://nx-api.place.naver.com/graphql"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Content-Type": "application/json",
    "Referer": "https://m.place.naver.com/",
    "Origin": "https://m.place.naver.com",
}

DEFAULT_X = "126.9784"
DEFAULT_Y = "37.5665"

DISPLAY_PER_PAGE = 100
MAX_RANK = 300


def _build_query(keyword: str, start: int, display: int) -> list[dict]:
    query = (
        "query {"
        f"  restaurantList(input: {{"
        f'    query: "{keyword}",'
        f"    start: {start},"
        f"    display: {display},"
        f'    deviceType: "mobile",'
        f'    x: "{DEFAULT_X}",'
        f'    y: "{DEFAULT_Y}"'
        f"  }}) {{"
        f"    items {{ id name saveCount visitorReviewCount blogCafeReviewCount }}"
        f"    total"
        f"  }}"
        f"}}"
    )
    return [{"query": query}]


async def check_rank(keyword: str, place_name: str = "", place_id: str = "") -> dict:
    """네이버 플레이스 GraphQL API로 업체 순위를 조회한다."""
    rank = 0

    try:
        async with httpx.AsyncClient(
            headers=HEADERS, timeout=15, follow_redirects=True
        ) as client:
            pages = MAX_RANK // DISPLAY_PER_PAGE

            for page in range(pages):
                start = page * DISPLAY_PER_PAGE + 1
                payload = _build_query(keyword, start, DISPLAY_PER_PAGE)

                resp = await client.post(GRAPHQL_URL, json=payload)
                resp.raise_for_status()

                data = resp.json()
                items = (
                    data[0]
                    .get("data", {})
                    .get("restaurantList", {})
                    .get("items", [])
                )

                if not items:
                    break

                for item in items:
                    name = item.get("name", "")
                    item_id = item.get("id", "")
                    if not name:
                        continue

                    rank += 1

                    # place_id로 매칭 (우선) 또는 업체명으로 매칭
                    matched = False
                    if place_id and item_id == place_id:
                        matched = True
                    elif place_name and (
                        place_name in name or name in place_name
                    ):
                        matched = True

                    if matched:
                        return {
                            "rank": rank,
                            "name": name,
                            "place_id": item_id,
                            "save_count": item.get("saveCount", "-"),
                            "visitor_review": item.get("visitorReviewCount", "-"),
                            "blog_review": item.get("blogCafeReviewCount", "-"),
                            "message": f'"{name}"은(는) "{keyword}" 검색 결과 {rank}위입니다.',
                        }

                    if rank >= MAX_RANK:
                        break

                if rank >= MAX_RANK:
                    break

        if rank == 0:
            return {
                "rank": None,
                "message": f'"{keyword}" 검색 결과를 가져오지 못했습니다. 다른 키워드로 시도해주세요.',
            }

        search_term = place_name or place_id
        return {
            "rank": None,
            "message": (
                f'"{search_term}"을(를) "{keyword}" 검색 결과 '
                f"상위 {rank}위 내에서 찾을 수 없습니다."
            ),
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return {
            "rank": None,
            "message": "네이버 검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            "rank": None,
            "message": "오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        }
