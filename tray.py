# -*- coding: utf-8 -*-
"""
Graph Viewer - 系统托盘启停控制
双击托盘图标打开浏览器
右键菜单：打开图谱 / 退出
退出托盘即自动停止服务器
"""

import subprocess
import threading
import webbrowser
import time
import os

import pystray
from PIL import Image, ImageDraw

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_URL = "http://127.0.0.1:7892"
SERVER_SCRIPT = os.path.join(BASE_DIR, "server.py")
SERVER_PORT = 7892

server_process = None


def create_icon_image(status="on"):
    """生成托盘图标：深色背景 + 蓝色圆环 + 中心点"""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 外圆背景
    draw.ellipse([2, 2, size - 2, size - 2], fill=(26, 29, 39, 220))

    # 圆环
    ring_color = (59, 130, 246, 255) if status == "on" else (100, 100, 100, 255)
    draw.ellipse([4, 4, size - 4, size - 4], outline=ring_color, width=4)

    # 中心点
    cx, cy = size // 2, size // 2
    r = 10
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ring_color)

    return img


def kill_port(port):
    """杀掉占用指定端口的进程"""
    try:
        result = subprocess.check_output(
            f"netstat -nao | findstr :{port}",
            shell=True, stderr=subprocess.DEVNULL
        ).decode(errors="ignore")
        for line in result.strip().splitlines():
            if "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid and pid != "0":
                    subprocess.call(
                        ["taskkill", "/F", "/T", "/PID", pid],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
    except Exception:
        pass


def start_server():
    """启动服务器子进程"""
    global server_process
    if server_process and server_process.poll() is None:
        return

    # 先清理端口
    kill_port(SERVER_PORT)
    time.sleep(1)

    server_process = subprocess.Popen(
        ["uv", "run", "python", SERVER_SCRIPT],
        cwd=BASE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    )

    # 等待服务器就绪（最多 10 秒）
    for _ in range(20):
        time.sleep(0.5)
        try:
            import urllib.request
            urllib.request.urlopen(SERVER_URL + "/api/stats", timeout=1)
            break
        except Exception:
            pass


def stop_server():
    """停止服务器（杀进程树 + 端口兜底）"""
    global server_process
    if server_process and server_process.poll() is None:
        try:
            subprocess.call(
                ["taskkill", "/F", "/T", "/PID", str(server_process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            server_process.wait(timeout=3)
        except Exception:
            pass
    server_process = None
    kill_port(SERVER_PORT)


def open_browser(icon=None, item=None):
    webbrowser.open(SERVER_URL)


def on_quit(icon, item):
    icon.title = "Graph Viewer - 停止中..."
    stop_server()
    icon.stop()


def setup(icon):
    icon.visible = True
    threading.Thread(target=_boot, args=(icon,), daemon=True).start()


def _boot(icon):
    icon.title = "Graph Viewer - 启动中..."
    icon.icon = create_icon_image(status="off")
    start_server()
    icon.title = "Graph Viewer - 运行中"
    icon.icon = create_icon_image(status="on")
    webbrowser.open(SERVER_URL)


def main():
    icon_img = create_icon_image(status="off")

    menu = pystray.Menu(
        pystray.MenuItem("打开图谱", open_browser, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", on_quit),
    )

    icon = pystray.Icon(
        name="graph-viewer",
        icon=icon_img,
        title="Graph Viewer - 启动中...",
        menu=menu,
    )

    icon.run(setup=setup)


if __name__ == "__main__":
    main()
