#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
砚 Inkstone 桌面版
原生窗口（WebView2）+ 内嵌本地服务，双击即用，不经过浏览器。
"""
import base64
import os
import socket
import subprocess
import sys
import threading
import time
import logging

import server as engine

# pythonnet 反射 WinForms 属性时会刷一长串无害报错，压掉
logging.getLogger("pywebview").setLevel(logging.CRITICAL)

try:
    import webview
except Exception:
    webview = None


class Bridge:
    """暴露给前端的原生能力。"""

    def __init__(self):
        self._win = None   # 下划线开头：避免被 js_api 序列化时递归反射 .NET 属性

    def save_markdown(self, filename, content):
        try:
            dialog = getattr(getattr(webview, "FileDialog", None), "SAVE", None)
            if dialog is None:
                dialog = webview.SAVE_DIALOG
            path = self._win.create_file_dialog(
                dialog,
                save_filename=filename or "创作.md",
                file_types=("Markdown (*.md)", "文本文件 (*.txt)", "所有文件 (*.*)"),
            )
            if not path:
                return {"ok": False, "message": "已取消"}
            if isinstance(path, (list, tuple)):
                path = path[0]
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"ok": True, "message": "已保存：" + os.path.basename(path), "path": path}
        except Exception as e:
            return {"ok": False, "message": "保存失败：%s" % e}

    def pick_skill_file(self):
        """选一个 .md / .zip，读成 base64 交给前端走导入接口。"""
        try:
            dialog = getattr(getattr(webview, "FileDialog", None), "OPEN", None)
            if dialog is None:
                dialog = webview.OPEN_DIALOG
            path = self._win.create_file_dialog(
                dialog,
                allow_multiple=False,
                file_types=("技能文件 (*.md;*.zip)", "Markdown (*.md)", "压缩包 (*.zip)"),
            )
            if not path:
                return {"ok": False, "message": "已取消"}
            if isinstance(path, (list, tuple)):
                path = path[0]
            if not os.path.exists(path):
                return {"ok": False, "message": "文件不存在"}
            if os.path.getsize(path) > 20 * 1024 * 1024:
                return {"ok": False, "message": "文件请小于 20MB"}
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            return {"ok": True, "name": os.path.basename(path), "data": data}
        except Exception as e:
            return {"ok": False, "message": "打开失败：%s" % e}

    def pick_doc_file(self):
        """选一个文档当素材，读成 base64 交给前端识别。"""
        try:
            dialog = getattr(getattr(webview, "FileDialog", None), "OPEN", None)
            if dialog is None:
                dialog = webview.OPEN_DIALOG
            path = self._win.create_file_dialog(
                dialog,
                allow_multiple=False,
                file_types=("文档 (*.txt;*.md;*.docx;*.epub;*.pdf;*.html;*.csv;*.json)",
                            "纯文本 (*.txt;*.md;*.csv;*.json)",
                            "Word 文档 (*.docx)",
                            "所有文件 (*.*)"),
            )
            if not path:
                return {"ok": False, "message": "已取消"}
            if isinstance(path, (list, tuple)):
                path = path[0]
            if not os.path.exists(path):
                return {"ok": False, "message": "文件不存在"}
            if os.path.getsize(path) > 40 * 1024 * 1024:
                return {"ok": False, "message": "文件请小于 40MB"}
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            return {"ok": True, "name": os.path.basename(path), "data": data}
        except Exception as e:
            return {"ok": False, "message": "打开失败：%s" % e}

    def open_data_dir(self):
        try:
            os.startfile(engine.DATA)
            return True
        except Exception:
            return False

    def pick_folder(self):
        """选一个文件夹（更改工作区位置用）。"""
        try:
            dialog = getattr(getattr(webview, "FileDialog", None), "FOLDER", None)
            if dialog is None:
                dialog = webview.FOLDER_DIALOG
            path = self._win.create_file_dialog(dialog)
            if not path:
                return {"ok": False, "message": "已取消"}
            if isinstance(path, (list, tuple)):
                path = path[0]
            return {"ok": True, "path": path}
        except Exception as e:
            return {"ok": False, "message": "打开失败：%s" % e}

    def restart_app(self):
        """重启自己，让新的工作区设置生效。"""
        try:
            exe = sys.executable
            args = [exe] if getattr(sys, "frozen", False) else [exe, os.path.abspath(__file__)]
            subprocess.Popen(args, close_fds=True,
                             cwd=os.path.dirname(exe) or os.getcwd())
        except Exception as e:
            return {"ok": False, "message": "重启失败：%s" % e}
        threading.Timer(0.9, lambda: os._exit(0)).start()
        return {"ok": True}


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def fatal(msg):
    """没有控制台时的兜底提示。"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "砚 Inkstone", 0x10)
    except Exception:
        print(msg)


def main():
    if webview is None:
        # 没有可用的 WebView，退回系统浏览器模式，保证还能用
        try:
            engine.main()
        except Exception as e:
            fatal("界面组件缺失，无法启动。\n\n%s" % e)
        return

    port = free_port()
    srv, port = engine.serve_in_thread(port)
    url = "http://127.0.0.1:%d" % port
    start_view = os.environ.get("INKSTONE_VIEW")
    if start_view in ("write", "book", "skills", "project"):
        url += "?view=" + start_view

    bridge = Bridge()
    try:
        window = webview.create_window(
            "砚 Inkstone · 写作智能体",
            url,
            width=1500,
            height=940,
            min_size=(980, 640),
            background_color="#FAF8F3",
            text_select=True,
            js_api=bridge,
        )
        bridge._win = window
        debug = "--debug" in sys.argv
        try:
            webview.start(gui="edgechromium", debug=debug)
        except Exception:
            webview.start(debug=debug)
    except Exception as e:
        fatal("启动失败。请确认系统已安装 Microsoft Edge WebView2 运行时。\n\n%s" % e)

    try:
        srv.shutdown()
    except Exception:
        pass


if __name__ == "__main__":
    main()
