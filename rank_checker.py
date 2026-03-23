import asyncio
import os
import time

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
)

_driver = None
_lock = asyncio.Lock()


def _create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
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
    driver.execute_cdl_cmd = None  # placeholder
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    driver.set_page_load_timeout(30)
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


def _search_rank(keyword: str, place_name: str) -> dict:
    """동기 함수: Selenium으로 네이버 지도 검색 후 순위 반환."""
    driver = _get_driver()
    max_pages = 5
    rank = 0

    try:
        url = f"https://map.naver.com/p/search/{keyword}"
        driver.get(url)
        time.sleep(3)

        # searchIframe으로 전환
        wait = WebDriverWait(driver, 15)
        search_iframe = wait.until(
            EC.presence_of_element_located((By.ID, "searchIframe"))
        )
        driver.switch_to.frame(search_iframe)
        time.sleep(2)

        for page in range(max_pages):
            # 업체 목록 로드 대기
            wait = WebDriverWait(driver, 10)
            wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li"))
            )
            time.sleep(1)

            items = driver.find_elements(By.CSS_SELECTOR, "li")

            for item in items:
                # 광고 항목 건너뛰기
                try:
                    item_text = item.text
                    if "광고" in item_text:
                        continue
                except Exception:
                    continue

                # 업체명 추출
                try:
                    name_elements = item.find_elements(
                        By.CSS_SELECTOR, "span.q2LdB"
                    )
                    if not name_elements:
                        continue

                    shop_name = name_elements[0].text.strip()
                    if not shop_name:
                        continue

                    rank += 1

                    if place_name in shop_name or shop_name in place_name:
                        return {
                            "rank": rank,
                            "message": f'"{place_name}"은(는) "{keyword}" 검색 결과 {rank}위입니다.',
                        }
                except Exception:
                    continue

            # 다음 페이지로 이동
            if page < max_pages - 1:
                try:
                    next_buttons = driver.find_elements(
                        By.CSS_SELECTOR, "a.eUTV2"
                    )
                    clicked = False
                    for btn in next_buttons:
                        # 마지막(다음) 버튼 클릭
                        if btn.is_displayed() and btn.is_enabled():
                            btn.click()
                            clicked = True
                            time.sleep(2)
                            break
                    if not clicked:
                        break
                except (NoSuchElementException, TimeoutException):
                    break

        return {
            "rank": None,
            "message": f'"{place_name}"을(를) "{keyword}" 검색 결과 상위 {rank}위 내에서 찾을 수 없습니다. 순위권({rank}위) 밖입니다.',
        }

    except TimeoutException:
        return {
            "rank": None,
            "message": "검색 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
        }
    except WebDriverException as e:
        _reset_driver()
        return {
            "rank": None,
            "message": f"브라우저 오류가 발생했습니다. 잠시 후 다시 시도해주세요. ({str(e)[:100]})",
        }
    except Exception as e:
        _reset_driver()
        return {
            "rank": None,
            "message": f"오류가 발생했습니다: {str(e)[:100]}",
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
