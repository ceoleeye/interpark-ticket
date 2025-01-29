import time
import os
import pandas as pd
import requests

from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+ 에서 사용 가능
# (Python 3.8 이하라면 'pytz'를 사용)

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# === 깃허브 Actions 등에서 불러오는 환경변수 ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
INTERPARK_ID = os.environ.get("INTERPARK_ID")
INTERPARK_PW = os.environ.get("INTERPARK_PW")


def calculate_display_hour(now=None):
    """
    - now가 없으면, 한국 시간(Asia/Seoul)의 현재 시각을 구한다.
    - 분(minute)이 30분 미만이면 그대로 시(hour),
      30분 이상이면 +1시 로 반환 (24시 초과시 %24)
    """
    if not now:
        # 한국시간
        now = datetime.now(ZoneInfo("Asia/Seoul"))

    hour = now.hour
    minute = now.minute
    if minute < 30:
        display_hour = hour
    else:
        display_hour = (hour + 1) % 24
    return display_hour


def send_telegram_message(ticket_count):
    """
    발권수를 텔레그램 채널로 알림.
    """
    display_hour = calculate_display_hour()
    hour_text = f"{display_hour:02d}:00"    # 예: 18 -> "18:00"

    # 콤마 추가 등 형식
    formatted_count = f"{ticket_count:,}"
    message = f"{hour_text} 발권수 {formatted_count} 입니다.\n대기 없습니다."

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    resp = requests.post(url, data=payload)

    if resp.status_code == 200:
        print(f"✅ 텔레그램 전송 완료: {message}")
    else:
        print(f"❌ 텔레그램 전송 실패: {resp.text}")


def ensure_correct_url(driver, expected_url):
    """
    현재 URL이 올바른지 확인, 아니면 재이동
    """
    current_url = driver.current_url
    if current_url == "data:," or current_url != expected_url:
        print(f"⚠️ 잘못된 URL 감지: {current_url}, 재이동 중...")
        driver.get(expected_url)
        time.sleep(3)
        if driver.current_url == expected_url:
            print("✅ 올바른 URL로 이동 완료!")
        else:
            raise Exception(f"❌ URL 이동 실패: {driver.current_url}")


def main():
    # 1) ChromeOptions 설정
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")  # 헤드리스 모드
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1197,1102")  
    # - 이 해상도로 맞춰서 좌표 더블클릭 (260,286)이 정상 동작하도록

    # - 기본 다운로드 설정 (Headless 모드에서 일부만 적용, CDP setDownloadBehavior가 최종)
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": os.path.expanduser("~/Downloads/interpark"),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })

    # 2) WebDriver Manager 통해 ChromeDriver 설치 경로
    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)

    # 3) 드라이버 생성
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # === (A) Headless에서 파일 다운로드 허용 (CDP 명령) ===
        download_path = os.path.expanduser("~/Downloads/interpark")
        if not os.path.exists(download_path):
            os.makedirs(download_path)

        driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {
                "behavior": "allow",
                "downloadPath": download_path
            }
        )

        wait = WebDriverWait(driver, 10)

        # === (B) 인터파크 관리자 로그인 페이지 진입 ===
        expected_url = "https://tadmin20.interpark.com/"
        driver.get(expected_url)
        ensure_correct_url(driver, expected_url)

        # 팝업 닫기
        main_window = driver.current_window_handle
        for window_handle in driver.window_handles:
            driver.switch_to.window(window_handle)
            if "Popup1.html" in driver.current_url:
                print(f"✅ 팝업 감지됨: {driver.current_url}")
                driver.close()
                print("✅ 팝업 닫기 완료!")
                driver.switch_to.window(main_window)
                break

        # 로그인 정보 입력
        try:
            username_field = wait.until(EC.presence_of_element_located((By.ID, "UserID")))
            password_field = wait.until(EC.presence_of_element_located((By.ID, "UserPassword")))
            username_field.send_keys(INTERPARK_ID)
            password_field.send_keys(INTERPARK_PW)
            print("✅ 로그인 정보 입력 완료!")
        except Exception as e:
            print(f"❌ 로그인 필드 로드 실패: {e}")

        # 로그인 버튼
        try:
            login_button = wait.until(EC.element_to_be_clickable((By.ID, "btnLogin")))
            login_button.click()
            print("✅ 로그인 버튼 클릭 완료!")
        except Exception as e:
            print(f"❌ 로그인 버튼 클릭 실패: {e}")

        # 2차 인증 (진행하지 않음)
        try:
            not_proceed_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "boxIcon")))
            not_proceed_button.click()
            print("✅ '진행하지 않음' 버튼 클릭 완료")

            confirm_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btnConfirm")))
            confirm_button.click()
            print("✅ '확인' 버튼 클릭 완료")
        except:
            print("⚠️ 2차 인증 창이 나타나지 않음. 다음 단계 진행")

        # 발권량 페이지 이동
        driver.get("https://tadmin20.interpark.com/stat/ticketprintinfo")
        time.sleep(3)
        print("✅ 발권량 페이지 이동 완료!")

        # 상품 검색 버튼 (돋보기)
        search_button = driver.find_element(By.ID, "btnSearch_lookupGoods")
        search_button.click()
        time.sleep(2)
        print("✅ 상품 검색 창 열기 완료!")

        # (C) 절대좌표 더블클릭
        action = ActionChains(driver)
        action.move_by_offset(260, 286).double_click().perform()
        time.sleep(2)
        print("✅ 상품 더블클릭 완료!")

        # 발권일 선택
        calendar_icon = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "fa.fa-calendar.bigger-110")))
        calendar_icon.click()
        time.sleep(2)

        driver.execute_script("document.querySelector('.today.day').click();")
        time.sleep(2)
        print("✅ 발권일 선택 완료!")

        # 조회 버튼
        search_button2 = wait.until(EC.element_to_be_clickable((By.ID, "btnSearch")))
        search_button2.click()
        time.sleep(3)
        print("✅ 조회 버튼 클릭 완료!")

        # (D) 엑셀 다운로드 버튼
        excel_button = wait.until(EC.element_to_be_clickable((By.ID, "btnExcel0")))
        excel_button.click()
        print("✅ 엑셀 다운로드 시작!")

        # 다운로드 대기
        time.sleep(10)

        # 다운로드된 파일 찾기
        files = sorted(
            [f for f in os.listdir(download_path) if f.startswith("티켓발권현황") and (f.endswith(".xls") or f.endswith(".xlsx"))],
            key=lambda x: os.path.getctime(os.path.join(download_path, x)),
            reverse=True
        )

        if not files:
            print("❌ 엑셀 파일 다운로드 실패")
            return

        latest_file = os.path.join(download_path, files[0])
        print(f"✅ 엑셀 다운로드 완료: {latest_file}")

        # (E) 엑셀 읽기
        df = pd.read_excel(latest_file, engine="openpyxl")
        last_row = df.iloc[:, 7].dropna().values[-1]
        print(f"🎟️ 현재 발권량 (엑셀에서 추출): {last_row}")

        # (F) 텔레그램 전송
        send_telegram_message(last_row)

        # (G) 파일 삭제
        os.remove(latest_file)
        print(f"🗑️ 다운로드된 엑셀 파일 삭제 완료: {latest_file}")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
