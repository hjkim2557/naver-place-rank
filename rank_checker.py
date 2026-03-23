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

_lock = asyncio.Lock()

NAME_SELECTOR = "span.TYaxT"
NEXT_BUTTON_SELECTOR = "a.eUTV2"
MAX_PAGES = 5
MAX_RANK = 50


def _create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--single-process")
    options.add_argument("--window-size=1280,720")
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
    driver.set_page_load_timeout(15)
    return driver


def _search_rank(keyword: str, place_name: str) -> dict:
    """Selenium으로 네이버 지도 검색 후 순위 반환."""
    driver = _create_driver()
    rank = 0

    try:
        encoded = urllib.parse.quote(keyword)
        url = f"https://map.naver.com/p/search/{encoded}"
        logger.info(f"Navigating to: {url}")
        driver.get(url)

        # searchIframe 대기 및 전환
        wait = WebDriverWait(driver, 10)
        iframe = wait.until(
            EC.presence_of_element_located((By.ID, "searchIframe"))
        )
        driver.switch_to.frame(iframe)

        # 첫 번째 결과 로드 대기
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, NAME_SELECTOR))
        )
        time.sleep(0.5)

        for page in range(MAX_PAGES):
            logger.info(f"Scanning page {page + 1}")

            items = driver.find_elements(By.CSS_SELECTOR, "li")

            for item in items:
                try:
                    text = item.text
                    if not text or "광고" in text[:20]:
                        continue

                    els = item.find_elements(By.CSS_SELECTOR, NAME_SELECTOR)
                    if not els or not els[0].text.strip():
                        continue

                    shop_name = els[0].text.strip()
                    rank += 1
                    logger.info(f"  #{rank}: {shop_name}")

                    if place_name in shop_name or shop_name in place_name:
                        return {
                            "rank": rank,
                            "message": f'"{place_name}"은(는) "{keyword}" 검색 결과 {rank}위입니다.',
                        }

                    if rank >= MAX_RANK:
                        break
                except StaleElementReferenceException:
                    continue

            if rank >= MAX_RANK:
                break

            # 다음 페이지 이동
            if page < MAX_PAGES - 1:
                btns = driver.find_elements(By.CSS_SELECTOR, NEXT_BUTTON_SELECTOR)
                if len(btns) >= 2:
                    # 마지막 버튼 = 다음 페이지
                    btns[-1].click()
                    time.sleep(0.3)
                    try:
                        WebDriverWait(driver, 5).until(
                            EC.staleness_of(items[0])
                        )
                    except TimeoutException:
                        time.sleep(1)
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, NAME_SELECTOR)
                        )
                    )
                    time.sleep(0.3)
                else:
                    break

        return {
            "rank": None,
            "message": f'"{place_name}"을(를) "{keyword}" 검색 결과 상위 50위 내에서 찾을 수 없습니다. 업체명을 네이버 지도에 등록된 정확한 이름으로 입력했는지 확인해주세요.',
        }

    except TimeoutException:
        logger.error("Timeout")
        return {
            "rank": None,
            "message": "검색 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
        }
    except WebDriverException as e:
        logger.error(f"WebDriver error: {e}")
        return {
            "rank": None,
            "message": "브라우저 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            "rank": None,
            "message": "오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        }
    finally:
        try:
            driver.quit()
        except Exception:
            pass


async def check_rank(keyword: str, place_name: str) -> dict:
    """비동기 래퍼: Lock으로 동시 접근 제어."""
    async with _lock:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, _search_rank, keyword, place_name
        )
        return result
