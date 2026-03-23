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

# 서울 중심 좌표 (기본값)
DEFAULT_X = "126.9784"
DEFAULT_Y = "37.5665"

DISPLAY_PER_PAGE = 10
MAX_RANK = 30


def _build_query(keyword: str, start: int) -> list[dict]:
    """GraphQL 쿼리 페이로드를 생성한다."""
    query = (
        "query {"
        f'  restaurantList(input: {{'
        f'    query: "{keyword}",'
        f"    start: {start},"
        f"    display: {DISPLAY_PER_PAGE},"
        f'    deviceType: "mobile",'
        f'    x: "{DEFAULT_X}",'
        f'    y: "{DEFAULT_Y}"'
        f"  }}) {{"
        f"    items {{ id name }}"
        f"    total"
        f"  }}"
        f"}}"
    )
    return [{"query": query}]


async def check_rank(keyword: str, place_name: str) -> dict:
    """네이버 플레이스 GraphQL API로 업체 순위를 조회한다."""
    rank = 0

    try:
        async with httpx.AsyncClient(
            headers=HEADERS, timeout=10, follow_redirects=True
        ) as client:
            pages = MAX_RANK // DISPLAY_PER_PAGE

            for page in range(pages):
                start = page * DISPLAY_PER_PAGE + 1
                payload = _build_query(keyword, start)

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
                    if not name:
                        continue

                    rank += 1
                    logger.info(f"  #{rank}: {name}")

                    if place_name in name or name in place_name:
                        return {
                            "rank": rank,
                            "message": f'"{place_name}"은(는) "{keyword}" 검색 결과 {rank}위입니다.',
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

        return {
            "rank": None,
            "message": (
                f'"{place_name}"을(를) "{keyword}" 검색 결과 '
                f"상위 {MAX_RANK}위 내에서 찾을 수 없습니다. "
                f"업체명을 네이버 지도에 등록된 정확한 이름으로 입력했는지 확인해주세요."
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
