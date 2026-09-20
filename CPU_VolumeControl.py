import sys
import time
import platform
import psutil
import os
import threading
import tkinter as tk
from tkinter import ttk
import pystray
from PIL import Image, ImageDraw
import locale

# 根据操作系统导入相应的音量控制库
system_name = platform.system()

if system_name == "Windows":
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        volume_interface = devices.EndpointVolume
    except Exception as e:
        print(f"Windows Volume Init Failed: {e}")
        exit()

# --- 多语言文本字典 ---
TRANSLATIONS = {
    'zh': {
        'title': 'CPU 联动音量调节器',
        'limit_set': '音量上限设置 (%)：',
        'current_limit': '当前上限: {}%',
        'cpu_usage': '当前 CPU 占用: -- %',
        'actual_vol': '当前实际音量: -- %',
        'btn_start': '开始监控',
        'btn_stop': '停止监控',
        'close_title': '确认关闭',
        'close_prompt': '请问是要退出程序，还是最小化到系统托盘？',
        'minimize_tray': '最小化到托盘',
        'exit_direct': '直接退出',
        'no_more_prompt': '以后不再提醒，按此选择执行',
        'tray_open': '打开主界面',
        'tray_start': '开始监控',
        'tray_stop': '停止监控',
        'tray_limit': '快捷音量上限',
        'tray_lang': '语言设置',
        'tray_exit': '退出程序',
        'lang_zh': '中文',
        'lang_en': 'English'
    },
    'en': {
        'title': 'CPU Volume Adjuster',
        'limit_set': 'Max Volume Limit (%):',
        'current_limit': 'Current Limit: {}%',
        'cpu_usage': 'CPU Usage: -- %',
        'actual_vol': 'Actual Volume: -- %',
        'btn_start': 'Start Monitor',
        'btn_stop': 'Stop Monitor',
        'close_title': 'Confirm Close',
        'close_prompt': 'Do you want to exit or minimize to tray?',
        'minimize_tray': 'Minimize to Tray',
        'exit_direct': 'Exit',
        'no_more_prompt': "Don't ask again",
        'tray_open': 'Open Window',
        'tray_start': 'Start Monitor',
        'tray_stop': 'Stop Monitor',
        'tray_limit': 'Quick Max Volume',
        'tray_lang': 'Language',
        'tray_exit': 'Exit',
        'lang_zh': '中文',
        'lang_en': 'English'
    }
}

def set_system_volume(volume_scalar):
    """设置系统音量"""
    if system_name == "Windows":
        volume_interface.SetMasterVolumeLevelScalar(volume_scalar, None)
    elif system_name == "Darwin":
        os.system(f"osascript -e 'set volume output volume {int(volume_scalar * 100)}'")
    elif system_name == "Linux":
        os.system(f"amixer set Master {int(volume_scalar * 100)}% > /dev/null 2>&1")


class CloseConfirmDialog:
    """自定义关闭提示框，支持传入语言字典"""
    def __init__(self, parent, lang_code):
        self.lang = lang_code
        self.t = TRANSLATIONS[self.lang]

        self.top = tk.Toplevel(parent)
        self.top.title(self.t['close_title'])
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()
        
        self.result = None
        self.no_more_prompt = False

        tk.Label(self.top, text=self.t['close_prompt'], font=("微软雅黑", 10)).pack(pady=15)

        btn_frame = tk.Frame(self.top)
        btn_frame.pack(pady=10)

        # 修正点：去掉 ipady，改用 pady=5 增加按钮内边距，让按钮文字完整显示且居中
        tk.Button(btn_frame, text=self.t['minimize_tray'], bg="#2196F3", fg="white",
                  font=("微软雅黑", 10), padx=15, pady=5, command=self.do_minimize).pack(side="left", padx=10)
        tk.Button(btn_frame, text=self.t['exit_direct'], bg="#f44336", fg="white",
                  font=("微软雅黑", 10), padx=15, pady=5, command=self.do_exit).pack(side="left", padx=10)

        self.var_no_more = tk.BooleanVar()
        tk.Checkbutton(self.top, text=self.t['no_more_prompt'], variable=self.var_no_more).pack(pady=10)

        # 弹窗尺寸
        self.center_on_parent(parent, width=360, height=200)

    def center_on_parent(self, parent, width, height):
        parent.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()

        x = parent_x + (parent_w - width) // 2
        y = parent_y + (parent_h - height) // 2
        self.top.geometry(f"{width}x{height}+{x}+{y}")

    def do_minimize(self):
        self.result = "minimize"
        self.no_more_prompt = self.var_no_more.get()
        self.top.destroy()

    def do_exit(self):
        self.result = "exit"
        self.no_more_prompt = self.var_no_more.get()
        self.top.destroy()


class CpuVolumeApp:
    def __init__(self, root):
        self.root = root
        self.root.resizable(False, False)
        
        self.is_running = False
        self.worker_thread = None
        self.max_limit = 100.0
        self.show_close_dialog = True
        self.default_close_action = "minimize"

        try:
            sys_lang, _ = locale.getdefaultlocale()
            self.current_lang = 'zh' if sys_lang and sys_lang.lower().startswith('zh') else 'en'
        except Exception:
            self.current_lang = 'en'
            
        self.t = TRANSLATIONS[self.current_lang]

        self.create_widgets()
        self.setup_tray()
        self.center_window(width=400, height=320)

    def get_text(self, key, *args):
        text = TRANSLATIONS[self.current_lang][key]
        return text.format(*args) if args else text

    def center_window(self, width, height):
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def create_widgets(self):
        self.root.title(self.get_text('title'))

        # --- 新增：设置主窗口左上角的图标 ---
        icon_path = self.resource_path("icon.ico")
        if os.path.exists(icon_path):
            try:
                # 如果是 Windows 系统，直接用 iconbitmap 最稳定
                self.root.iconbitmap(icon_path)
            except Exception as e:
                print(f"设置主窗口图标失败: {e}")
        # ----------------------------------

        # 下面的顶部语言选择器...
        top_frame = tk.Frame(self.root)
        # ...（其余代码保持不变）

        # 顶部语言选择器
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=15, pady=(10, 0))
        self.lang_combo = ttk.Combobox(top_frame, values=['中文', 'English'], state='readonly', width=8)
        self.lang_combo.set('中文' if self.current_lang == 'zh' else 'English')
        self.lang_combo.bind("<<ComboboxSelected>>", self.on_lang_combo_change)
        self.lang_combo.pack(side="right")

        # 音量上限标签
        self.label_limit_set = tk.Label(self.root, text=self.get_text('limit_set'), font=("微软雅黑", 11))
        self.label_limit_set.pack(pady=(15, 5))
        
        self.slider_var = tk.DoubleVar(value=self.max_limit)
        self.slider = ttk.Scale(self.root, from_=0, to=100, variable=self.slider_var, 
                                orient="horizontal", command=self.on_slider_move)
        self.slider.pack(fill="x", padx=60)
        
        self.slider_label = tk.Label(self.root, text=self.get_text('current_limit', int(self.max_limit)), font=("微软雅黑", 10, "bold"))
        self.slider_label.pack(pady=(5, 15))

        # 状态显示区
        self.status_frame = tk.Frame(self.root)
        self.status_frame.pack(pady=10)
        
        self.cpu_label = tk.Label(self.status_frame, text=self.get_text('cpu_usage'), font=("微软雅黑", 12))
        self.cpu_label.pack()
        
        self.vol_label = tk.Label(self.status_frame, text=self.get_text('actual_vol'), font=("微软雅黑", 12, "bold"), fg="blue")
        self.vol_label.pack(pady=(5, 0))

        # 按钮
        self.btn_toggle = tk.Button(self.root, text=self.get_text('btn_start'), font=("微软雅黑", 12), 
                                    bg="#4CAF50", fg="white", width=15, command=self.toggle_monitoring)
        self.btn_toggle.pack(pady=20)

    def on_lang_combo_change(self, event):
        selected = self.lang_combo.get()
        new_lang = 'zh' if selected == '中文' else 'en'
        self.set_language(new_lang)

    def set_language(self, lang):
        if self.current_lang == lang:
            return
        
        self.current_lang = lang
        self.t = TRANSLATIONS[lang]
        
        def update_main_ui():
            self.root.title(self.get_text('title'))
            self.label_limit_set.config(text=self.get_text('limit_set'))
            self.slider_label.config(text=self.get_text('current_limit', int(self.max_limit)))
            self.cpu_label.config(text=self.get_text('cpu_usage') if not self.is_running else self.cpu_label.cget("text"))
            self.vol_label.config(text=self.get_text('actual_vol') if not self.is_running else self.vol_label.cget("text"))
            self.update_toggle_button()
            self.lang_combo.set('中文' if lang == 'zh' else 'English')
        
        self.root.after(0, update_main_ui)
        self.rebuild_tray_menu()

    def rebuild_tray_menu(self):
        menu = pystray.Menu(
            pystray.MenuItem(self.get_text('tray_open'), self.show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.get_text('tray_start'), self.start_monitoring, enabled=lambda item: not self.is_running),
            pystray.MenuItem(self.get_text('tray_stop'), self.stop_monitoring, enabled=lambda item: self.is_running),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.get_text('tray_limit'), pystray.Menu(
                pystray.MenuItem('30%', lambda: self.set_limit_from_tray(30)),
                pystray.MenuItem('50%', lambda: self.set_limit_from_tray(50)),
                pystray.MenuItem('80%', lambda: self.set_limit_from_tray(80)),
                pystray.MenuItem('100%', lambda: self.set_limit_from_tray(100)),
            )),
            pystray.MenuItem(self.get_text('tray_lang'), pystray.Menu(
                pystray.MenuItem(self.get_text('lang_zh'), lambda: self.set_language('zh'), checked=lambda item: self.current_lang == 'zh', radio=True),
                pystray.MenuItem(self.get_text('lang_en'), lambda: self.set_language('en'), checked=lambda item: self.current_lang == 'en', radio=True),
            )),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.get_text('tray_exit'), self.quit_app)
        )
        if hasattr(self, 'tray_icon'):
            self.tray_icon.menu = menu
            self.tray_icon.update_menu()

    def setup_tray(self):
        self.icon_image = self.create_tray_icon()
        self.tray_icon = pystray.Icon("CpuVolume", self.icon_image, self.get_text('title'))
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        self.rebuild_tray_menu()

    def resource_path(self, relative_path):
        """获取打包后资源的绝对路径（用于单文件 exe）"""
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def create_tray_icon(self):
        """优先加载 icon.ico，如果没有则回退到默认图标"""
        icon_path = self.resource_path("icon.ico")
        if os.path.exists(icon_path):
            try:
                return Image.open(icon_path)
            except Exception as e:
                print(f"托盘图标加载失败: {e}")
        
        # 如果找不到 icon.ico，就画一个默认的蓝色圆圈（备用）
        image = Image.new('RGB', (64, 64), color=(255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.ellipse((10, 10, 54, 54), fill=(0, 122, 204))
        return image

    def set_limit_from_tray(self, val):
        def update():
            self.max_limit = float(val)
            self.slider_var.set(self.max_limit)
            self.slider_label.config(text=self.get_text('current_limit', int(self.max_limit)))
        self.root.after(0, update)

    def show_window(self, icon=None, item=None):
        def restore():
            self.root.deiconify()
            self.root.state('normal')
            self.root.focus_force()
        self.root.after(0, restore)

    def on_slider_move(self, val):
        self.max_limit = float(val)
        self.slider_label.config(text=self.get_text('current_limit', int(self.max_limit)))

    def start_monitoring(self, icon=None, item=None):
        if not self.is_running:
            self.is_running = True
            self.root.after(0, self.update_toggle_button)
            self.worker_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.worker_thread.start()
            self.tray_icon.update_menu()

    def stop_monitoring(self, icon=None, item=None):
        if self.is_running:
            self.is_running = False
            self.root.after(0, self.update_toggle_button)
            self.root.after(0, self.reset_ui_labels)
            self.tray_icon.update_menu()

    def toggle_monitoring(self):
        if not self.is_running:
            self.start_monitoring()
        else:
            self.stop_monitoring()

    def update_toggle_button(self):
        if self.is_running:
            self.btn_toggle.config(text=self.get_text('btn_stop'), bg="#f44336")
        else:
            self.btn_toggle.config(text=self.get_text('btn_start'), bg="#4CAF50")

    def reset_ui_labels(self):
        self.cpu_label.config(text=self.get_text('cpu_usage'))
        self.vol_label.config(text=self.get_text('actual_vol'))

    def monitor_loop(self):
        psutil.cpu_percent(interval=None)
        while self.is_running:
            cpu_usage = psutil.cpu_percent(interval=1)
            target_volume_scalar = (cpu_usage / 100.0) * (self.max_limit / 100.0)
            target_volume_scalar = max(0.0, min(1.0, target_volume_scalar))
            
            try:
                set_system_volume(target_volume_scalar)
                self.root.after(0, self.update_ui, cpu_usage, target_volume_scalar * 100)
            except Exception as e:
                self.root.after(0, lambda: self.cpu_label.config(text=f"Error: {e}"))

    def update_ui(self, cpu_usage, actual_volume):
        if self.is_running:
            cpu_str = TRANSLATIONS[self.current_lang]['cpu_usage'].replace('--', f"{cpu_usage:.1f}")
            vol_str = TRANSLATIONS[self.current_lang]['actual_vol'].replace('--', f"{actual_volume:.1f}")
            self.cpu_label.config(text=cpu_str)
            self.vol_label.config(text=vol_str)

    def on_closing(self):
        if self.show_close_dialog:
            dialog = CloseConfirmDialog(self.root, self.current_lang)
            self.root.wait_window(dialog.top)
            
            if dialog.result == "exit":
                self.quit_app()
            elif dialog.result == "minimize":
                self.minimize_to_tray()
            
            if dialog.no_more_prompt:
                self.show_close_dialog = False
                self.default_close_action = dialog.result
        else:
            if self.default_close_action == "exit":
                self.quit_app()
            else:
                self.minimize_to_tray()

    def minimize_to_tray(self):
        self.root.withdraw()

    def quit_app(self, icon=None, item=None):
        self.is_running = False
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.root.quit()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = CpuVolumeApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()