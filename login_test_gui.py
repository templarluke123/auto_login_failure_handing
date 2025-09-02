# login_cli.py
# QA lockout tester for router/extender login pages
# Notes:
# - Comments are in English (per user's preference).
# - Handles router vs extender DOM differences, iframes, SSL warning, and auto-dumps on failure.

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


# ---------- Logging ----------
def log_result(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    Path("login_test_results/logs").mkdir(parents=True, exist_ok=True)
    with open("login_test_results/logs/login_test_log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


# ---------- Helpers: robust element finding, click, URL normalize, SSL warning ----------
def find_first(driver, candidates, timeout=10):
    """Try a list of (By, locator) candidates; return the first present element or raise."""
    last_err = None
    for by, loc in candidates:
        try:
            return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, loc)))
        except Exception as e:
            last_err = e
    raise last_err if last_err else Exception("No locator matched.")

def find_first_or_none(driver, candidates, timeout=6):
    """Return the first present element from candidates, or None if none found."""
    for by, loc in candidates:
        try:
            return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, loc)))
        except Exception:
            continue
    return None

def click_first(driver, candidates, timeout=10):
    """Try to click the first clickable candidate; fall back to JS click; return True if clicked."""
    last_err = None
    for by, loc in candidates:
        try:
            el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, loc)))
            el.click()
            return True
        except Exception as e:
            last_err = e
    # fallback: JS click on first present
    for by, loc in candidates:
        try:
            el = WebDriverWait(driver, 2).until(EC.presence_of_element_located((by, loc)))
            driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            continue
    if last_err:
        raise last_err
    return False

def bypass_https_warning_if_needed(driver):
    """Handle Chrome's SSL warning page if present."""
    try:
        adv = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.ID, "details-button")))
        adv.click()
        proceed = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.ID, "proceed-link")))
        proceed.click()
    except Exception:
        # If not on SSL warning page, nothing to do.
        pass

def normalize_url(url: str) -> str:
    """
    Prefer HTTP for mywifiext* to avoid SSL warning.
    Otherwise, keep the user's scheme or default to https.
    """
    url = (url or "").strip()
    if not url:
        return url
    low = url.lower()
    if "mywifiext" in low:
        if low.startswith("https://"):
            return "http://" + url[8:]
        if not low.startswith(("http://", "https://")):
            return "http://" + url
        return url
    return url if low.startswith(("http://", "https://")) else "https://" + url


# ---------- Switch into the context (main or an iframe) that contains our inputs ----------
def switch_to_form_context(driver, user_candidates, pass_candidates):
    """
    Try current document first; if not found, iterate all iframes/frames and switch
    into the one containing any of the form fields. Return True if found; else False.
    """
    # main doc first
    u = find_first_or_none(driver, user_candidates, timeout=2)
    p = find_first_or_none(driver, pass_candidates, timeout=2)
    if u or p:
        return True

    # try all frames
    try:
        frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
    except Exception:
        frames = []

    for fr in frames:
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(fr)
            u = find_first_or_none(driver, user_candidates, timeout=2)
            p = find_first_or_none(driver, pass_candidates, timeout=2)
            if u or p:
                return True
        except Exception:
            continue

    # not found; go back
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    return False


# ---------- Device profiles (router vs extender) ----------
DEVICE_PROFILES = {
    "router": {
        "user_candidates": [
            (By.NAME, "username"),
            (By.ID, "username"),
            (By.CSS_SELECTOR, 'input[name="username"]'),
        ],
        "pass_candidates": [
            (By.NAME, "password"),
            (By.ID, "password"),
            (By.CSS_SELECTOR, 'input[type="password"]'),
        ],
        "login_btn_candidates": [
            (By.XPATH, '//a[contains(@onclick,"checklogin")]'),
            (By.CSS_SELECTOR, "div.loginButton > div"),
            (By.ID, "loginBtn"),
            (By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]'),
        ],
    },
    "extender": {
        "user_candidates": [
            (By.NAME, "email_auth"),
            (By.ID, "userId"),
            (By.CSS_SELECTOR, "input.email"),
        ],
        "pass_candidates": [
            (By.NAME, "passwd_auth"),
            (By.ID, "password"),
            (By.CSS_SELECTOR, "input.password[type='password']"),
        ],
        "login_btn_candidates": [
            (By.ID, "loginBt"),
            (By.NAME, "login_bt"),
            (By.CSS_SELECTOR, "input.btn.primary"),
        ],
    }
}

# ---------- Generic "done" indicators for success or lockout text ----------
DONE_INDICATORS = [
    (By.XPATH, '//*[contains(text(),"Login successful") or contains(text(),"登入成功")]'),
    (By.XPATH, '//*[contains(translate(text(),"LOCKED","locked"),"locked") '
               'or contains(text(),"鎖定") or contains(text(),"too many")]'),
    (By.CSS_SELECTOR, ".error, .warning, .message, #errorMsg, .alert"),
]


# ---------- Core test runner ----------
def run_test(url, username, password, device_type, case, headed=False):
    url = normalize_url(url)

    driver = None
    try:
        print("啟動 ChromeDriver...")
        options = webdriver.ChromeOptions()
        if not headed:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-features=AutofillEnableByDefault,Translate")
        options.add_argument("--no-default-browser-check")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 10)

        max_attempts = {"case1": 3, "case2": 6, "case3": 9, "case4": 12}.get(case, 3)
        lock_9 = lock_12 = False

        profile = DEVICE_PROFILES.get(device_type.lower(), DEVICE_PROFILES["router"])

        for i in range(max_attempts):
            attempt = i + 1
            print(f"{case} - 第 {attempt} 次登入嘗試")

            driver.get(url)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            bypass_https_warning_if_needed(driver)
            time.sleep(0.6)

            # Ensure we are in the context (main or a frame) that contains the form
            has_form_ctx = switch_to_form_context(driver, profile["user_candidates"], profile["pass_candidates"])
            if not has_form_ctx:
                raise Exception("找不到登入表單欄位（主頁或任何 iframe 內皆無）")

            try:
                # --- Fill credentials (username optional for extenders) ---
                u = find_first_or_none(driver, profile["user_candidates"], timeout=6)
                p = find_first_or_none(driver, profile["pass_candidates"], timeout=6)

                if device_type.lower() == "extender":
                    # Some extenders only require password; username may exist and be type=email.
                    if u:
                        try:
                            # If type=email and username lacks '@', switch to text to bypass HTML5 email validity.
                            if (u.get_attribute("type") or "").lower() == "email" and ("@" not in (username or "")):
                                driver.execute_script("arguments[0].setAttribute('type','text')", u)
                        except Exception:
                            pass
                        u.click(); u.clear(); u.send_keys(username)

                    if p is None:
                        raise Exception("Extender 模式找不到密碼欄位")
                    p.click(); p.clear(); p.send_keys(password)
                else:
                    # Router expects both fields present.
                    if not (u and p):
                        raise Exception("Router 模式找不到 username/password 欄位")
                    u.click(); u.clear(); u.send_keys(username)
                    p.click(); p.clear(); p.send_keys(password)

                log_result(
                    f"[{case}] 第 {attempt} 次 - 填入帳密: "
                    f"user_field_type={(u.get_attribute('type') if u else 'N/A')} "
                    f"user_value={(username if u else '(auto or none)')} "
                    f"pass_len={len(password or '')}"
                )

                # Clear required attributes if any hidden required fields block submit
                try:
                    driver.execute_script("""
                      (function(){
                        var inputs = document.querySelectorAll('input[required]');
                        inputs.forEach(function(el){ el.required = false; });
                      })();
                    """)
                except Exception:
                    pass

                # --- Click login ---
                clicked = click_first(driver, profile["login_btn_candidates"], timeout=6)
                if not clicked:
                    # Fallback to common JS login handlers
                    for js in (
                        "if (typeof checklogin==='function') { return checklogin(document.forms[0]); }",
                        "if (typeof login==='function') { return login(); }",
                        "var f=document.querySelector('form'); if (f) f.submit();",
                    ):
                        try:
                            driver.execute_script(js)
                            clicked = True
                            break
                        except Exception:
                            continue

                time.sleep(3.5)

                # --- Detect locked/success states ---
                page = (driver.page_source or "").lower()
                current_url = (driver.current_url or "").lower()
                locked = (
                    "unauth" in current_url
                    or "locked" in page
                    or "鎖定" in page
                    or "too many" in page
                    or "try again" in page
                )

                if locked:
                    if case == "case1" and attempt == 3:
                        log_result(f"[Case 1] 第 {attempt} 次鎖定成功")
                        print("✅ Case1 成功")
                        break

                    elif case == "case2" and attempt == 6:
                        if ("1 minute" in page) or ("1 分鐘" in page) or ("60 seconds" in page):
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
                            if ("5 minute" in page) or ("5 分鐘" in page) or ("300 seconds" in page):
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
                            if ("5 minute" in page) or ("5 分鐘" in page) or ("300 seconds" in page):
                                lock_9 = True
                                log_result(f"[Case 4] 第 9 次鎖定成功（5分鐘）")
                                print("📌 Case4：第 9 次鎖定成功，等待 5 分鐘")
                                time.sleep(305)
                            else:
                                log_result(f"[Case 4] 第 9 次鎖定但無 5 分鐘提示")
                                print("⚠️ Case4：第 9 次未偵測到 5 分鐘文字")
                        elif attempt == 12:
                            if ("5 minute" in page) or ("5 分鐘" in page) or ("300 seconds" in page):
                                lock_12 = True
                                log_result(f"[Case 4] 第 12 次鎖定成功（5分鐘）")
                                print("📌 Case4：第 12 次鎖定成功")
                            else:
                                log_result(f"[Case 4] 第 12 次鎖定但無 5 分鐘提示")
                                print("⚠️ Case4：第 12 次未偵測到 5 分鐘文字")

                else:
                    log_result(f"[{case}] 第 {attempt} 次登入失敗但未鎖定")

            except Exception as inner_e:
                # Log and dump diagnostics for this attempt, then re-raise to abort the run.
                log_result(f"[{case}] 第 {attempt} 次登入異常: {inner_e}")

                try:
                    dump_dir = Path("login_test_results/dumps")
                    dump_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    driver.save_screenshot(str(dump_dir / f"{case}_{device_type}_attempt{attempt}_{ts}.png"))
                    with open(dump_dir / f"{case}_{device_type}_attempt{attempt}_{ts}.html", "w", encoding="utf-8") as fh:
                        fh.write(driver.page_source or "")
                except Exception:
                    pass

                raise

            finally:
                # Always return to default content for next attempt
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass

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


# ---------- CLI ----------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Login test with router/extender DOM fallbacks & lockout cases")
    parser.add_argument("--url", required=True, help="Login URL (router IP or mywifiext.local)")
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument("--password", required=True, help="Wrong password to trigger lockout")
    parser.add_argument("--device", required=True, choices=["router", "extender"], help="Device type")
    parser.add_argument("--case", required=True, choices=["case1", "case2", "case3", "case4"], help="Test case")
    parser.add_argument("--headed", action="store_true", help="Run in headed mode")
    args = parser.parse_args()

    run_test(args.url, args.username, args.password, args.device, args.case, args.headed)


# ---------- (Optional) Tiny helper used in CI/tests ----------
def lockout_action(failed_count: int):
    """
    Return ('retry', None) or ('lock', seconds) according to your spec:
    - 3 fails -> lock 1 min
    - 6 fails -> lock 1 min
    - 9 fails -> lock 5 min
    """
    if failed_count == 3:
        return ('lock', 60)
    if failed_count == 6:
        return ('lock', 60)
    if failed_count == 9:
        return ('lock', 300)
    return ('retry', None)
