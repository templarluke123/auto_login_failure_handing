import argparse
import time
import traceback
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def log_result(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    Path("login_test_results/logs").mkdir(parents=True, exist_ok=True)
    with open("login_test_results/logs/login_test_log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def run_test(url, username, password, device_type, case, headed=False):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    driver = None
    try:
        print("啟動 ChromeDriver...")
        options = webdriver.ChromeOptions()
        if not headed:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 10)

        max_attempts = {"case1": 3, "case2": 6, "case3": 9, "case4": 12}.get(case, 3)
        lock_9 = lock_12 = False

        for i in range(max_attempts):
            attempt = i + 1
            print(f"{case} - 第 {attempt} 次登入嘗試")

            driver.get(url)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(1)

            try:
                u = wait.until(EC.presence_of_element_located((By.NAME, "username")))
                p = wait.until(EC.presence_of_element_located((By.NAME, "password")))

                btn_div = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.loginButton > div")))
                btn_a = driver.find_elements(By.CSS_SELECTOR, "div.loginButton > a, a[onclick*='checklogin']")
                btn_a = btn_a[0] if btn_a else None

                u.click(); u.clear(); u.send_keys(username)
                p.click(); p.clear(); p.send_keys(password)
                log_result(f"[{case}] 第 {attempt} 次 - 填入帳密: user={u.get_attribute('value')} pass_len={len(p.get_attribute('value') or '')}")

                clicked = False
                try:
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.loginButton > div")))
                    btn_div.click()
                    clicked = True
                except Exception:
                    pass

                if not clicked and btn_a:
                    try:
                        btn_a.click()
                        clicked = True
                    except Exception:
                        try:
                            driver.execute_script("arguments[0].click();", btn_a)
                            clicked = True
                        except Exception:
                            pass

                if not clicked:
                    driver.execute_script("return checklogin(document.forms[0]);")

                time.sleep(5)

                page = driver.page_source.lower()
                current_url = driver.current_url.lower()
                locked = ("unauth" in current_url or "帳號已鎖定" in page or "try again" in page)

                if locked:
                    if case == "case1" and attempt == 3:
                        log_result(f"[Case 1] 第 {attempt} 次鎖定成功")
                        print("✅ Case1 成功")
                        break
                    elif case == "case2" and attempt == 6:
                        if "1 minute" in page:
                            log_result(f"[Case 2] 第 {attempt} 次鎖定成功（1分鐘）")
                            print("✅ Case2 成功")
                        else:
                            log_result(f"[Case 2] 第 {attempt} 次鎖定但無 1 分鐘提示")
                            print("⚠️ Case2：未偵測到 1 分鐘文字")
                        break
                    elif case == "case3":
                        if attempt in [3, 6]:
                            log_result(f"[Case 3] 第 {attempt} 次暫時鎖定，繼續測試")
                            if attempt == 6:
                                log_result("[Case 3] 等待 65 秒解除暫鎖")
                                time.sleep(65)
                            continue
                        elif attempt == 9:
                            if "5 minute" in page or "5 分鐘" in page:
                                log_result("[Case 3] 第 9 次鎖定成功（5分鐘）")
                                print("✅ Case3 成功")
                            else:
                                log_result("[Case 3] 第 9 次鎖定但無 5 分鐘提示")
                                print("⚠️ Case3：未偵測到 5 分鐘文字")
                            break
                    elif case == "case4":
                        if attempt in [3, 6]:
                            log_result(f"[Case 4] 第 {attempt} 次暫時鎖定，繼續測試")
                            if attempt == 6:
                                log_result("[Case 4] 等待 65 秒解除暫鎖")
                                time.sleep(65)
                            continue
                        elif attempt == 9:
                            if "5 minute" in page or "5 分鐘" in page:
                                lock_9 = True
                                log_result(f"[Case 4] 第 9 次鎖定成功（5分鐘）")
                                print("📌 Case4：第 9 次鎖定成功，等待 5 分鐘")
                                time.sleep(305)
                            else:
                                log_result(f"[Case 4] 第 9 次鎖定但無 5 分鐘提示")
                                print("⚠️ Case4：第 9 次未偵測到 5 分鐘文字")
                        elif attempt == 12:
                            if "5 minute" in page or "5 分鐘" in page:
                                lock_12 = True
                                log_result(f"[Case 4] 第 12 次鎖定成功（5分鐘）")
                                print("📌 Case4：第 12 次鎖定成功")
                            else:
                                log_result(f"[Case 4] 第 12 次鎖定但無 5 分鐘提示")
                                print("⚠️ Case4：第 12 次未偵測到 5 分鐘文字")
                else:
                    log_result(f"[{case}] 第 {attempt} 次登入失敗但未鎖定")

            except Exception as inner_e:
                log_result(f"[{case}] 第 {attempt} 次登入異常: {inner_e}")
                raise

        if case == "case4":
            if lock_9 and lock_12:
                print("✅ Case4 成功：第 9 與第 12 次皆鎖定 5 分鐘")
                log_result("[Case 4] 測試成功")
            else:
                print("❌ Case4 失敗：第 9 或第 12 次未達成鎖定條件")
                log_result("[Case 4] 測試失敗：條件未全達成")

    except Exception as e:
        log_result(f"[{case}] 總體錯誤：{e}\n{traceback.format_exc()}")
        print(f"❌ 發生錯誤：{e}")
    finally:
        if driver:
            driver.quit()
            print("已關閉瀏覽器")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Login test with retry and case4 fix + 5min wait")
    parser.add_argument("--url", required=True, help="Login URL")
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument("--password", required=True, help="Wrong password to trigger lockout")
    parser.add_argument("--device", required=True, choices=["router", "extender"], help="Device type")
    parser.add_argument("--case", required=True, choices=["case1", "case2", "case3", "case4"], help="Test case")
    parser.add_argument("--headed", action="store_true", help="Run in headed mode")

    args = parser.parse_args()
    run_test(args.url, args.username, args.password, args.device, args.case, args.headed)


# --- 小函式 1：URL 正規化 , for CI test---
def normalize_url(url: str) -> str:
    url = (url or "").strip()
    return url if url.startswith(("http://", "https://")) else "http://" + url

# --- 小函式 2：鎖定規則, for CI test ---
def lockout_action(failed_count: int):
    """
    回傳 ('retry', None) 或 ('lock', 秒數)
    """
    if failed_count == 3:
        return ('lock', 60)     # 3 次 -> 鎖 1 分鐘
    if failed_count == 6:
        return ('lock', 60)     # 6 次 -> 再鎖 1 分鐘
    if failed_count == 9:
        return ('lock', 300)    # 9 次 -> 鎖 5 分鐘
    return ('retry', None)
