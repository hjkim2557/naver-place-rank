import asyncio
import logging
import os
import time
import urllib.parse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
    StaleElementReferenceException,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_driver = None
_lock = asyncio.Lock()

# 업체명을 찾기 위한 CSS 셀렉터 후보 목록 (네이버 지도 구조 변경 대응)
NAME_SELECTORS = [
    "span.q2LdB",
    "span.place_bluelink",
    "span.YwYLL",
    "span.TYaxT",
    "a.place_bluelink span",
    "div.CHC5F a.place_bluelink",
    "div.ouxiq a span",
]

# 페이지 이동 버튼 셀렉터 후보
NEXT_PAGE_SELECTORS = [
    "a.eUTV2",
    "button.eUTV2",
    "a[aria-label='다음']",
    "button[aria-label='다음']",
]


def _create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1280,720")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--no-first-run")
    options.add_argument("--single-process")
    options.add_argument("--js-flags=--max-old-space-size=256")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin:
        options.binary_location = chrome_bin

    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
    if chromedriver_path:
        service = Service(executable_path=chromedriver_path)
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(2)
    return driver


def _get_driver():
    global _driver
    if _driver is None:
        _driver = _create_driver()
    return _driver


def _reset_driver():
    global _driver
    if _driver is not None:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None


def _extract_place_name(item):
    """여러 셀렉터를 시도하여 업체명을 추출한다."""
    for selector in NAME_SELECTORS:
        try:
            els = item.find_elements(By.CSS_SELECTOR, selector)
            for el in els:
                text = el.text.strip()
                if text and len(text) > 0:
                    return text
        except (StaleElementReferenceException, NoSuchElementException):
            continue
    return None


def _is_ad_item(item):
    """광고 항목인지 확인한다."""
    try:
        text = item.text
        if not text:
            return True
        # 광고 라벨 확인
        if "광고" in text[:20]:
            return True
        ad_elements = item.find_elements(By.CSS_SELECTOR, "span[class*='ad'], span[class*='Ad'], em.ad")
        if ad_elements:
            for ad_el in ad_elements:
                if "광고" in ad_el.text:
                    return True
    except (StaleElementReferenceException, Exception):
        return True
    return False


def _click_next_page(driver):
    """다음 페이지 버튼 클릭 시도."""
    for selector in NEXT_PAGE_SELECTORS:
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, selector)
            for btn in buttons:
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    return True
        except Exception:
            continue
    return False


def _search_rank(keyword: str, place_name: str) -> dict:
    """동기 함수: Selenium으로 네이버 지도 검색 후 순위 반환."""
    driver = _get_driver()
    max_pages = 5
    max_rank = 50
    rank = 0
    start_time = time.time()
    timeout = 60  # 최대 60초

    try:
        encoded_keyword = urllib.parse.quote(keyword)
        url = f"https://map.naver.com/p/search/{encoded_keyword}"
        logger.info(f"Navigating to: {url}")
        driver.get(url)
        time.sleep(4)

        # searchIframe으로 전환
        wait = WebDriverWait(driver, 20)
        search_iframe = wait.until(
            EC.presence_of_element_located((By.ID, "searchIframe"))
        )
        driver.switch_to.frame(search_iframe)
        logger.info("Switched to searchIframe")
        time.sleep(3)

        for page in range(max_pages):
            if time.time() - start_time > timeout:
                logger.info("Timeout reached")
                break
            logger.info(f"Scanning page {page + 1}")

            # 검색 결과 리스트 로드 대기
            try:
                wait = WebDriverWait(driver, 10)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#_pcmap_list_scroll_container, ul")))
            except TimeoutException:
                logger.warning("Result list container not found")
                break

            time.sleep(2)

            # 스크롤하여 모든 결과 로드
            try:
                scroll_container = driver.find_element(By.CSS_SELECTOR, "#_pcmap_list_scroll_container")
            except NoSuchElementException:
                scroll_container = None

            if scroll_container:
                driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight",
                    scroll_container,
                )
                time.sleep(1)
                driver.execute_script("arguments[0].scrollTop = 0", scroll_container)
                time.sleep(1)

            # 검색 결과 li 수집
            items = driver.find_elements(By.CSS_SELECTOR, "li.UEzoS, li.VLTHu, li[data-laim-exp-id]")
            if not items:
                # fallback: 모든 li
                items = driver.find_elements(By.CSS_SELECTOR, "ul > li")
            logger.info(f"Found {len(items)} list items on page {page + 1}")

            for item in items:
                if _is_ad_item(item):
                    continue

                shop_name = _extract_place_name(item)
                if not shop_name:
                    continue

                rank += 1
                logger.info(f"  #{rank}: {shop_name}")

                if place_name in shop_name or shop_name in place_name:
                    return {
                        "rank": rank,
                        "message": f'"{place_name}"은(는) "{keyword}" 검색 결과 {rank}위입니다.',
                    }

                if rank >= max_rank:
                    break

            if rank >= max_rank or time.time() - start_time > timeout:
                break

            # 다음 페이지로 이동
            if rank >= max_rank or time.time() - start_time > timeout:
                break
            if page < max_pages - 1:
                if not _click_next_page(driver):
                    logger.info("No next page button found")
                    break
                time.sleep(3)

        return {
            "rank": None,
            "message": f'"{place_name}"을(를) "{keyword}" 검색 결과 상위 50위 내에서 찾을 수 없습니다. 업체명을 네이버 지도에 등록된 정확한 이름으로 입력했는지 확인해주세요.',
        }

    except TimeoutException:
        logger.error("Timeout waiting for page elements")
        return {
            "rank": None,
            "message": "검색 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
        }
    except WebDriverException as e:
        logger.error(f"WebDriver error: {e}")
        _reset_driver()
        return {
            "rank": None,
            "message": f"브라우저 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        _reset_driver()
        return {
            "rank": None,
            "message": f"오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        }
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass


async def check_rank(keyword: str, place_name: str) -> dict:
    """비동기 래퍼: Lock을 사용하여 동시 접근 제어."""
    async with _lock:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _search_rank, keyword, place_name)
        return result
