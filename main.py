import time
import os
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

# === 1) 민감 정보: 환경변수로 받기 ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")       # 예: "123456:ABC..."
CHAT_ID = os.environ.get("CHAT_ID")          # 예: "-4184976892"
INTERPARK_ID = os.environ.get("INTERPARK_ID")  # 예: "ieum00"
INTERPARK_PW = os.environ.get("INTERPARK_PW")  # 예: "dldma#1A@@"

# ✅ 다운로드 경로 설정 (Mac 기준: ~/Downloads/interpark)
download_path = os.path.expanduser("~/Downloads/interpark")
if not os.path.exists(download_path):  # 폴더 없으면 생성
    os.makedirs(download_path)

# ✅ Chrome 다운로드 설정
chrome_options = webdriver.ChromeOptions()
# === 2) 헤드리스 모드 추가 + 기타 옵션 ===
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920x1080")

chrome_options.add_experimental_option("prefs", {
    "download.default_directory": download_path,  # 지정된 다운로드 폴더
    "download.prompt_for_download": False,        # 다운로드 창 뜨지 않도록 설정
    "safebrowsing.enabled": True
})

# ✅ WebDriver 설정
service = Service(ChromeDriverManager().install())

def calculate_display_hour(now=None):
    """
    현재 분(minute)이 30분 미만이면 그대로 현재 시(hour),
    30분 이상이면 +1 시간을 반환. 24시를 넘어가면 0시로 처리.
    """
    if not now:
        now = datetime.now()
    hour = now.hour
    minute = now.minute
    if minute < 30:
        display_hour = hour
    else:
        display_hour = (hour + 1) % 24
    return display_hour

def send_telegram_message(ticket_count):
    """ 발권량을 텔레그램으로 전송 """
    formatted_count = f"{ticket_count:,}"  # 콤마 추가
    display_hour = calculate_display_hour()
    hour_text = f"{display_hour:02d}:00"
    message = f"{hour_text} 발권수 {formatted_count} 입니다.\n대기 없습니다."

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}

    response = requests.post(url, data=payload)
    if response.status_code == 200:
        print(f"✅ 텔레그램 전송 완료: {message}")
    else:
        print(f"❌ 텔레그램 전송 실패: {response.text}")

def ensure_correct_url(driver, expected_url):
    """ 현재 URL을 확인하고 올바른 URL로 리다이렉트 """
    current_url = driver.current_url
    if current_url == "data:," or current_url != expected_url:
        print(f"⚠️ 잘못된 URL 감지: {current_url}. 올바른 URL로 이동 중...")
        driver.get(expected_url)
        time.sleep(3)
        if driver.current_url == expected_url:
            print("✅ 올바른 URL로 이동 완료!")
        else:
            raise Exception(f"❌ URL 이동 실패: {driver.current_url}")

with webdriver.Chrome(service=service, options=chrome_options) as driver:
    try:
        wait = WebDriverWait(driver, 10)

        # ✅ 인터파크 관리자 로그인 페이지 이동
        expected_url = "https://tadmin20.interpark.com/"
        driver.get(expected_url)
        ensure_correct_url(driver, expected_url)

        # ✅ 팝업 감지 및 닫기
        main_window = driver.current_window_handle
        for window_handle in driver.window_handles:
            driver.switch_to.window(window_handle)
            if "Popup1.html" in driver.current_url:
                print(f"✅ 팝업 감지됨: {driver.current_url}")
                driver.close()
                print("✅ 팝업 닫기 완료!")
                driver.switch_to.window(main_window)
                break

        # ✅ 로그인 정보 입력
        try:
            username_field = wait.until(EC.presence_of_element_located((By.ID, "UserID")))
            password_field = wait.until(EC.presence_of_element_located((By.ID, "UserPassword")))
            username_field.send_keys(INTERPARK_ID)  # 환경변수로 받음
            password_field.send_keys(INTERPARK_PW)  # 환경변수로 받음
            print("✅ 로그인 정보 입력 완료!")
        except Exception as e:
            print(f"❌ 로그인 필드 로드 실패: {e}")

        # ✅ 로그인 버튼 클릭
        try:
            login_button = wait.until(EC.element_to_be_clickable((By.ID, "btnLogin")))
            login_button.click()
            print("✅ 로그인 버튼 클릭 완료!")
        except Exception as e:
            print(f"❌ 로그인 버튼 클릭 실패: {e}")

        # ✅ 2차 인증 창 처리
        try:
            not_proceed_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "boxIcon")))
            not_proceed_button.click()
            print("✅ '진행하지 않음' 버튼 클릭 완료")

            confirm_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btnConfirm")))
            confirm_button.click()
            print("✅ '확인' 버튼 클릭 완료")
        except:
            print("⚠️ 2차 인증 창이 나타나지 않음. 다음 단계 진행")

        # ✅ 발권량 페이지 이동
        driver.get("https://tadmin20.interpark.com/stat/ticketprintinfo")
        time.sleep(3)
        print("✅ 발권량 페이지 이동 완료!")

        # ✅ 상품 검색 (돋보기 버튼 클릭)
        search_button = driver.find_element(By.ID, "btnSearch_lookupGoods")
        search_button.click()
        time.sleep(2)
        print("✅ 상품 검색 창 열기 완료!")

        # ✅ 좌표 클릭 (경고: Headless 모드에서 안 될 가능성)
        action = ActionChains(driver)
        action.move_by_offset(260, 286).double_click().perform()
        time.sleep(2)
        print("✅ 상품 더블클릭 완료!")

        # ✅ 발권일 선택
        calendar_icon = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "fa.fa-calendar.bigger-110")))
        calendar_icon.click()
        time.sleep(2)

        driver.execute_script("document.querySelector('.today.day').click();")
        time.sleep(2)
        print("✅ 발권일 선택 완료!")

        # ✅ 조회 버튼 클릭
        search_button = wait.until(EC.element_to_be_clickable((By.ID, "btnSearch")))
        search_button.click()
        time.sleep(3)
        print("✅ 조회 버튼 클릭 완료!")

        # ✅ 엑셀 다운로드 버튼 클릭
        excel_button = wait.until(EC.element_to_be_clickable((By.ID, "btnExcel0")))
        excel_button.click()
        print("✅ 엑셀 다운로드 시작!")
        time.sleep(10)

        # ✅ 엑셀 파일 찾기
        files = sorted(
            [f for f in os.listdir(download_path) if f.startswith("티켓발권현황") and (f.endswith(".xls") or f.endswith(".xlsx"))],
            key=lambda x: os.path.getctime(os.path.join(download_path, x)),
            reverse=True
        )

        if not files:
            print("❌ 엑셀 파일 다운로드 실패")
            exit()

        latest_file = os.path.join(download_path, files[0])
        print(f"✅ 엑셀 다운로드 완료: {latest_file}")

        # ✅ 엑셀 파일 열기
        df = pd.read_excel(latest_file, engine="openpyxl")

        # ✅ H열(7번째 컬럼)의 마지막 값 가져오기
        last_row = df.iloc[:, 7].dropna().values[-1]
        print(f"🎟️ 현재 발권량 (엑셀에서 추출): {last_row}")

        # ✅ 텔레그램 메시지 전송
        send_telegram_message(last_row)

        # ✅ 파일 삭제
        os.remove(latest_file)
        print(f"🗑️ 다운로드된 엑셀 파일 삭제 완료: {latest_file}")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
