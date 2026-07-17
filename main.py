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
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
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
    "columns": 1,
    "app_text_size": 24,
    "text_align": "left",
    "background_color": "#000000",
    "text_color": "#FFFFFF",
    "accent_color": "#7C5CFF",
    "app_name_color": "#FFFFFF",
    "show_clock": True,
    "sort_by": "name",       # name | recent
    "hidden_apps": []         # list of package names to hide
}

COLOR_PALETTE = [
    ("Black", "#000000"),
    ("White", "#FFFFFF"),
    ("Dark Gray", "#1C1C1E"),
    ("Light Gray", "#D1D1D6"),
    ("Navy", "#0A1F44"),
    ("Indigo", "#4B3F72"),
    ("Purple", "#7C5CFF"),
    ("Teal", "#2EC4B6"),
    ("Forest", "#1B5E20"),
    ("Olive", "#6B7A3D"),
    ("Crimson", "#D7263D"),
    ("Orange", "#FF7A00"),
    ("Amber", "#FFC300"),
    ("Pink", "#FF6F91"),
    ("Brown", "#5C4033"),
    ("Sky", "#3AA6FF"),
]


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


def _resolve_label(ri, pm):
    """Try several ways to get a proper app name — .toString() on the
    CharSequence loadLabel() returns can fail via pyjnius, so try str()
    and an alternate API before giving up and using the package name."""
    try:
        label_obj = ri.loadLabel(pm)
        if label_obj is not None:
            text = str(label_obj)
            if text:
                return text
    except Exception:
        pass
    try:
        label_obj = pm.getApplicationLabel(ri.activityInfo.applicationInfo)
        if label_obj is not None:
            text = str(label_obj)
            if text:
                return text
    except Exception:
        pass
    return ri.activityInfo.packageName


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
        apps.append({
            "label": _resolve_label(ri, pm),
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


class AppRow(ButtonBehavior, BoxLayout):
    """One app name in the list — text only, tappable to launch."""

    def __init__(self, app, cfg, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        lbl = Label(
            text=app["label"],
            font_size=f"{cfg.get('app_text_size', 24)}sp",
            color=hex_to_rgba(cfg.get("app_name_color", cfg["text_color"])),
            halign=cfg.get("text_align", "left"),
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
    """Minimal home screen: just the clock. Swipe up to see your apps."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cfg = load_config()
        layout = BoxLayout(orientation="vertical")
        self.add_widget(layout)

        layout.add_widget(Widget(size_hint_y=0.35))

        self.time_label = Label(font_size="52sp", size_hint=(1, None), height=dp(70))
        layout.add_widget(self.time_label)

        self.date_label = Label(font_size="18sp", size_hint=(1, None), height=dp(30))
        layout.add_widget(self.date_label)

        self.hint_label = Label(text="↑  swipe up for apps", font_size="14sp",
                                 size_hint=(1, None), height=dp(30), opacity=0.5)
        layout.add_widget(self.hint_label)

        layout.add_widget(Widget())

        Clock.schedule_interval(self.update_clock, 1)

    def update_clock(self, *_):
        self.cfg = load_config()
        self.set_bg(self.cfg["background_color"])
        if self.cfg.get("show_clock", True):
            self.time_label.text = datetime.now().strftime("%H:%M")
            self.date_label.text = datetime.now().strftime("%A, %d %B")
            self.time_label.opacity = 1
            self.date_label.opacity = 1
        else:
            self.time_label.opacity = 0
            self.date_label.opacity = 0
        text_color = hex_to_rgba(self.cfg["text_color"])
        self.time_label.color = text_color
        self.date_label.color = text_color
        self.hint_label.color = hex_to_rgba(self.cfg["text_color"], 0.5)

    def on_pre_enter(self):
        self.update_clock()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud["start_y"] = touch.y
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if "start_y" in touch.ud:
            if touch.y - touch.ud["start_y"] < -dp(60):
                self.manager.current = "apps"
        return super().on_touch_up(touch)


class AppsScreen(Screen, BackgroundMixin):
    """Full app list — reached by swiping up from Home."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cfg = load_config()
        self.root_layout = BoxLayout(orientation="vertical")
        self.add_widget(self.root_layout)

        top_bar = BoxLayout(size_hint=(1, None), height=dp(48), spacing=dp(8), padding=[dp(8), 0])
        home_btn = Button(text="⌂ Home", background_color=hex_to_rgba(self.cfg["accent_color"]))
        home_btn.bind(on_release=lambda *_: self.manager.__setattr__("current", "home"))
        settings_btn = Button(text="⚙ Settings", background_color=hex_to_rgba(self.cfg["accent_color"]))
        settings_btn.bind(on_release=lambda *_: self.manager.__setattr__("current", "settings"))
        top_bar.add_widget(home_btn)
        top_bar.add_widget(settings_btn)
        self.root_layout.add_widget(top_bar)

        scroll = ScrollView()
        self.grid = GridLayout(cols=self.cfg["columns"], spacing=dp(18),
                                padding=[dp(24), dp(16)], size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        self.root_layout.add_widget(scroll)

    def refresh(self):
        self.cfg = load_config()
        self.set_bg(self.cfg["background_color"])
        self.grid.cols = self.cfg["columns"]
        self.grid.clear_widgets()

        apps = get_installed_apps()
        apps = [a for a in apps if a["package"] not in self.cfg.get("hidden_apps", [])]
        if self.cfg.get("sort_by") == "name":
            apps.sort(key=lambda a: a["label"].lower())

        row_height = dp(self.cfg.get("app_text_size", 24) + 30)
        for app in apps:
            row = AppRow(app, self.cfg, size_hint_y=None, height=row_height)
            self.grid.add_widget(row)

    def on_pre_enter(self):
        self.refresh()


class SettingsScreen(Screen, BackgroundMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cfg = load_config()
        self.scroll = ScrollView()
        self.add_widget(self.scroll)
        self.layout = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(18),
                                 size_hint_y=None)
        self.layout.bind(minimum_height=self.layout.setter("height"))
        self.scroll.add_widget(self.layout)
        self.set_bg(self.cfg["background_color"])
        self.build_ui()

    def build_ui(self):
        self.layout.clear_widgets()
        title = Label(text="Customize your launcher", size_hint=(1, None), height=dp(40),
                       font_size="20sp", color=hex_to_rgba(self.cfg["text_color"]))
        self.layout.add_widget(title)

        # Columns
        row1 = BoxLayout(orientation="vertical", size_hint=(1, None), height=dp(60), spacing=dp(4))
        row1.add_widget(Label(text=f"Columns: {self.cfg['columns']}", size_hint=(1, None), height=dp(24),
                               color=hex_to_rgba(self.cfg["text_color"])))
        col_slider = Slider(min=1, max=4, value=self.cfg["columns"], step=1, size_hint=(1, None), height=dp(30))
        col_slider.bind(value=lambda inst, v: self.update_field("columns", int(v)))
        row1.add_widget(col_slider)
        self.layout.add_widget(row1)

        # Text size
        row2 = BoxLayout(orientation="vertical", size_hint=(1, None), height=dp(60), spacing=dp(4))
        row2.add_widget(Label(text=f"Text size: {self.cfg['app_text_size']}", size_hint=(1, None), height=dp(24),
                               color=hex_to_rgba(self.cfg["text_color"])))
        size_slider = Slider(min=16, max=40, value=self.cfg["app_text_size"], step=1,
                              size_hint=(1, None), height=dp(30))
        size_slider.bind(value=lambda inst, v: self.update_field("app_text_size", int(v)))
        row2.add_widget(size_slider)
        self.layout.add_widget(row2)

        # Text alignment — visual picker, no typing
        align_wrap = BoxLayout(orientation="vertical", size_hint=(1, None), height=dp(64), spacing=dp(6))
        align_wrap.add_widget(Label(text="Text alignment", size_hint=(1, None), height=dp(20),
                                     color=hex_to_rgba(self.cfg["text_color"])))
        align_row = BoxLayout(size_hint=(1, None), height=dp(38), spacing=dp(8))
        for value, label in [("left", "Left"), ("center", "Center"), ("right", "Right")]:
            selected = self.cfg.get("text_align", "left") == value
            btn = Button(
                text=label,
                background_normal="",
                background_color=hex_to_rgba(self.cfg["accent_color"], 1.0 if selected else 0.25),
            )
            btn.bind(on_release=lambda inst, v=value: self.set_align(v))
            align_row.add_widget(btn)
        align_wrap.add_widget(align_row)
        self.layout.add_widget(align_wrap)

        # Colors — visual swatches, no hex typing
        for key, label in [("background_color", "Background color"),
                            ("text_color", "Text color"),
                            ("accent_color", "Accent color"),
                            ("app_name_color", "App name color")]:
            self.layout.add_widget(self._build_color_row(label, key))

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

    def _build_color_row(self, label_text, cfg_key):
        container = BoxLayout(orientation="vertical", size_hint=(1, None), height=dp(84), spacing=dp(6))

        header = BoxLayout(size_hint=(1, None), height=dp(24))
        header.add_widget(Label(text=label_text, color=hex_to_rgba(self.cfg["text_color"]),
                                 halign="left", size_hint=(0.75, 1)))
        preview = Button(background_normal="", background_color=hex_to_rgba(self.cfg[cfg_key]),
                          size_hint=(0.25, 1), disabled=True)
        header.add_widget(preview)
        container.add_widget(header)

        scroll = ScrollView(size_hint=(1, None), height=dp(44), do_scroll_y=False)
        swatch_row = BoxLayout(size_hint=(None, 1), spacing=dp(8))
        swatch_row.bind(minimum_width=swatch_row.setter("width"))
        for _, hexval in COLOR_PALETTE:
            sw = Button(size_hint=(None, 1), width=dp(40), background_normal="",
                        background_color=hex_to_rgba(hexval))
            sw.bind(on_release=lambda inst, k=cfg_key, h=hexval, p=preview: self._set_color(k, h, p))
            swatch_row.add_widget(sw)
        scroll.add_widget(swatch_row)
        container.add_widget(scroll)
        return container

    def _set_color(self, key, hexval, preview_widget):
        self.cfg[key] = hexval
        preview_widget.background_color = hex_to_rgba(hexval)

    def set_align(self, value):
        self.cfg["text_align"] = value
        self.build_ui()

    def update_field(self, key, value):
        self.cfg[key] = value

    def save_and_return(self):
        save_config(self.cfg)
        self.manager.current = "apps"


class PyLauncherApp(App):
    def build(self):
        Window.softinput_mode = "below_target"
        try:
            sm = ScreenManager()
            sm.add_widget(HomeScreen(name="home"))
            sm.add_widget(AppsScreen(name="apps"))
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