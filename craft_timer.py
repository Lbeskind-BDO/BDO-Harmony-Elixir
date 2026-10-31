# -*- coding: utf-8 -*-
"""제작 타이머 + 기대값 패널 (영약 탭 / 하위 재료 탭 공용)"""
import time
import tkinter as tk
from ui_round import RoundFrame, RoundButton
from tkinter import messagebox

from kakao_notify import SECONDS_PER_CRAFT, GRACE_SEC, fmt_duration, fmt_clock


class CraftTimer:
    """key: 'main' | 'sub'. app: HarmonyElixirApp (NotifierMixin 포함)
    get_var(): 제작 목표 IntVar, get_items(): 선택된 품목 이름 리스트
    expect_fn(count) -> [(라벨, 값), ...], note: 기대값 하단 안내문"""

    def __init__(self, app, key, title, item_label, get_var, get_items, expect_fn, note=""):
        self.app, self.key, self.title, self.item_label = app, key, title, item_label
        self.get_var, self.get_items, self.expect_fn, self.note = get_var, get_items, expect_fn, note
        self.state = app.timer_saved.get(key) if isinstance(app.timer_saved.get(key), dict) else None
        self.job = None
        app.timers[key] = self

    # ---------- UI ----------
    def build(self, parent):
        a = self.app
        box = RoundFrame(parent, bg=a.color_panel, relief="ridge")
        box.pack(side="bottom", fill="x", padx=10, pady=(0, 6))
        self.label = tk.Label(box, text="--:--:--", font=("맑은 고딕", 20, "bold"),
                              fg=a.color_gold, bg=a.color_panel)
        self.label.pack(pady=(6, 0))
        self.info = tk.Label(box, text="", font=("맑은 고딕", 9), fg="#aaaaaa",
                             bg=a.color_panel, wraplength=260, justify="center")
        self.info.pack(pady=(0, 2))

        # 기대값 (시작/정지 버튼 바로 위)
        tk.Frame(box, height=1, bg=a.color_border).pack(fill="x", padx=10, pady=2)
        self.exp_lbls = []
        for _ in range(len(self.expect_fn(0))):
            r = tk.Frame(box, bg=a.color_panel)
            r.pack(fill="x", padx=12)
            l1 = tk.Label(r, text="", font=("맑은 고딕", 10), fg=a.color_text, bg=a.color_panel)
            l1.pack(side="left")
            l2 = tk.Label(r, text="", font=("맑은 고딕", 10, "bold"), fg=a.color_gold, bg=a.color_panel)
            l2.pack(side="right")
            self.exp_lbls.append((l1, l2))
        tk.Label(box, text="📊 " + self.note, font=("맑은 고딕", 8), fg="#888888", bg=a.color_panel,
                 wraplength=250, justify="center").pack(pady=(0, 4))

        row = tk.Frame(box, bg=a.color_panel)
        row.pack(fill="x", padx=10, pady=(0, 4))
        self.btn_start = RoundButton(
            row, text="▶ 시작", font=("맑은 고딕", 11, "bold"), bg="#2e6b3a", fg="#ffffff",
            activebackground="#3b8a4b", activeforeground="#ffffff", relief="flat", pady=4,
            cursor="hand2", command=self.begin)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_stop = RoundButton(
            row, text="■ 정지", font=("맑은 고딕", 11, "bold"), bg="#7a2f2f", fg="#ffffff",
            activebackground="#9a3f3f", activeforeground="#ffffff", relief="flat", pady=4,
            cursor="hand2", command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=(4, 0))
        self.status = tk.Label(box, text="", font=("맑은 고딕", 9), fg="#aaaaaa",
                               bg=a.color_panel, wraplength=260, justify="center")
        self.status.pack(pady=(0, 4))

    def start(self):
        """UI 구성 완료 후 호출"""
        self.get_var().trace_add("write", lambda *x: self.refresh_idle())
        if self.state:
            self.tick()
        else:
            self.refresh_idle()

    # ---------- 값 ----------
    def count(self):
        try:
            return int(self.get_var().get())
        except (tk.TclError, ValueError):
            return 0

    def refresh_expect(self):
        for (l1, l2), (name, val) in zip(self.exp_lbls, self.expect_fn(max(0, self.count()))):
            l1.config(text=name)
            l2.config(text=val)

    def refresh_idle(self):
        self.refresh_expect()
        if self.state:
            return
        n = self.count()
        total = max(0, n) * SECONDS_PER_CRAFT
        self.label.config(text=fmt_clock(total) if n > 0 else "--:--:--")
        self.info.config(text=f"목표 {n:,}회 → {fmt_duration(total)}" if n > 0 else "제작 목표 횟수를 입력하세요")
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")

    def refresh_ui(self, rem=None):
        s = self.state
        if not s:
            self.refresh_idle()
            return
        self.refresh_expect()
        self.label.config(text=fmt_clock(rem if rem is not None else s["end_ts"] - time.time()))
        self.info.config(text=f"진행 중 · 목표 {s['count']:,}회 ({fmt_duration(s['total'])})")
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")

    def suffix(self, s=None):
        names = (s or self.state or {}).get("potions") or []
        if not names:
            return ""
        t = ", ".join(names[:3]) + (f" 외 {len(names) - 3}" if len(names) > 3 else "")
        return f"\n{self.item_label}: {t}"

    # ---------- 로직 (종료 시각 기준, 앱 재시작 시 이어짐) ----------
    def begin(self):
        a = self.app
        if self.state:
            return
        n = self.count()
        if n <= 0:
            messagebox.showwarning("타이머", "제작 목표 횟수를 1 이상으로 입력해 주세요.")
            return
        if not a.kakao.logged_in():
            if not messagebox.askyesno("카카오톡 미연결",
                                       "카카오톡에 로그인되어 있지 않습니다.\n알림 없이 타이머만 시작할까요?"):
                return
        total = n * SECONDS_PER_CRAFT
        self.state = {"end_ts": time.time() + total, "total": total, "count": n,
                      "fired": [], "potions": list(self.get_items())}
        self.status.config(text="")
        a.save_state()
        self.tick()

    def tick(self):
        a = self.app
        self.job = None
        s = self.state
        if not s:
            self.refresh_ui()
            return
        rem = s["end_ts"] - time.time()
        if rem <= 0:
            self.finish()
            return
        ns = a.notify_settings
        if ns.get("notify_before"):
            for m in ns.get("before_minutes", []):
                if m in s["fired"] or m * 60 >= s["total"]:
                    continue
                if rem <= m * 60:
                    s["fired"].append(m)
                    if rem >= m * 60 - GRACE_SEC:
                        a.notify_async(
                            f"⏰ {self.title} 제작 종료 {m}분 전입니다.\n남은 시간: {fmt_duration(rem)}"
                            f"\n목표 {s['count']:,}회{self.suffix(s)}", "종료 전 알림", self)
                    a.save_state()
        self.refresh_ui(rem)
        self.job = a.root.after(500, self.tick)

    def finish(self):
        a = self.app
        s = self.state
        late = time.time() - s["end_ts"]
        if a.notify_settings.get("notify_end"):
            msg = (f"✅ {self.title} 제작 완료!\n목표 {s['count']:,}회 ({fmt_duration(s['total'])}) "
                   f"시간이 끝났습니다.{self.suffix(s)}")
            if late > 60:
                msg += f"\n(앱이 꺼져 있어 {fmt_duration(late)} 늦게 알림)"
            a.notify_async(msg, "종료 알림", self)
        self.state = None
        a.save_state()
        self.refresh_idle()
        self.info.config(text="타이머 종료 ✔")

    def stop(self):
        if self.job:
            self.app.root.after_cancel(self.job)
            self.job = None
        self.state = None
        self.app.save_state()
        self.refresh_idle()
        self.info.config(text="정지됨")
