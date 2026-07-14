"""
PyLauncher — a fully customizable, minimalistic Android home-screen launcher
written in Python (Kivy + pyjnius).

Everything visual (colors, columns, icon size, labels, sort order, clock,
which apps show) is controlled by config.json, editable live from the
in-app Settings screen — no rebuild required for those changes.
"""

import json
import os
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.switch import Switch
from kivy.uix.slider import Slider
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp

ANDROID = True
try:
    from jnius import autoclass, cast
except Exception:
    ANDROID = False

DEFAULT_CONFIG = {
    "columns": 4,
    "icon_size": 64,
    "background_color": "#000000",
    "text_color": "#FFFFFF",
    "accent_color": "#7C5CFF",
    "show_labels": True,
    "show_clock": True,
    "sort_by": "name",
    "hidden_apps": []
}


def hex_to_rgba(h, a=1.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return r, g, b, a


def config_path():
    app = App.get_running_app()
    base = app.user_data_dir if app else "."
    return os.path.join(base, "config.json")


def load_config():
    path = config_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(data)
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)


def get_installed_apps():
    """Return [{'label':..., 'package':..., 'class':...}] of launchable apps."""
    if not ANDROID:
        return [
            {"label": f"Demo App {i}", "package": f"com.demo.app{i}", "class": ""}
            for i in range(1, 13)
        ]
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    activity = PythonActivity.mActivity
    pm = activity.getPackageManager()
    intent = Intent(Intent.ACTION_MAIN, None)
    intent.addCategory(Intent.CATEGORY_LAUNCHER)
    resolve_infos = pm.queryIntentActivities(intent, 0)
    apps = []
    if resolve_infos is None:
        return apps
    for i in range(resolve_infos.size()):
        ri = resolve_infos.get(i)
        try:
            label = ri.loadLabel(pm).toString()
        except Exception:
            label = ri.activityInfo.packageName
        apps.append({
            "label": label,
            "package": ri.activityInfo.packageName,
            "class": ri.activityInfo.name,
        })
    return apps


def launch_app(package_name, class_name):
    if not ANDROID:
        print(f"[preview] would launch {package_name}/{class_name}")
        return
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    ComponentName = autoclass("android.content.ComponentName")
    activity = PythonActivity.mActivity
    intent = Intent(Intent.ACTION_MAIN)
    intent.addCategory(Intent.CATEGORY_LAUNCHER)
    intent.setComponent(ComponentName(package_name, class_name))
    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    activity.startActivity(intent)


class BackgroundMixin:
    def set_bg(self, hex_color):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*hex_to_rgba(hex_color))
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size


class HomeScreen(Screen, BackgroundMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cfg = load_config()
        self.root_layout = BoxLayout(orientation="vertical")
        self.add_widget(self.root_layout)
        self.set_bg(self.cfg["background_color"])
        self.clock_label = Label(size_hint=(1, None), height=dp(60), font_size="24sp")
        self.root_layout.add_widget(self.clock_label)

        scroll = ScrollView()
        self.grid = GridLayout(cols=self.cfg["columns"], spacing=dp(12),
                                padding=dp(16), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        self.root_layout.add_widget(scroll)

        settings_bar = BoxLayout(size_hint=(1, None), height=dp(48))
        settings_btn = Button(text="⚙ Settings", background_color=hex_to_rgba(self.cfg["accent_color"]))
        settings_btn.bind(on_release=lambda *_: self.manager.__setattr__("current", "settings"))
        settings_bar.add_widget(settings_btn)
        self.root_layout.add_widget(settings_bar)

        Clock.schedule_interval(self.update_clock, 1)
        self.refresh()

    def update_clock(self, *_):
        if self.cfg.get("show_clock", True):
            self.clock_label.text = datetime.now().strftime("%H:%M   %a %d %b")
            self.clock_label.color = hex_to_rgba(self.cfg["text_color"])
            self.clock_label.opacity = 1
        else:
            self.clock_label.opacity = 0

    def refresh(self):
        self.cfg = load_config()
        self.set_bg(self.cfg["background_color"])
        self.grid.cols = self.cfg["columns"]
        self.grid.clear_widgets()

        apps = get_installed_apps()
        apps = [a for a in apps if a["package"] not in self.cfg.get("hidden_apps", [])]
        if self.cfg.get("sort_by") == "name":
            apps.sort(key=lambda a: a["label"].lower())

        for app in apps:
            btn = Button(
                text=app["label"] if self.cfg["show_labels"] else "",
                size_hint_y=None,
                height=dp(self.cfg["icon_size"] + 20),
                background_normal="",
                background_color=hex_to_rgba(self.cfg["accent_color"], 0.15),
                color=hex_to_rgba(self.cfg["text_color"]),
                font_size="13sp",
            )
            btn.bind(on_release=lambda inst, a=app: launch_app(a["package"], a["class"]))
            self.grid.add_widget(btn)

    def on_pre_enter(self):
        self.refresh()


class SettingsScreen(Screen, BackgroundMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cfg = load_config()
        self.layout = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        self.add_widget(self.layout)
        self.set_bg(self.cfg["background_color"])
        self.build_ui()

    def build_ui(self):
        self.layout.clear_widgets()
        title = Label(text="Customize your launcher", size_hint=(1, None), height=dp(40),
                       font_size="20sp", color=hex_to_rgba(self.cfg["text_color"]))
        self.layout.add_widget(title)

        row1 = BoxLayout(size_hint=(1, None), height=dp(44))
        row1.add_widget(Label(text=f"Columns: {self.cfg['columns']}", color=hex_to_rgba(self.cfg["text_color"])))
        col_slider = Slider(min=2, max=6, value=self.cfg["columns"], step=1)
        col_slider.bind(value=lambda inst, v: self.update_field("columns", int(v)))
        row1.add_widget(col_slider)
        self.layout.add_widget(row1)

        row2 = BoxLayout(size_hint=(1, None), height=dp(44))
        row2.add_widget(Label(text=f"Icon size: {self.cfg['icon_size']}", color=hex_to_rgba(self.cfg["text_color"])))
        size_slider = Slider(min=48, max=120, value=self.cfg["icon_size"], step=4)
        size_slider.bind(value=lambda inst, v: self.update_field("icon_size", int(v)))
        row2.add_widget(size_slider)
        self.layout.add_widget(row2)

        for key, label in [("background_color", "Background hex"),
                            ("text_color", "Text hex"),
                            ("accent_color", "Accent hex")]:
            row = BoxLayout(size_hint=(1, None), height=dp(44))
            row.add_widget(Label(text=label, color=hex_to_rgba(self.cfg["text_color"]), size_hint=(0.4, 1)))
            ti = TextInput(text=self.cfg[key], multiline=False)
            ti.bind(text=lambda inst, v, k=key: self.update_field(k, v))
            row.add_widget(ti)
            self.layout.add_widget(row)

        row3 = BoxLayout(size_hint=(1, None), height=dp(44))
        row3.add_widget(Label(text="Show labels", color=hex_to_rgba(self.cfg["text_color"])))
        sw1 = Switch(active=self.cfg["show_labels"])
        sw1.bind(active=lambda inst, v: self.update_field("show_labels", v))
        row3.add_widget(sw1)
        self.layout.add_widget(row3)

        row4 = BoxLayout(size_hint=(1, None), height=dp(44))
        row4.add_widget(Label(text="Show clock", color=hex_to_rgba(self.cfg["text_color"])))
        sw2 = Switch(active=self.cfg["show_clock"])
        sw2.bind(active=lambda inst, v: self.update_field("show_clock", v))
        row4.add_widget(sw2)
        self.layout.add_widget(row4)

        save_btn = Button(text="Save & Apply", size_hint=(1, None), height=dp(50),
                           background_color=hex_to_rgba(self.cfg["accent_color"]))
        save_btn.bind(on_release=lambda *_: self.save_and_return())
        self.layout.add_widget(save_btn)

    def update_field(self, key, value):
        self.cfg[key] = value

    def save_and_return(self):
        save_config(self.cfg)
        self.manager.current = "home"


class PyLauncherApp(App):
    def build(self):
        Window.softinput_mode = "below_target"
        try:
            sm = ScreenManager()
            sm.add_widget(HomeScreen(name="home"))
            sm.add_widget(SettingsScreen(name="settings"))
            return sm
        except Exception:
            import traceback
            err_text = traceback.format_exc()
            root = BoxLayout(orientation="vertical", padding=dp(16))
            scroll = ScrollView()
            lbl = Label(
                text="Startup error — screenshot this:\n\n" + err_text,
                color=(1, 1, 1, 1),
                size_hint_y=None,
                halign="left",
                valign="top",
            )
            lbl.bind(width=lambda inst, w: setattr(lbl, "text_size", (w, None)))
            lbl.bind(texture_size=lambda inst, ts: setattr(lbl, "height", ts[1]))
            scroll.add_widget(lbl)
            root.add_widget(scroll)
            return root


if __name__ == "__main__":
    PyLauncherApp().run()
