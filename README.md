# 🔐 Login Lockout Tester

自動化測試網站帳號登入錯誤後的鎖定機制。支援 GUI 操作，模擬多次輸入錯誤帳號密碼，驗證網站是否依預期出現鎖定提示或限制登入。

---

## 🧰 功能特色

- ✅ 支援 3 種測試情境（輸入錯密碼 3、6、9 次）
- ✅ 自動判斷是否進入鎖定頁面或顯示特定鎖定訊息
- ✅ 使用 `tkinter` GUI 輕鬆輸入帳密與網址
- ✅ 產出詳細 log (`login_test_log.txt`) 供後續分析
- ✅ 多執行緒處理，GUI 不會卡住


---

## 📦 安裝方式

### Python 版本需求：
- Python 3.8+
- 已安裝 Chrome 瀏覽器

### 套件安裝：
請先建立虛擬環境（可選），然後安裝依賴：

```bash
pip install -r requirements.txt

