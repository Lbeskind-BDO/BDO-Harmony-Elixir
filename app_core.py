# -*- coding: utf-8 -*-
"""앱 공통: 버전/경로, 단일 실행, GitHub Releases 기반 자동 업데이트 (app.py 에서 import)"""
import ctypes
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from tkinter import messagebox

import requests

APP_TITLE = "조화의영약_4종 레시피"
CURRENT_VERSION = "3.0.1"
GITHUB_REPO = "Lbeskind-BDO/BDO-Harmony-Elixir"      # 업데이트를 확인할 GitHub 저장소
INSTALLER_ASSET = "HarmonyElixirSetup.exe"            # 릴리스에 올리는 설치 파일 이름
MUTEX_NAME = "HarmonyElixirRecipe_SingleInstance"     # installer.iss 의 AppMutex 와 동일해야 함
DATA_DIR_NAME = "HarmonyElixirRecipe"                 # %APPDATA% 아래 저장 폴더


# ───────────────────────── 저장 폴더 ─────────────────────────
def get_data_dir():
    """설정/저장 파일 위치: %APPDATA%\\HarmonyElixirRecipe (설치 폴더가 아니라서 업데이트·재설치에도 유지)"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, DATA_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    new_save = os.path.join(d, "elixir_save.json")
    old_save = os.path.join(os.path.dirname(sys.executable), "elixir_save.json")   # 예전(exe 옆) 저장 파일 이전
    if not os.path.exists(new_save) and os.path.exists(old_save):
        try:
            shutil.copy2(old_save, new_save)
        except OSError:
            pass
    return d


# ───────────────────────── 단일 실행 ─────────────────────────
_mutex_handle = None


def _bring_existing_to_front():
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, APP_TITLE)
        if hwnd:
            user32.ShowWindow(hwnd, 9)          # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def acquire_single_instance():
    """이미 실행 중이면 그 창을 앞으로 가져오고 False 반환 (새 프로세스는 종료해야 함)"""
    global _mutex_handle
    if os.name != "nt":
        return True
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    _mutex_handle = k32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.get_last_error() == 183:          # ERROR_ALREADY_EXISTS
        _bring_existing_to_front()
        return False
    return True


# ───────────────────────── 자동 업데이트 (GitHub Releases) ─────────────────────────
def _ver(v):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) or (0,)


class UpdaterMixin:
    def check_for_updates_thread(self, silent=False):
        if not getattr(sys, "frozen", False):
            if not silent:
                messagebox.showinfo("테스트 환경", "현재 .py 스크립트로 실행 중입니다.\n업데이트 기능은 설치된 프로그램에서만 작동합니다.")
            return
        if getattr(self, "_update_busy", False):
            return
        self._update_busy = True
        if not silent:
            self.update_btn.config(text="업데이트 확인 중...", state="disabled")
        threading.Thread(target=self._update_check_worker, args=(silent,), daemon=True).start()

    def _update_check_worker(self, silent):
        info, err = None, None
        try:
            r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                             headers={"Accept": "application/vnd.github+json", "User-Agent": "HarmonyElixirRecipe"},
                             timeout=8)
            if r.status_code == 404:                 # 아직 릴리스가 없음 → 최신으로 간주
                info = {"version": CURRENT_VERSION}
            else:
                r.raise_for_status()
                j = r.json()
                asset = next((a for a in j.get("assets", []) if a.get("name") == INSTALLER_ASSET), None) or {}
                info = {"version": str(j.get("tag_name", "")).lstrip("vV"), "url": asset.get("browser_download_url"),
                        "size": asset.get("size"), "digest": asset.get("digest"), "page": j.get("html_url")}
        except Exception as e:
            err = str(e)
        self.ui_queue.put(lambda: self._update_checked(info, err, silent))

    def _update_checked(self, info, err, silent):
        self._update_busy = False
        if err or not info:
            if not silent:
                messagebox.showerror("오류", "인터넷에 연결할 수 없거나 서버 오류입니다.")
                self.update_btn.config(text="↻ 업데이트 재시도", state="normal")
            return
        latest = info["version"]
        if _ver(latest) > _ver(CURRENT_VERSION):
            if not info.get("url"):
                if not silent:
                    messagebox.showwarning("업데이트", f"v{latest} 릴리스에 설치 파일이 없습니다.\n릴리스 페이지를 엽니다.")
                    if info.get("page"):
                        webbrowser.open(info["page"])
                    self.update_btn.config(text="↻ 업데이트 확인", state="normal")
                return
            self.prompt_update(latest, info)
        else:
            if not silent:
                messagebox.showinfo("업데이트", f"현재 최신 버전(v{CURRENT_VERSION})을 사용 중입니다.")
                self.update_btn.config(text="✔ 최신 버전", state="normal")

    def prompt_update(self, latest_version, info):
        if messagebox.askyesno("새로운 업데이트 발견!",
                               f"새로운 버전(v{latest_version})이 출시되었습니다!\n지금 바로 업데이트 하시겠습니까?\n\n"
                               "※ 업데이트 시 프로그램이 자동으로 껐다 켜집니다."):
            self._update_busy = True
            self.update_btn.config(text="다운로드 중... 0%", state="disabled")
            threading.Thread(target=self._download_worker, args=(info,), daemon=True).start()
        else:
            self.update_btn.config(text="↻ 업데이트 나중에", state="normal")

    def _download_worker(self, info):
        path = os.path.join(tempfile.gettempdir(), INSTALLER_ASSET)
        try:
            h = hashlib.sha256()
            with requests.get(info["url"], stream=True, timeout=20,
                              headers={"User-Agent": "HarmonyElixirRecipe"}) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length") or info.get("size") or 0)
                done, last = 0, -1
                with open(path, "wb") as f:
                    for chunk in r.iter_content(65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        h.update(chunk)
                        done += len(chunk)
                        pct = int(done * 100 / total) if total else 0
                        if pct != last:
                            last = pct
                            self.ui_queue.put(lambda p=pct: self.update_btn.config(text=f"다운로드 중... {p}%"))
            if os.path.getsize(path) < 1_000_000:
                raise RuntimeError("다운로드한 파일이 너무 작습니다.")
            digest = str(info.get("digest") or "")
            if digest.startswith("sha256:") and digest[7:].lower() != h.hexdigest():
                raise RuntimeError("파일 무결성 검사에 실패했습니다.")
            with open(path, "rb") as f:
                if f.read(2) != b"MZ":
                    raise RuntimeError("다운로드한 파일이 설치 프로그램이 아닙니다.")
        except Exception as e:
            msg = str(e)

            def fail():
                self._update_busy = False
                messagebox.showerror("업데이트 실패", f"설치 파일을 받지 못했습니다.\n({msg})\n\n릴리스 페이지를 엽니다.")
                if info.get("page"):
                    webbrowser.open(info["page"])
                self.update_btn.config(text="↻ 업데이트 재시도", state="normal")
            self.ui_queue.put(fail)
            return
        self.ui_queue.put(lambda: self._launch_installer(path))

    def _launch_installer(self, path):
        try:
            self.save_state()
        except Exception:
            pass
        # 이 프로세스가 종료될 시간을 벌고(ping 2초) 설치 프로그램을 조용히 실행 → 설치 후 자동 재실행
        cmd = f'cmd /c "ping -n 3 127.0.0.1 >nul & "{path}" /SILENT /SUPPRESSMSGBOXES /NORESTART"'
        subprocess.Popen(cmd, creationflags=0x08000000 | 0x00000008, close_fds=True)
        os._exit(0)
