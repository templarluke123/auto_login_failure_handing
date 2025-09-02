20250808
.Add headed/headless mode to check the auto test in real time.
.Add case4 (verify login can be blocked 5 mins at 12 times login, same as 9 times. )

20250806
Initial cli-branch and change code to cli mode.

20250902
## 更新紀錄

### 2025-09-02
- **Extender Profile 修正**
  - 新增對 `NETGEAR Extender EAX16` 登入頁的支援。
  - 調整欄位定位器：
    - 帳號欄位：`name="email_auth"`, `id="userId"`, `.email`
    - 密碼欄位：`name="passwd_auth"`, `id="password"`, `.password[type=password]`
    - 登入按鈕：`id="loginBt"`, `name="login_bt"`, `.btn.primary`
- **自動 Dump 功能**
  - 登入異常時自動輸出：
    - `login_test_results/dumps/*.png` → 當下畫面截圖
    - `login_test_results/dumps/*.html` → 頁面 HTML
  - 方便除錯與新增 profile。

> ✅ 測試結果：  
> `--device extender` 在 `mywifiext.local` 驗證通過，Case1～Case4 均可執行。
