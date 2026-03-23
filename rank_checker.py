import asyncio
import logging
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEARCH_URL = "https://map.naver.com/p/api/search"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://map.naver.com/",
}
MAX_RANK = 50
DISPLAY_COUNT = 20


async def check_rank(keyword: str, place_name: str) -> dict:
    """네이버 지도 API로 업체 순위를 조회한다."""
    rank = 0

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as client:
            for page in range(1, (MAX_RANK // DISPLAY_COUNT) + 2):
                params = {
                    "caller": "pcweb",
                    "query": keyword,
                    "type": "all",
                    "page": page,
                    "displayCount": DISPLAY_COUNT,
                }

                resp = await client.get(SEARCH_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

                # 검색 결과 추출
                place_list = (
                    data.get("result", {}).get("place", {}).get("list", [])
                )

                if not place_list:
                    break

                for item in place_list:
                    name = item.get("name", "")
                    if not name:
                        continue

                    # 광고 건너뛰기
                    if item.get("isAdPlace") or item.get("isAd"):
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

        return {
            "rank": None,
            "message": f'"{place_name}"을(를) "{keyword}" 검색 결과 상위 50위 내에서 찾을 수 없습니다. 업체명을 네이버 지도에 등록된 정확한 이름으로 입력했는지 확인해주세요.',
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return {
            "rank": None,
            "message": "네이버 지도 검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            "rank": None,
            "message": f"오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        }
