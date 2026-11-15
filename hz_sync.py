# -*- coding: utf-8 -*-
"""모바일 앱(서버)과 실시간 양방향 연동 (app.py 에서 Mixin 으로 사용)
- 카카오 로그인은 서버(워커)에서 처리 → 이 PC 에는 토큰만 저장
- 상태는 필드 단위(op)로 주고받음. 서버 프로토콜은 모바일 앱과 동일."""
import json
import os
import secrets
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import messagebox
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

try:
    import websocket          # pip install websocket-client
except ImportError:           # 없으면 연동만 비활성
    websocket = None

SERVER = "https://harmony-elixir.libebank.workers.dev"
WS_URL = "wss://harmony-elixir.libebank.workers.dev/api/ws"
NOTIFY_KEYS = ("notify_end", "notify_before", "before_minutes")


class _LoginHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path != "/hz-login":
            self.send_response(404)
            self.end_headers()
            return
        tok = (parse_qs(u.query).get("token") or [""])[0]
        ok = len(tok) >= 32 and tok.isalnum()
        if ok:
            self.server.token = tok
        body = (
            "<html><head><meta charset='utf-8'><title>조화의 영약</title></head>"
            "<body style='font-family:sans-serif;text-align:center;margin-top:80px;background:#12110e;color:#e6ce8a'>"
            + ("<h2>모바일 연동 완료</h2><p>이 창을 닫고 앱으로 돌아가세요.</p>" if ok
               else "<h2>로그인 실패</h2><p>앱에서 다시 시도해 주세요.</p>")
            + "</body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _eq(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _copy(v):
    return json.loads(json.dumps(v)) if isinstance(v, (dict, list)) else v


def _ok_path(p):
    if not p or not isinstance(p[0], str):
        return False
    if p[0] in ("checklist", "recipes"):
        return len(p) == 2
    if p[0] == "notify":
        return len(p) == 2 and p[1] in NOTIFY_KEYS
    return len(p) == 1 and p[0] in ("target_count", "sub_target_count", "variant", "timer", "timer_sub")


class HzSyncMixin:
    # ───────────── 시작/종료 ─────────────
    def hz_start(self):
        self._hz = {"ws": None, "shadow": None, "synced": False, "stop": False, "applying": False,
                    "thread": None, "cid": "pc" + secrets.token_hex(4), "last_rx": 0.0}
        self._hz_tokfile = os.path.join(os.path.dirname(self.save_file), "hz_token.json")
        self._hz_token = self._hz_load_token()
        self._hz_ready = True
        self.hz_refresh_btn()
        if self._hz_token and websocket:
            self._hz_connect()

    def _hz_load_token(self):
        try:
            with open(self._hz_tokfile, "r", encoding="utf-8") as f:
                return json.load(f).get("token", "")
        except Exception:
            return ""

    def _hz_save_token(self, tok):
        self._hz_token = tok
        try:
            if tok:
                with open(self._hz_tokfile, "w", encoding="utf-8") as f:
                    json.dump({"token": tok}, f)
            elif os.path.exists(self._hz_tokfile):
                os.remove(self._hz_tokfile)
        except Exception:
            pass

    # ───────────── 버튼 ─────────────
    def hz_refresh_btn(self):
        b = getattr(self, "btn_hz", None)
        if b is None:
            return
        st = getattr(self, "_hz", None) or {}
        if not getattr(self, "_hz_token", ""):
            b.config(text="📱 모바일 연동", bg="#2f4f6f", fg="#ffffff", activebackground="#3b6794", activeforeground="#ffffff")
        elif st.get("synced"):
            b.config(text="✔ 모바일 연동됨", bg="#3a6b3a", fg="#ffffff", activebackground="#4a8b4a", activeforeground="#ffffff")
        else:
            b.config(text="⏳ 모바일 연결 중…", bg="#6b5a2e", fg="#ffffff", activebackground="#8a7438", activeforeground="#ffffff")

    def on_hz_click(self):
        if not websocket:
            messagebox.showerror("모바일 연동", "websocket-client 모듈이 없어 연동을 사용할 수 없습니다.")
            return
        if self._hz_token:
            if messagebox.askyesno("모바일 연동", "모바일 연동을 해제할까요?\n(이 PC의 로그인 정보만 지워지며, 모바일 데이터는 유지됩니다)"):
                self.hz_logout()
            return
        if getattr(self, "_hz_login_busy", False):
            return
        self._hz_login_busy = True
        self.btn_hz.config(text="⏳ 브라우저에서 로그인 중…")

        def work():
            err, tok = None, ""
            try:
                srv = HTTPServer(("127.0.0.1", 0), _LoginHandler)
                srv.token, srv.timeout = "", 1
                try:
                    webbrowser.open(f"{SERVER}/auth/kakao/login?pc={srv.server_port}")
                    end = time.time() + 180
                    while not srv.token and time.time() < end:
                        srv.handle_request()
                finally:
                    srv.server_close()
                tok = srv.token
                if not tok:
                    err = "로그인 시간이 초과되었거나 취소되었습니다"
            except Exception as e:
                err = str(e)

            def done():
                self._hz_login_busy = False
                if tok:
                    self._hz_save_token(tok)
                    self._hz_connect()
                self.hz_refresh_btn()
                if err:
                    messagebox.showerror("모바일 연동 실패", err)
            self.ui_queue.put(done)
        threading.Thread(target=work, daemon=True).start()

    def hz_logout(self):
        st = self._hz
        st["stop"] = True
        try:
            if st["ws"]:
                st["ws"].close()
        except Exception:
            pass
        st.update(ws=None, shadow=None, synced=False)
        self._hz_save_token("")
        self.hz_refresh_btn()

    # ───────────── 연결 ─────────────
    def _hz_connect(self):
        st = self._hz
        if st["thread"] and st["thread"].is_alive():
            return
        st["stop"] = False
        st["thread"] = threading.Thread(target=self._hz_loop, daemon=True)
        st["thread"].start()

    def _hz_loop(self):
        st = self._hz
        delay = 2
        while not st["stop"] and self._hz_token:
            alive = threading.Event()
            alive.set()

            def on_open(ws):
                st["last_rx"] = time.time()
                threading.Thread(target=keep, args=(ws,), daemon=True).start()

            def keep(ws):
                while alive.is_set() and not st["stop"]:
                    time.sleep(25)
                    try:
                        if time.time() - st["last_rx"] > 80:
                            ws.close()
                            return
                        ws.send("ping")
                    except Exception:
                        return

            def on_message(ws, msg):
                st["last_rx"] = time.time()
                if msg == "pong":
                    return
                try:
                    m = json.loads(msg)
                except ValueError:
                    return
                t = m.get("t")
                if t == "hello":
                    self.ui_queue.put(lambda m=m: self._hz_on_hello(m))
                elif t == "op":
                    self.ui_queue.put(lambda m=m: self._hz_on_op(m))
                elif t == "notify":
                    self.ui_queue.put(lambda m=m: self.hz_toast(m.get("title") or "조화의 영약", m.get("body") or "",
                                                                m.get("kind")))

            def on_error(ws, err):
                if getattr(err, "status_code", None) == 401:     # 토큰 만료 → 재로그인 필요
                    st["stop"] = True
                    self.ui_queue.put(lambda: [self._hz_save_token(""), self.hz_refresh_btn()])

            ws = websocket.WebSocketApp(WS_URL, header=["Authorization: Bearer " + self._hz_token],
                                        on_open=on_open, on_message=on_message, on_error=on_error)
            st["ws"] = ws
            t0 = time.time()
            try:
                ws.run_forever()
            except Exception:
                pass
            alive.clear()
            st["synced"] = False
            self.ui_queue.put(self.hz_refresh_btn)
            if time.time() - t0 > 20:
                delay = 2
            for _ in range(int(delay * 2)):
                if st["stop"]:
                    return
                time.sleep(0.5)
            delay = min(delay * 2, 30)

    # ───────────── 상태 ↔ 평면 dict ─────────────
    def _hz_flat(self):
        f = {}
        for k, v in getattr(self, "saved_state", {}).items():
            if v is True:
                f[("checklist", k)] = True
        for k, v in getattr(self, "recipe_states", {}).items():
            if v:
                f[("recipes", k)] = int(v)
        try:
            f[("target_count",)] = int(self.count_var.get())
        except Exception:
            pass
        try:
            f[("sub_target_count",)] = int(self.sub_count_for_save())
        except Exception:
            pass
        f[("variant",)] = getattr(self, "current_variant", "에다니아")
        for k in NOTIFY_KEYS:
            if k in self.notify_settings:
                f[("notify", k)] = _copy(self.notify_settings[k])
        for key, name in (("main", "timer"), ("sub", "timer_sub")):
            s = self.timer_get(key)
            if isinstance(s, dict):
                f[(name,)] = _copy(s)
        return f

    @staticmethod
    def _hz_flat_from_state(d):
        f = {}
        if not isinstance(d, dict):
            return f
        for sect in ("checklist", "recipes"):
            for k, v in (d.get(sect) or {}).items():
                if v:
                    f[(sect, k)] = True if sect == "checklist" else int(v)
        ns = d.get("notify") or {}
        for k in NOTIFY_KEYS:
            if k in ns:
                f[("notify", k)] = _copy(ns[k])
        for k in ("target_count", "sub_target_count", "variant"):
            if d.get(k) is not None:
                f[(k,)] = d[k]
        for k in ("timer", "timer_sub"):
            if isinstance(d.get(k), dict):
                f[(k,)] = _copy(d[k])
        return f

    @staticmethod
    def _hz_nest(flat):
        out = {}
        for p, v in flat.items():
            o = out
            for k in p[:-1]:
                o = o.setdefault(k, {})
            o[p[-1]] = v
        return out

    @staticmethod
    def _hz_diff(old, new):
        ops = []
        for p, v in new.items():
            if p not in old or not _eq(old[p], v):
                ops.append({"p": list(p), "v": v})
        for p in old:
            if p not in new:
                ops.append({"p": list(p), "d": 1})
        return ops

    # ───────────── 보내기 ─────────────
    def hz_push(self):
        st = getattr(self, "_hz", None)
        if not st or not getattr(self, "_hz_ready", False) or st["applying"] or not st["synced"] or st["shadow"] is None:
            return
        cur = self._hz_flat()
        ops = self._hz_diff(st["shadow"], cur)
        if not ops:
            return
        try:
            for i in range(0, len(ops), 400):
                st["ws"].send(json.dumps({"t": "op", "cid": st["cid"], "ops": ops[i:i + 400]}))
        except Exception:
            return                      # 실패 시 shadow 유지 → 재연결 후 다시 전송
        st["shadow"] = cur

    # ───────────── 받기 ─────────────
    def _hz_on_hello(self, m):
        st = self._hz
        srv = m.get("state")
        cur = self._hz_flat()
        if srv is None:                                  # 서버가 비어 있으면 이 PC 데이터로 초기화
            try:
                st["ws"].send(json.dumps({"t": "init", "state": self._hz_nest(cur)}))
            except Exception:
                return
            st["shadow"], st["synced"] = cur, True
            self.hz_refresh_btn()
            return
        sflat = self._hz_flat_from_state(srv)
        target = dict(sflat)
        if st["shadow"] is not None:                     # 재연결: 연결 끊긴 동안의 PC 변경분은 유지
            for p in set(cur) | set(st["shadow"]):
                if p in st["shadow"] and p in cur and _eq(st["shadow"][p], cur[p]):
                    continue
                if p not in st["shadow"] and p not in cur:
                    continue
                if p in cur:
                    target[p] = cur[p]
                else:
                    target.pop(p, None)
        self._hz_apply_ops(self._hz_diff(cur, target))
        st["shadow"], st["synced"] = sflat, True
        self.hz_refresh_btn()
        self.hz_push()

    def _hz_on_op(self, m):
        st = self._hz
        ops = [o for o in (m.get("ops") or []) if isinstance(o, dict) and isinstance(o.get("p"), list)
               and _ok_path(tuple(o["p"]))]
        if st["shadow"] is not None:
            for o in ops:
                p = tuple(o["p"])
                v = o.get("v")
                if o.get("d") or v is None or v is False or v == 0 and p[0] == "recipes":
                    st["shadow"].pop(p, None)
                else:
                    st["shadow"][p] = _copy(v)
        self._hz_apply_ops(ops)

    def _hz_apply_ops(self, ops):
        if not ops:
            return
        st = self._hz
        st["applying"] = True
        try:
            prog = False
            for o in ops:
                p = tuple(o["p"])
                v = None if o.get("d") else o.get("v")
                try:
                    prog |= self._hz_apply_one(p, v)
                except Exception:
                    pass
            if prog and hasattr(self, "update_progress"):
                self.update_progress()
            self.save_state()
        finally:
            st["applying"] = False

    def _hz_apply_one(self, p, v):
        k = p[0]
        if k == "checklist":
            val = bool(v)
            names = [p[1]]
            other = self.LINKED_ITEMS.get(p[1])
            if other:
                names.append(other)
            for n in names:
                self.saved_state[n] = val
                mat = self.global_materials.get(n)
                if mat:
                    mat["is_done"].set(val)
            return True
        if k == "recipes":
            val = int(v or 0)
            self.recipe_states[p[1]] = val
            fn = getattr(self, "recipe_apply", {}).get(p[1])
            if fn:
                fn(val)
        elif k == "target_count" and v is not None:
            self.count_var.set(int(v))
        elif k == "sub_target_count" and v is not None and hasattr(self, "sub_count_var"):
            self.sub_count_var.set(int(v))
        elif k == "variant" and v and v != getattr(self, "current_variant", None) and v in self.variant_btn_frames:
            self.change_variant(v)
        elif k == "notify":
            if v is None:
                self.notify_settings.pop(p[1], None)
            else:
                self.notify_settings[p[1]] = v
        elif k in ("timer", "timer_sub"):
            t = self.timers.get("main" if k == "timer" else "sub")
            if t:
                if t.job:
                    try:
                        self.root.after_cancel(t.job)
                    except Exception:
                        pass
                    t.job = None
                if isinstance(v, dict):
                    v.setdefault("fired", [])
                    v.setdefault("potions", [])
                    t.state = v
                    t.tick()
                else:
                    t.state = None
                    t.refresh_idle()
        return False

    # ───────────── 데스크톱 알림창 ─────────────
    def hz_toast(self, title, body, kind=None):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
        try:
            w = tk.Toplevel(self.root)
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            w.configure(bg=self.color_gold)
            box = tk.Frame(w, bg=self.color_panel, padx=16, pady=12)
            box.pack(padx=1, pady=1)
            tk.Label(box, text=title, font=("맑은 고딕", 12, "bold"), fg=self.color_gold, bg=self.color_panel,
                     anchor="w", justify="left", wraplength=340).pack(fill="x")
            if body:
                tk.Label(box, text=body, font=("맑은 고딕", 10), fg=self.color_text, bg=self.color_panel,
                         anchor="w", justify="left", wraplength=340).pack(fill="x", pady=(4, 0))
            w.update_idletasks()
            x = w.winfo_screenwidth() - w.winfo_reqwidth() - 24
            y = w.winfo_screenheight() - w.winfo_reqheight() - 70
            w.geometry(f"+{x}+{y}")
            for wd in (w, box) + tuple(box.winfo_children()):
                wd.bind("<Button-1>", lambda e: w.destroy())
            w.after(8000, lambda: w.winfo_exists() and w.destroy())
        except Exception:
            pass
