#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动打包好的 exe 并截图，验证能否正常启动。
用法：python tools/shot_exe.py dist/Inkstone.exe out.png [等待秒数]
"""
import ctypes
import os
import subprocess
import sys
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

from PIL import ImageGrab  # noqa: E402

EXE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "dist/Inkstone.exe")
OUT = sys.argv[2] if len(sys.argv) > 2 else "exe.png"
WAIT = float(sys.argv[3]) if len(sys.argv) > 3 else 9.0

user32 = ctypes.windll.user32


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


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


def main():
    print("启动", EXE)
    p = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    hwnd = None
    t0 = time.time()
    while time.time() - t0 < WAIT:
        hwnd = find_win()
        if hwnd:
            break
        time.sleep(0.4)
    if not hwnd:
        print("没找到窗口，exe 可能启动失败")
        p.terminate()
        return 1
    print("窗口已出现，等待渲染…")
    time.sleep(4.0)
    user32.SetWindowPos(hwnd, -1, 0, 0, 2100, 1290, 0x0040)
    user32.SetForegroundWindow(hwnd)
    time.sleep(1.4)
    r = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=True)
    img.save(OUT)
    print("saved", OUT, img.size)
    try:
        p.terminate()
        p.wait(timeout=6)
    except Exception:
        subprocess.run(["taskkill", "/F", "/IM", os.path.basename(EXE)], capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
