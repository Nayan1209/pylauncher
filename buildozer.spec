[app]
title = PyLauncher
package.name = pylauncher
package.domain = org.nayan
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,xml
version = 1.0.0

requirements = python3==3.14.2,hostpython3==3.14.2,kivy==2.3.1,pyjnius

p4a.branch = v2026.05.09

orientation = portrait
fullscreen = 0

# Register as a HOME launcher replacement
android.manifest.intent_filters = intent_filters.xml

android.permissions = INTERNET,QUERY_ALL_PACKAGES
android.api = 36
android.minapi = 24
android.ndk = 28c
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
