#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动真实窗口并截图，用于界面自查。
用法：python tools/shot.py out.png "?view=book" [等待秒数]
"""
import ctypes
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import server as engine          # noqa: E402
import webview                   # noqa: E402
from PIL import ImageGrab        # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "shot.png"
QUERY = sys.argv[2] if len(sys.argv) > 2 else ""
WAIT = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
JS = sys.argv[4] if len(sys.argv) > 4 else ""

user32 = ctypes.windll.user32
holder = {}


def find_win():
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _l):
        n = user32.GetWindowTextLengthW(hwnd)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if "Inkstone" in buf.value:
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def worker():
    time.sleep(WAIT)
    try:
        hwnd = None
        for _ in range(40):
            hwnd = find_win()
            if hwnd:
                break
            time.sleep(0.25)
        if not hwnd:
            print("没找到窗口")
            holder["win"].destroy()
            return
        if JS:
            try:
                r = holder["win"].evaluate_js(JS)
                if r is not None:
                    print("js =>", r)
                time.sleep(2.8)
            except Exception as e:
                print("js 执行失败:", e)
        user32.ShowWindow(hwnd, 9)          # SW_RESTORE
        user32.SetWindowPos(hwnd, -1, 0, 0, 2100, 1290, 0x0040)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        time.sleep(1.2)
        r = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        box = (r.left, r.top, r.right, r.bottom)
        img = ImageGrab.grab(bbox=box, all_screens=True)
        img.save(OUT)
        print("saved", OUT, img.size, "box=", box)
    except Exception as e:
        print("截图失败:", e)
    finally:
        try:
            holder["win"].destroy()
        except Exception:
            pass


def main():
    port = 8799
    srv, port = engine.serve_in_thread(port)
    url = "http://127.0.0.1:%d/%s" % (port, QUERY)
    print("url =", url)
    holder["win"] = webview.create_window(
        "砚 Inkstone · 写作智能体", url,
        width=1400, height=860, background_color="#FAF8F3",
        text_select=True,
    )
    threading.Thread(target=worker, daemon=True).start()
    try:
        webview.start(gui="edgechromium")
    except Exception:
        webview.start()
    try:
        srv.shutdown()
    except Exception:
        pass


if __name__ == "__main__":
    main()
