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
from io import BytesIO

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.switch import Switch
from kivy.uix.slider import Slider
from kivy.uix.behaviors import ButtonBehavior
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
    "app_name_color": "#FFFFFF",
    "show_labels": True,
    "show_clock": True,
    "sort_by": "name",       # name | recent
    "hidden_apps": []         # list of package names to hide
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
        # Desktop preview / testing fallback
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


_icon_cache = {}


def get_app_icon_texture(package_name):
    """Fetch and cache a real app icon as a Kivy texture. Returns None on any
    failure so a single broken icon can never take down the whole grid."""
    if package_name in _icon_cache:
        return _icon_cache[package_name]
    if not ANDROID:
        _icon_cache[package_name] = None
        return None
    try:
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Bitmap = autoclass("android.graphics.Bitmap")
        BitmapConfig = autoclass("android.graphics.Bitmap$Config")
        Canvas = autoclass("android.graphics.Canvas")
        ByteArrayOutputStream = autoclass("java.io.ByteArrayOutputStream")
        CompressFormat = autoclass("android.graphics.Bitmap$CompressFormat")

        activity = PythonActivity.mActivity
        pm = activity.getPackageManager()
        drawable = pm.getApplicationIcon(package_name)

        w = max(drawable.getIntrinsicWidth(), 1)
        h = max(drawable.getIntrinsicHeight(), 1)
        bitmap = Bitmap.createBitmap(w, h, BitmapConfig.ARGB_8888)
        canvas = Canvas(bitmap)
        drawable.setBounds(0, 0, w, h)
        drawable.draw(canvas)

        stream = ByteArrayOutputStream()
        bitmap.compress(CompressFormat.PNG, 100, stream)
        png_bytes = bytes(stream.toByteArray())

        core_img = CoreImage(BytesIO(png_bytes), ext="png")
        texture = core_img.texture
        _icon_cache[package_name] = texture
        return texture
    except Exception:
        _icon_cache[package_name] = None
        return None


class BackgroundMixin:
    _bg_color_instruction = None
    _bg_rect_instruction = None

    def set_bg(self, hex_color):
        if self._bg_color_instruction is None:
            with self.canvas.before:
                self._bg_color_instruction = Color(*hex_to_rgba(hex_color))
                self._bg_rect_instruction = Rectangle(pos=self.pos, size=self.size)
            self.bind(pos=self._update_rect, size=self._update_rect)
        else:
            self._bg_color_instruction.rgba = hex_to_rgba(hex_color)

    def _update_rect(self, *args):
        if self._bg_rect_instruction:
            self._bg_rect_instruction.pos = self.pos
            self._bg_rect_instruction.size = self.size


class AppTile(ButtonBehavior, BoxLayout):
    """One app icon + name in the grid. Name font size scales with icon
    height, so bumping the icon-size slider grows both together."""

    def __init__(self, app, cfg, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(4), **kwargs)
        self.app = app

        icon_h = dp(cfg["icon_size"])
        img = Image(size_hint=(1, None), height=icon_h, allow_stretch=True, keep_ratio=True)
        texture = get_app_icon_texture(app["package"])
        if texture:
            img.texture = texture
        self.add_widget(img)

        if cfg.get("show_labels", True):
            font_size = max(10, cfg["icon_size"] * 0.2)
            lbl = Label(
                text=app["label"],
                size_hint=(1, None),
                height=dp(20),
                font_size=f"{font_size}sp",
                color=hex_to_rgba(cfg.get("app_name_color", cfg["text_color"])),
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
            )
            lbl.bind(size=lambda inst, s: setattr(lbl, "text_size", s))
            self.add_widget(lbl)

        self.bind(on_release=self._launch)

    def _launch(self, *_):
        launch_app(self.app["package"], self.app["class"])


class HomeScreen(Screen, BackgroundMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cfg = load_config()
        self.root_layout = BoxLayout(orientation="vertical")
        self.add_widget(self.root_layout)
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
            tile_height = dp(self.cfg["icon_size"] + (24 if self.cfg["show_labels"] else 4))
            tile = AppTile(app, self.cfg, size_hint_y=None, height=tile_height)
            self.grid.add_widget(tile)

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

        # Columns
        row1 = BoxLayout(size_hint=(1, None), height=dp(44))
        row1.add_widget(Label(text=f"Columns: {self.cfg['columns']}", color=hex_to_rgba(self.cfg["text_color"])))
        col_slider = Slider(min=2, max=6, value=self.cfg["columns"], step=1)
        col_slider.bind(value=lambda inst, v: self.update_field("columns", int(v)))
        row1.add_widget(col_slider)
        self.layout.add_widget(row1)

        # Icon size
        row2 = BoxLayout(size_hint=(1, None), height=dp(44))
        row2.add_widget(Label(text=f"Icon size: {self.cfg['icon_size']}", color=hex_to_rgba(self.cfg["text_color"])))
        size_slider = Slider(min=48, max=120, value=self.cfg["icon_size"], step=4)
        size_slider.bind(value=lambda inst, v: self.update_field("icon_size", int(v)))
        row2.add_widget(size_slider)
        self.layout.add_widget(row2)

        # Colors
        for key, label in [("background_color", "Background hex"),
                            ("text_color", "Text hex"),
                            ("accent_color", "Accent hex"),
                            ("app_name_color", "App name hex")]:
            row = BoxLayout(size_hint=(1, None), height=dp(44))
            row.add_widget(Label(text=label, color=hex_to_rgba(self.cfg["text_color"]), size_hint=(0.4, 1)))
            ti = TextInput(text=self.cfg[key], multiline=False)
            ti.bind(text=lambda inst, v, k=key: self.update_field(k, v))
            row.add_widget(ti)
            self.layout.add_widget(row)

        # Labels toggle
        row3 = BoxLayout(size_hint=(1, None), height=dp(44))
        row3.add_widget(Label(text="Show labels", color=hex_to_rgba(self.cfg["text_color"])))
        sw1 = Switch(active=self.cfg["show_labels"])
        sw1.bind(active=lambda inst, v: self.update_field("show_labels", v))
        row3.add_widget(sw1)
        self.layout.add_widget(row3)

        # Clock toggle
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