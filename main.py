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

# === 환경변수 (깃허브 Actions에서 Secrets로 받음) ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
INTERPARK_ID = os.environ.get("INTERPARK_ID")
INTERPARK_PW = os.environ.get("INTERPARK_PW")

def calculate_display_hour(now=None):
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
    """ 발권량을 텔레그램 메시지로 전송 """
    formatted_count = f"{ticket_count:,}"
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
    current_url = driver.current_url
    if current_url == "data:," or current_url != expected_url:
        print(f"⚠️ 잘못된 URL 감지: {current_url}. 올바른 URL로 이동 중...")
        driver.get(expected_url)
        time.sleep(3)
        if driver.current_url == expected_url:
            print("✅ 올바른 URL로 이동 완료!")
        else:
            raise Exception(f"❌ URL 이동 실패: {driver.current_url}")

def main():
    # 1) ChromeOptions: 헤드리스 + 창 크기 지정
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")  # 헤드리스 모드
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1197,1102")  
    # ↑ 브라우저(가상) 창 크기를 1197×1102 로 설정

    # 2) ChromeDriverManager: 자동으로 크롬드라이버 버전에 맞게 설치
    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)

    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # === 아래는 기존 로직: 파일 다운로드 경로 등 ===
        download_path = os.path.expanduser("~/Downloads/interpark")
        if not os.path.exists(download_path):
            os.makedirs(download_path)

        wait = WebDriverWait(driver, 10)

        # === 인터파크 관리자 로그인 ===
        expected_url = "https://tadmin20.interpark.com/"
        driver.get(expected_url)
        ensure_correct_url(driver, expected_url)

        # 팝업 감지 및 닫기
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

        # 로그인 버튼 클릭
        try:
            login_button = wait.until(EC.element_to_be_clickable((By.ID, "btnLogin")))
            login_button.click()
            print("✅ 로그인 버튼 클릭 완료!")
        except Exception as e:
            print(f"❌ 로그인 버튼 클릭 실패: {e}")

        # 2차 인증 창 처리
        try:
            not_proceed_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "boxIcon")))
            not_proceed_button.click()
            print("✅ '진행하지 않음' 버튼 클릭 완료")

            confirm_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btnConfirm")))
            confirm_button.click()
            print("✅ '확인' 버튼 클릭 완료")
        except:
            print("⚠️ 2차 인증 창이 나타나지 않음. 다음 단계 진행")

        # === 발권량 페이지 이동 ===
        driver.get("https://tadmin20.interpark.com/stat/ticketprintinfo")
        time.sleep(3)
        print("✅ 발권량 페이지 이동 완료!")

        # 상품 검색 (돋보기 버튼 클릭)
        search_button = driver.find_element(By.ID, "btnSearch_lookupGoods")
        search_button.click()
        time.sleep(2)
        print("✅ 상품 검색 창 열기 완료!")

        # === (중요) 절대좌표 (260, 286) 더블클릭 ===
        # 헤드리스 모드 + window-size=1197,1102 상태에서 해당 좌표가 맞길 기대
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

        # 엑셀 다운로드
        excel_button = wait.until(EC.element_to_be_clickable((By.ID, "btnExcel0")))
        excel_button.click()
        print("✅ 엑셀 다운로드 시작!")

        time.sleep(10)

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

        df = pd.read_excel(latest_file, engine="openpyxl")
        last_row = df.iloc[:, 7].dropna().values[-1]
        print(f"🎟️ 현재 발권량 (엑셀에서 추출): {last_row}")

        send_telegram_message(last_row)
        os.remove(latest_file)
        print(f"🗑️ 다운로드된 엑셀 파일 삭제 완료: {latest_file}")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
