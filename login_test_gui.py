import tkinter as tk
from tkinter import messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import threading
import time
import traceback
from datetime import datetime

# Log 測試結果
def log_result(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("login_test_log.txt", "a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")

# 主測試函式
def run_test(case):
    url = url_entry.get().strip()
    username = username_entry.get()
    password = password_entry.get()
    device_type = device_var.get()

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    if not url or not username or not password:
        messagebox.showwarning("輸入錯誤", "請填寫所有欄位")
        return

    driver = None

    try:
        print("啟動 ChromeDriver...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
        wait = WebDriverWait(driver, 10)
        driver.get(url)

        max_attempts = {"case1": 3, "case2": 6, "case3": 9}.get(case, 3)

        for i in range(max_attempts):
            attempt_num = i + 1
            print(f"{case} - 第 {attempt_num} 次登入嘗試")

            try:
                # 根據設備類型選擇欄位
                if device_type == "router":
                    username_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
                    password_input = driver.find_element(By.NAME, "password")
                    login_button = driver.find_element(By.XPATH, '//a[contains(@onclick, "checklogin")]')
                elif device_type == "extender":
                    username_input = wait.until(EC.presence_of_element_located((By.ID, "userId")))
                    password_input = driver.find_element(By.ID, "password")
                    login_button = driver.find_element(By.ID, "loginBt")
                else:
                    raise Exception("未知設備類型")

                username_input.clear()
                password_input.clear()
                username_input.send_keys(username)
                password_input.send_keys(password)
                login_button.click()

                time.sleep(5)

                if "unauth" in driver.current_url or "帳號已鎖定" in driver.page_source:
                    if case == "case1" and attempt_num == 3:
                        log_result(f"[Case 1] Attempt {attempt_num}: Lockout page detected.")
                        messagebox.showinfo("測試結果", "✅ Case 1 測試成功：第3次登入後導向鎖定頁面")
                        break
                    elif case == "case2":
                        if attempt_num == 3:
                            log_result(f"[Case 2] Attempt {attempt_num}: Lockout detected, retrying...")
                            driver.get(url)
                            continue
                        elif attempt_num == 6:
                            if "try again in 1 minute" in driver.page_source.lower():
                                log_result(f"[Case 2] Attempt {attempt_num}: 1-minute lockout detected.")
                                messagebox.showinfo("測試結果", "✅ Case 2 測試成功：帳號鎖定，頁面顯示『try again in 1 minute』")
                            else:
                                log_result(f"[Case 2] Attempt {attempt_num}: Lockout found but no 1-minute text.")
                                messagebox.showwarning("測試結果", "⚠️ Case 2：鎖定未顯示 1 分鐘訊息")
                            break
                    elif case == "case3":
                        if attempt_num in [3, 6]:
                            log_result(f"[Case 3] Attempt {attempt_num}: Lockout, reloading.")
                            if attempt_num == 6:
                                log_result(f"[Case 3] Waiting 65 seconds before next attempt.")
                                time.sleep(65)
                            driver.get(url)
                            continue
                        elif attempt_num == 9:
                            if "5 minutes" in driver.page_source.lower() or "try again in 5 minute" in driver.page_source:
                                log_result(f"[Case 3] Attempt {attempt_num}: 5-minute lockout detected.")
                                messagebox.showinfo("測試結果", "✅ Case 3 測試成功：帳號鎖定 5 分鐘")
                            else:
                                log_result(f"[Case 3] Attempt {attempt_num}: Lockout but no 5-minute text.")
                                messagebox.showwarning("測試結果", "⚠️ Case 3：鎖定未顯示 5 分鐘訊息")
                            break
                        else:
                            log_result(f"[Case 3] Attempt {attempt_num}: Lockout detected.")
                else:
                    log_result(f"[{case}] Attempt {attempt_num}: Login failed, no lockout.")

            except Exception as inner_e:
                log_result(f"[{case}] Attempt {attempt_num}: Exception - {inner_e}")
                raise inner_e

    except Exception as e:
        error_details = traceback.format_exc()
        messagebox.showerror("錯誤", f"執行過程中發生錯誤：\n{error_details}")
        log_result(f"[{case}] Exception during test: {error_details}")
    finally:
        if driver:
            driver.quit()
            print("已關閉瀏覽器")

# 建立 GUI
root = tk.Tk()
root.title("登入鎖定測試工具")

tk.Label(root, text="登入網址：").grid(row=0, column=0, sticky="e")
tk.Label(root, text="帳號：").grid(row=1, column=0, sticky="e")
tk.Label(root, text="密碼：").grid(row=2, column=0, sticky="e")
tk.Label(root, text="設備類型：").grid(row=3, column=0, sticky="e")

url_entry = tk.Entry(root, width=40)
username_entry = tk.Entry(root, width=40)
password_entry = tk.Entry(root, width=40, show="*")
device_var = tk.StringVar(value="router")
device_menu = tk.OptionMenu(root, device_var, "router", "extender")

url_entry.grid(row=0, column=1, padx=5, pady=5)
username_entry.grid(row=1, column=1, padx=5, pady=5)
password_entry.grid(row=2, column=1, padx=5, pady=5)
device_menu.grid(row=3, column=1, padx=5, pady=5)

tk.Button(root, text="Case 1：3次錯誤導向鎖定頁面", command=lambda: threading.Thread(target=run_test, args=("case1",)).start()).grid(row=4, column=0, columnspan=2, pady=5)
tk.Button(root, text="Case 2：6次錯誤鎖定1分鐘", command=lambda: threading.Thread(target=run_test, args=("case2",)).start()).grid(row=5, column=0, columnspan=2, pady=5)
tk.Button(root, text="Case 3：9次錯誤鎖定5分鐘", command=lambda: threading.Thread(target=run_test, args=("case3",)).start()).grid(row=6, column=0, columnspan=2, pady=5)

root.mainloop()

