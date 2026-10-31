# -*- coding: utf-8 -*-
"""카카오톡 '나에게 보내기' 알림 + 제작 타이머 (app.py 에서 import 해서 사용)"""
import json
import math
import os
import queue
import secrets
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import messagebox
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, urlencode

import requests

# ───────────────────────── 설정 (여기만 채우면 됩니다) ─────────────────────────
try:  # 키는 저장소에 올리지 않는 kakao_config.py 에 둡니다 (kakao_config.example.py 참고)
    from kakao_config import KAKAO_REST_API_KEY, KAKAO_CLIENT_SECRET
except ImportError:
    KAKAO_REST_API_KEY = ""
    KAKAO_CLIENT_SECRET = ""
KAKAO_REDIRECT_PORT = 8765   # Redirect URI: http://localhost:8765/callback 으로 등록
KAKAO_REDIRECT_URI = f"http://localhost:{KAKAO_REDIRECT_PORT}/callback"

SECONDS_PER_CRAFT = 1        # 1회 제작당 1초
GRACE_SEC = 120              # 절전/종료 등으로 늦은 '종료 N분 전' 알림은 이 시간 넘으면 생략

DEFAULT_NOTIFY = {
    "login_mode": "auto",      # auto: 자동 로그인 / manual: 수동 로그인
    "notify_end": True,        # 제작 종료 시 알림
    "notify_before": True,     # 종료 N분 전 알림
    "before_minutes": [10],
}


# ───────────────────────── 유틸 ─────────────────────────
def fmt_duration(sec):
    sec = max(0, int(round(sec)))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}시간 {m}분 {s}초"
    if m:
        return f"{m}분 {s}초"
    return f"{s}초"


def fmt_clock(sec):
    sec = max(0, int(math.ceil(sec)))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_minutes(text):
    out = []
    for p in text.replace("，", ",").replace(" ", ",").split(","):
        p = p.strip()
        if p.isdigit() and int(p) > 0 and int(p) not in out:
            out.append(int(p))
    return sorted(out, reverse=True)


# ───────────────────────── 카카오 API 클라이언트 ─────────────────────────
class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        q = parse_qs(u.query)
        self.server.result = {k: v[0] for k, v in q.items()}
        ok = "code" in q
        body = (
            "<html><head><meta charset='utf-8'><title>BDO 조화의 영약</title></head>"
            "<body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
            + ("<h2>카카오 로그인 완료</h2><p>이 창을 닫고 앱으로 돌아가세요.</p>" if ok
               else "<h2>로그인 실패</h2><p>앱에서 다시 시도해 주세요.</p>")
            + "</body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class KakaoClient:
    AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
    TOKEN_URL = "https://kauth.kakao.com/oauth/token"
    SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

    def __init__(self, base_dir):
        self.token_file = os.path.join(base_dir, "kakao_token.json")
        self.tok = {}
        self.persist = True          # True=자동 로그인(토큰 파일 저장), False=수동 로그인(메모리만)
        self._lock = threading.Lock()

    @staticmethod
    def configured():
        return bool(KAKAO_REST_API_KEY.strip())

    # ----- 토큰 보관 -----
    def load(self):
        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                self.tok = json.load(f)
        except Exception:
            self.tok = {}

    def _save(self):
        if not self.persist:
            return
        try:
            with open(self.token_file, "w", encoding="utf-8") as f:
                json.dump(self.tok, f)
        except Exception:
            pass

    def set_persist(self, flag):
        self.persist = flag
        if flag:
            if self.tok:
                self._save()
        else:
            try:
                os.remove(self.token_file)
            except OSError:
                pass

    def clear(self):
        self.tok = {}
        try:
            os.remove(self.token_file)
        except OSError:
            pass

    def logged_in(self):
        return bool(self.tok.get("refresh_token")) and \
            self.tok.get("refresh_expires_at", float("inf")) > time.time()

    def _apply(self, d):
        now = time.time()
        self.tok["access_token"] = d["access_token"]
        self.tok["access_expires_at"] = now + int(d.get("expires_in", 3600))
        if d.get("refresh_token"):
            self.tok["refresh_token"] = d["refresh_token"]
            self.tok["refresh_expires_at"] = now + int(d.get("refresh_token_expires_in", 5184000))
        self._save()

    def _token_request(self, data):
        data = dict(data, client_id=KAKAO_REST_API_KEY.strip())
        if KAKAO_CLIENT_SECRET.strip():
            data["client_secret"] = KAKAO_CLIENT_SECRET.strip()
        r = requests.post(self.TOKEN_URL, data=data, timeout=10)
        try:
            j = r.json()
        except ValueError:
            j = {}
        if r.status_code != 200 or "access_token" not in j:
            raise RuntimeError(j.get("error_description") or j.get("error") or f"HTTP {r.status_code}")
        return j

    def refresh(self):
        with self._lock:
            rt = self.tok.get("refresh_token")
            if not rt:
                raise RuntimeError("카카오톡 로그인이 필요합니다")
            try:
                j = self._token_request({"grant_type": "refresh_token", "refresh_token": rt})
            except requests.RequestException:
                raise                      # 네트워크 오류: 토큰은 유지
            except RuntimeError:
                self.clear()               # 토큰 만료/폐기: 재로그인 필요
                raise
            self._apply(j)

    # ----- 로그인 (브라우저 + 로컬 콜백) -----
    def login(self, cancel=None, timeout=180):
        if not self.configured():
            raise RuntimeError("REST API 키가 설정되지 않았습니다")
        state = secrets.token_urlsafe(16)
        try:
            server = HTTPServer(("127.0.0.1", KAKAO_REDIRECT_PORT), _CallbackHandler)
        except OSError:
            raise RuntimeError(f"포트 {KAKAO_REDIRECT_PORT} 를 사용할 수 없습니다 (다른 프로그램이 사용 중)")
        server.result = None
        server.timeout = 1
        try:
            url = self.AUTH_URL + "?" + urlencode({
                "client_id": KAKAO_REST_API_KEY.strip(),
                "redirect_uri": KAKAO_REDIRECT_URI,
                "response_type": "code",
                "scope": "talk_message",
                "state": state,
            })
            webbrowser.open(url)
            end = time.time() + timeout
            while server.result is None and time.time() < end and not (cancel and cancel.is_set()):
                server.handle_request()
        finally:
            server.server_close()
        res = server.result
        if not res:
            raise RuntimeError("로그인 시간이 초과되었거나 취소되었습니다")
        if res.get("state") != state:
            raise RuntimeError("잘못된 로그인 응답입니다")
        if "code" not in res:
            raise RuntimeError(res.get("error_description") or res.get("error") or "로그인이 취소되었습니다")
        j = self._token_request({"grant_type": "authorization_code",
                                 "redirect_uri": KAKAO_REDIRECT_URI, "code": res["code"]})
        with self._lock:
            self._apply(j)

    # ----- 나에게 보내기 -----
    def _access(self):
        if self.tok.get("access_expires_at", 0) - 60 < time.time():
            self.refresh()
        return self.tok["access_token"]

    def send_text(self, text):
        if not self.logged_in():
            raise RuntimeError("카카오톡 로그인이 필요합니다")
        link = "https://developers.kakao.com"
        tmpl = json.dumps({"object_type": "text", "text": text[:190],
                           "link": {"web_url": link, "mobile_web_url": link}}, ensure_ascii=False)
        r = None
        for attempt in (0, 1):
            r = requests.post(self.SEND_URL, headers={"Authorization": "Bearer " + self._access()},
                              data={"template_object": tmpl}, timeout=10)
            if r.status_code == 401 and attempt == 0:
                self.refresh()
                continue
            break
        try:
            j = r.json()
        except ValueError:
            j = {}
        if r.status_code != 200 or j.get("result_code") != 0:
            raise RuntimeError(j.get("msg") or f"HTTP {r.status_code}")


# ───────────────────────── 앱에 섞어 쓰는 Mixin ─────────────────────────
class NotifierMixin:
    # ===== 초기화 / 시작 =====
    def notify_init_state(self):
        """load_save_data() 직후 호출: 알림 설정·타이머 상태 로드, 카카오 클라이언트 생성"""
        self.notify_settings = dict(DEFAULT_NOTIFY)
        self.timer_state = None
        try:
            with open(self.save_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            ns, ts = data.get("notify"), data.get("timer")
            if isinstance(ns, dict):
                self.notify_settings.update(ns)
            if isinstance(ts, dict):
                self.timer_state = ts
        except Exception:
            pass
        self.ui_queue = queue.Queue()
        self.timer_job = None
        self.login_busy = False
        self.cfg_win = None
        self.kakao = KakaoClient(os.path.dirname(self.save_file))
        if self.notify_settings.get("login_mode") == "auto":
            self.kakao.persist = True
            self.kakao.load()
        else:
            self.kakao.set_persist(False)

    def notify_start(self):
        """UI 구성이 모두 끝난 뒤 호출"""
        self._poll_ui_queue()
        self.count_var.trace_add("write", lambda *a: self.refresh_timer_idle())
        self.refresh_login_ui()
        if self.kakao.persist and self.kakao.logged_in():
            threading.Thread(target=self._verify_login, daemon=True).start()
        if self.timer_state:
            self.timer_tick()
        else:
            self.refresh_timer_idle()

    def _poll_ui_queue(self):
        try:
            while True:
                fn = self.ui_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass
        self.root.after(300, self._poll_ui_queue)

    def _verify_login(self):
        try:
            self.kakao.refresh()
        except Exception:
            pass
        self.ui_queue.put(self.refresh_login_ui)

    # ===== 탭 줄 오른쪽 버튼 (알림 설정 / 카카오톡 로그인) =====
    def build_tab_actions(self):
        bar = tk.Frame(self.notebook, bg=self.color_bg)
        bar.place(relx=1.0, x=-6, y=12, anchor="ne")
        self.btn_notify_cfg = tk.Button(
            bar, text="🔔 알림 설정", font=("맑은 고딕", 11, "bold"), bg=self.color_btn, fg=self.color_gold,
            activebackground=self.color_border, activeforeground=self.color_gold,
            relief="flat", padx=14, pady=6, cursor="hand2", command=self.open_notify_settings)
        self.btn_notify_cfg.pack(side="left", padx=(0, 8))
        self.btn_kakao = tk.Button(
            bar, text="💬 카카오톡 로그인", font=("맑은 고딕", 11, "bold"), bg="#FEE500", fg="#191919",
            activebackground="#F5DC00", activeforeground="#191919",
            relief="flat", padx=14, pady=6, cursor="hand2", command=self.on_kakao_click)
        self.btn_kakao.pack(side="left")
        bar.lift()

    def refresh_login_ui(self):
        if not hasattr(self, "btn_kakao"):
            return
        if self.kakao.logged_in():
            self.btn_kakao.config(text="✔ 카카오톡 연결됨", bg="#3a6b3a", fg="#ffffff",
                                  activebackground="#4a8b4a", activeforeground="#ffffff", state="normal")
        else:
            self.btn_kakao.config(text="💬 카카오톡 로그인", bg="#FEE500", fg="#191919",
                                  activebackground="#F5DC00", activeforeground="#191919", state="normal")

    def on_kakao_click(self):
        if self.login_busy:
            return
        if self.kakao.logged_in():
            if messagebox.askyesno("카카오톡", "카카오톡 연결을 해제(로그아웃)할까요?"):
                self.kakao.clear()
                self.refresh_login_ui()
            return
        if not self.kakao.configured():
            messagebox.showwarning(
                "카카오톡 설정 필요",
                "kakao_config.py 의 KAKAO_REST_API_KEY 에\n카카오 디벨로퍼스 REST API 키를 입력해 주세요.\n\n"
                f"Redirect URI : {KAKAO_REDIRECT_URI}\n동의항목 : 카카오톡 메시지 전송(talk_message)")
            return
        self.login_busy = True
        self.btn_kakao.config(text="⏳ 브라우저에서 로그인 중...", state="disabled")

        def work():
            err = None
            try:
                self.kakao.login()
            except Exception as e:
                err = str(e)

            def done():
                self.login_busy = False
                self.refresh_login_ui()
                if err:
                    messagebox.showerror("카카오톡 로그인 실패", err)
            self.ui_queue.put(done)
        threading.Thread(target=work, daemon=True).start()

    # ===== 알림 전송 =====
    def notify_async(self, text, tag="알림"):
        def work():
            err = None
            for _ in range(3):
                try:
                    self.kakao.send_text(text)
                    err = None
                    break
                except Exception as e:
                    err = str(e)
                    if not self.kakao.logged_in():
                        break
                    time.sleep(5)
            self.ui_queue.put(lambda: self.on_notify_result(tag, err))
        threading.Thread(target=work, daemon=True).start()

    def on_notify_result(self, tag, err):
        self.refresh_login_ui()
        now = time.strftime("%H:%M:%S")
        if err:
            self.notify_status.config(text=f"✖ {tag} 전송 실패 ({now})\n{err}", fg="#e06c6c")
        else:
            self.notify_status.config(text=f"✔ {tag} 전송 완료 ({now})", fg="#7fc47f")

    # ===== 타이머 UI (레시피 탭 우하단) =====
    def build_timer_controls(self, parent):
        box = tk.Frame(parent, bg=self.color_panel, bd=1, relief="ridge")
        box.pack(side="bottom", fill="x", padx=10, pady=(0, 6))
        tk.Label(box, text="⏱ 제작 타이머", font=("맑은 고딕", 11, "bold"),
                 fg=self.color_text, bg=self.color_panel).pack(pady=(8, 0))
        self.timer_label = tk.Label(box, text="--:--:--", font=("맑은 고딕", 22, "bold"),
                                    fg=self.color_gold, bg=self.color_panel)
        self.timer_label.pack()
        self.timer_info = tk.Label(box, text="", font=("맑은 고딕", 9), fg="#aaaaaa",
                                   bg=self.color_panel, wraplength=260, justify="center")
        self.timer_info.pack(pady=(0, 4))
        row = tk.Frame(box, bg=self.color_panel)
        row.pack(fill="x", padx=10, pady=(0, 6))
        self.btn_timer_start = tk.Button(
            row, text="▶ 시작", font=("맑은 고딕", 11, "bold"), bg="#2e6b3a", fg="#ffffff",
            activebackground="#3b8a4b", activeforeground="#ffffff", relief="flat", pady=6,
            cursor="hand2", command=self.timer_start)
        self.btn_timer_start.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_timer_stop = tk.Button(
            row, text="■ 정지", font=("맑은 고딕", 11, "bold"), bg="#7a2f2f", fg="#ffffff",
            activebackground="#9a3f3f", activeforeground="#ffffff", relief="flat", pady=6,
            cursor="hand2", command=self.timer_stop, state="disabled")
        self.btn_timer_stop.pack(side="left", expand=True, fill="x", padx=(4, 0))
        self.notify_status = tk.Label(box, text="", font=("맑은 고딕", 9), fg="#aaaaaa",
                                      bg=self.color_panel, wraplength=260, justify="center")
        self.notify_status.pack(pady=(0, 8))

    def _target_count(self):
        try:
            return int(self.count_var.get())
        except (tk.TclError, ValueError):
            return 0

    def refresh_timer_idle(self):
        if self.timer_state or not hasattr(self, "timer_label"):
            return
        count = self._target_count()
        total = max(0, count) * SECONDS_PER_CRAFT
        self.timer_label.config(text=fmt_clock(total) if count > 0 else "--:--:--")
        self.timer_info.config(text=f"목표 {count:,}회 → {fmt_duration(total)}" if count > 0
                               else "제작 목표 횟수를 입력하세요")
        self.btn_timer_start.config(state="normal")
        self.btn_timer_stop.config(state="disabled")

    def refresh_timer_ui(self, rem=None):
        ts = self.timer_state
        if not ts:
            self.refresh_timer_idle()
            return
        self.timer_label.config(text=fmt_clock(rem if rem is not None else ts["end_ts"] - time.time()))
        self.timer_info.config(text=f"진행 중 · 목표 {ts['count']:,}회 ({fmt_duration(ts['total'])})")
        self.btn_timer_start.config(state="disabled")
        self.btn_timer_stop.config(state="normal")

    # ===== 타이머 로직 (종료 시각 기준 → 오차 누적 없음, 앱 재시작 시 이어짐) =====
    def potion_suffix(self, ts=None):
        names = (ts or self.timer_state or {}).get("potions") or []
        if not names:
            return ""
        s = ", ".join(names[:3]) + (f" 외 {len(names) - 3}" if len(names) > 3 else "")
        return f"\n비약: {s}"

    def timer_start(self):
        if self.timer_state:
            return
        count = self._target_count()
        if count <= 0:
            messagebox.showwarning("타이머", "제작 목표 횟수를 1 이상으로 입력해 주세요.")
            return
        if not self.kakao.logged_in():
            if not messagebox.askyesno("카카오톡 미연결",
                                       "카카오톡에 로그인되어 있지 않습니다.\n알림 없이 타이머만 시작할까요?"):
                return
        total = count * SECONDS_PER_CRAFT
        picked = [k.split("_", 1)[-1] for k, v in getattr(self, "recipe_states", {}).items() if v == 1]
        self.timer_state = {"end_ts": time.time() + total, "total": total, "count": count,
                            "fired": [], "potions": picked}
        self.notify_status.config(text="")
        self.save_state()
        self.timer_tick()

    def timer_tick(self):
        self.timer_job = None
        ts = self.timer_state
        if not ts:
            self.refresh_timer_ui()
            return
        rem = ts["end_ts"] - time.time()
        if rem <= 0:
            self.timer_finish()
            return
        ns = self.notify_settings
        if ns.get("notify_before"):
            for m in ns.get("before_minutes", []):
                if m in ts["fired"] or m * 60 >= ts["total"]:
                    continue
                if rem <= m * 60:
                    ts["fired"].append(m)
                    if rem >= m * 60 - GRACE_SEC:
                        self.notify_async(
                            f"⏰ 조화의 영약 제작 종료 {m}분 전입니다.\n남은 시간: {fmt_duration(rem)}"
                            f"\n목표 {ts['count']:,}회{self.potion_suffix(ts)}", "종료 전 알림")
                    self.save_state()
        self.refresh_timer_ui(rem)
        self.timer_job = self.root.after(500, self.timer_tick)

    def timer_finish(self):
        ts = self.timer_state
        late = time.time() - ts["end_ts"]
        if self.notify_settings.get("notify_end"):
            msg = (f"✅ 조화의 영약 제작 완료!\n목표 {ts['count']:,}회 ({fmt_duration(ts['total'])}) "
                   f"시간이 끝났습니다.{self.potion_suffix(ts)}")
            if late > 60:
                msg += f"\n(앱이 꺼져 있어 {fmt_duration(late)} 늦게 알림)"
            self.notify_async(msg, "종료 알림")
        self.timer_state = None
        self.save_state()
        self.refresh_timer_idle()
        self.timer_info.config(text="타이머 종료 ✔")

    def timer_stop(self):
        if self.timer_job:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None
        self.timer_state = None
        self.save_state()
        self.refresh_timer_idle()
        self.timer_info.config(text="정지됨")

    # ===== 알림 설정 창 =====
    def open_notify_settings(self):
        if self.cfg_win is not None and self.cfg_win.winfo_exists():
            self.cfg_win.lift()
            return
        ns = self.notify_settings
        win = tk.Toplevel(self.root)
        self.cfg_win = win
        win.title("알림 설정")
        win.configure(bg=self.color_bg)
        win.resizable(False, False)
        win.transient(self.root)
        w, h = 520, 440
        x = self.root.winfo_x() + max(0, (self.root.winfo_width() - w) // 2)
        y = self.root.winfo_y() + max(0, (self.root.winfo_height() - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

        v_mode = tk.StringVar(value=ns.get("login_mode", "auto"))
        v_end = tk.BooleanVar(value=bool(ns.get("notify_end", True)))
        v_before = tk.BooleanVar(value=bool(ns.get("notify_before", True)))
        v_min = tk.StringVar(value=", ".join(str(m) for m in ns.get("before_minutes", [10])))

        def group(title):
            g = tk.LabelFrame(win, text=f" {title} ", font=("맑은 고딕", 11, "bold"), fg=self.color_gold,
                              bg=self.color_panel, bd=1, relief="ridge", padx=12, pady=8)
            g.pack(fill="x", padx=18, pady=(14, 0))
            return g

        def radio(parent, text, val):
            tk.Radiobutton(parent, text=text, value=val, variable=v_mode, font=("맑은 고딕", 10),
                           fg=self.color_text, bg=self.color_panel, selectcolor="#000000",
                           activebackground=self.color_panel, activeforeground=self.color_gold,
                           anchor="w", justify="left").pack(fill="x", pady=2)

        def check(parent, text, var):
            tk.Checkbutton(parent, text=text, variable=var, font=("맑은 고딕", 10),
                           fg=self.color_text, bg=self.color_panel, selectcolor="#000000",
                           activebackground=self.color_panel, activeforeground=self.color_gold,
                           anchor="w").pack(fill="x", pady=2)

        g1 = group("로그인 방식")
        radio(g1, "자동 로그인 — 앱을 켜면 자동으로 연결 (토큰을 이 PC에 저장)", "auto")
        radio(g1, "수동 로그인 — 저장하지 않음, 켤 때마다 직접 로그인", "manual")

        g2 = group("알림 시점")
        check(g2, "제작 종료 시 알림", v_end)
        check(g2, "종료 몇 분 전에도 알림", v_before)
        row = tk.Frame(g2, bg=self.color_panel)
        row.pack(fill="x", pady=(2, 0))
        tk.Label(row, text="종료", font=("맑은 고딕", 10), fg=self.color_text, bg=self.color_panel).pack(side="left", padx=(24, 4))
        tk.Entry(row, textvariable=v_min, width=14, font=("맑은 고딕", 12, "bold"), justify="center",
                 bg="#000000", fg=self.color_gold, insertbackground="white", bd=0).pack(side="left")
        tk.Label(row, text="분 전", font=("맑은 고딕", 10), fg=self.color_text, bg=self.color_panel).pack(side="left", padx=4)
        tk.Label(g2, text="여러 개는 쉼표로 구분 (예: 30, 10, 5)\n목표 시간보다 긴 값은 자동으로 건너뜁니다.",
                 font=("맑은 고딕", 9), fg="#aaaaaa", bg=self.color_panel, justify="left").pack(anchor="w", padx=24, pady=(4, 0))

        count = self._target_count()
        tk.Label(win, text=f"현재 제작 목표 {count:,}회 → 타이머 {fmt_duration(count * SECONDS_PER_CRAFT)}",
                 font=("맑은 고딕", 10), fg=self.color_text, bg=self.color_bg).pack(pady=(14, 0))

        btns = tk.Frame(win, bg=self.color_bg)
        btns.pack(side="bottom", fill="x", padx=18, pady=16)

        def do_test():
            if not self.kakao.logged_in():
                messagebox.showinfo("알림 설정", "먼저 카카오톡에 로그인해 주세요.", parent=win)
                return
            self.notify_async("🔔 조화의 영약 알림 테스트입니다.", "테스트 알림")
            messagebox.showinfo("알림 설정", "테스트 메시지를 보냈습니다.\n카카오톡 '나와의 채팅'을 확인하세요.", parent=win)

        def do_save():
            mins = parse_minutes(v_min.get())
            if v_before.get() and not mins:
                messagebox.showwarning("알림 설정", "종료 전 알림 시간(분)을 숫자로 입력해 주세요.", parent=win)
                return
            ns["login_mode"] = v_mode.get()
            ns["notify_end"] = bool(v_end.get())
            ns["notify_before"] = bool(v_before.get())
            ns["before_minutes"] = mins or ns.get("before_minutes", [10])
            self.kakao.set_persist(ns["login_mode"] == "auto")
            self.save_state()
            win.destroy()

        def mk(text, cmd, bg, fg):
            return tk.Button(btns, text=text, command=cmd, font=("맑은 고딕", 11, "bold"), bg=bg, fg=fg,
                             activebackground=self.color_border, activeforeground=self.color_gold,
                             relief="flat", padx=14, pady=6, cursor="hand2")
        mk("테스트 메시지", do_test, self.color_btn, self.color_gold).pack(side="left")
        mk("닫기", win.destroy, self.color_panel, self.color_text).pack(side="right")
        mk("저장", do_save, "#2e6b3a", "#ffffff").pack(side="right", padx=8)
