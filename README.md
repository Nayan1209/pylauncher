# PyLauncher

A minimalistic, fully-customizable Android home-screen launcher, written in
Python (Kivy + pyjnius). No app is hardcoded — it reads whatever's actually
installed on your phone, and every visual detail (columns, icon size,
colors, labels, clock, hidden apps) is editable from the in-app **⚙
Settings** screen, saved to `config.json` on-device.

## Deploy in ~45–60 minutes (no local Android SDK needed)

The APK is built for you by GitHub Actions — you never install Buildozer
or the Android SDK locally. You just need `git` and a GitHub account.

### 1. Create the repo (2 min)
Go to https://github.com/new, name it e.g. `pylauncher`, keep it **empty**
(no README/gitignore), and create it.

### 2. Push this project (3 min)
From this project folder, run:

```bash
cd PyLauncher
git init
git add .
git commit -m "Initial commit: PyLauncher"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/pylauncher.git
git push -u origin main
```

### 3. Let Actions build the APK (20–35 min, automatic)
The push triggers `.github/workflows/build-apk.yml`. Watch it live at:
`https://github.com/<YOUR_USERNAME>/pylauncher/actions`

First builds are slow (Android SDK/NDK + Kivy toolchain download inside the
CI runner) — expect 20–35 minutes. Every build after that is faster because
of caching.

### 4. Download the APK
When the workflow finishes (green check ✅), open that run → **Artifacts**
→ download `PyLauncher-apk` → unzip to get `pylauncher-1.0.0-debug.apk`.

### 5. Install on your phone (5 min)
- Transfer the APK to your phone (Google Drive, email to yourself, USB, etc.)
- Tap the APK file → allow "install from unknown sources" if prompted →
  Install.

### 6. Make it your default launcher (1 min)
Phone **Settings → Apps → Default apps → Home app** → select **PyLauncher**.
(Exact wording varies by Android skin — e.g. on some phones it's
**Settings → Home screen → Default Home app**.)

You can switch back to your original launcher the same way, anytime.

## Customizing further
Everything the Settings screen doesn't expose (fonts, animations, gestures,
widgets) lives in plain, short `main.py` — it's ~250 lines, organized into
`HomeScreen` and `SettingsScreen`. Edit, commit, push — Actions rebuilds
automatically.

## Local testing on desktop (optional, before you build the APK)
```bash
pip install kivy
python main.py
```
Runs in a desktop window with demo apps so you can preview layout/colors
before committing to a mobile build.
