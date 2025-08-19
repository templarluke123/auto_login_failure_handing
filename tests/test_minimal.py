# tests/test_minimal.py
import sys, os
# 把「專案根目錄」加到匯入路徑，確保能 import 根目錄的 login_test_gui.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from login_test_gui import normalize_url, lockout_action

def test_normalize_url():
    assert normalize_url("192.168.1.1") == "http://192.168.1.1"
    assert normalize_url("https://routerlogin.net") == "https://routerlogin.net"
    assert normalize_url("  http://x ") == "http://x"

def test_lockout_action():
    assert lockout_action(2)[0] == 'retry'
    assert lockout_action(3) == ('lock', 60)
    assert lockout_action(6) == ('lock', 60)
    assert lockout_action(9) == ('lock', 300)
