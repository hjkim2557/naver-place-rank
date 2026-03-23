import logging
import re
import json
import urllib.parse

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    ),
}

# 서울 중심 좌표 (기본값)
DEFAULT_X = "126.9784"
DEFAULT_Y = "37.5665"

MAX_DISPLAY = 10


async def check_rank(keyword: str, place_name: str) -> dict:
    """네이버 플레이스 검색에서 업체 순위를 조회한다."""
    try:
        encoded = urllib.parse.quote(keyword)
        url = (
            f"https://m.place.naver.com/restaurant/list"
            f"?query={encoded}&x={DEFAULT_X}&y={DEFAULT_Y}"
        )

        async with httpx.AsyncClient(
            headers=HEADERS, timeout=10, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        # __APOLLO_STATE__에서 데이터 추출
        match = re.search(
            r"window\.__APOLLO_STATE__\s*=\s*(\{.*?\});",
            resp.text,
            re.DOTALL,
        )
        if not match:
            logger.error("APOLLO_STATE not found")
            return {
                "rank": None,
                "message": "검색 결과를 파싱하지 못했습니다. 잠시 후 다시 시도해주세요.",
            }

        data = json.loads(match.group(1))
        root = data.get("ROOT_QUERY", {})

        # restaurantList에서 순위 목록 추출 (isNmap=false, filterOpening 없는 메인 리스트)
        items_ordered = []
        for key, val in root.items():
            if not key.startswith("restaurantList("):
                continue
            if "filterOpening" in key:
                continue
            if "ad" in key.lower():
                continue
            if not isinstance(val, dict):
                continue

            raw_items = val.get("items", [])
            if len(raw_items) < MAX_DISPLAY:
                continue

            for item in raw_items:
                ref = item.get("__ref", "")
                ref_data = data.get(ref, {})
                name = ref_data.get("name", "")
                if name:
                    items_ordered.append(name)
            break

        if not items_ordered:
            # fallback: 모든 ListSummary 항목 수집 (순서 보장 안 됨)
            for key, val in root.items():
                if not key.startswith("restaurantList("):
                    continue
                if "ad" in key.lower():
                    continue
                if not isinstance(val, dict):
                    continue
                for item in val.get("items", []):
                    ref = item.get("__ref", "")
                    ref_data = data.get(ref, {})
                    name = ref_data.get("name", "")
                    if name and name not in items_ordered:
                        items_ordered.append(name)

        logger.info(f"Found {len(items_ordered)} places for '{keyword}'")

        for rank, name in enumerate(items_ordered, 1):
            logger.info(f"  #{rank}: {name}")
            if place_name in name or name in place_name:
                return {
                    "rank": rank,
                    "message": f'"{place_name}"은(는) "{keyword}" 검색 결과 {rank}위입니다.',
                }

        if not items_ordered:
            return {
                "rank": None,
                "message": f'"{keyword}" 검색 결과를 가져오지 못했습니다. 다른 키워드로 시도해주세요.',
            }

        return {
            "rank": None,
            "message": (
                f'"{place_name}"을(를) "{keyword}" 검색 결과 '
                f"상위 {len(items_ordered)}위 내에서 찾을 수 없습니다. "
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
