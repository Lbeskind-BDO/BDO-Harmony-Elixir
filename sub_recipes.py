# -*- coding: utf-8 -*-
"""하위 재료 레시피 탭 (연금 혈액류 / 오일류) + 기대값/타이머 + 체크리스트 연동"""
import json
import tkinter as tk

from craft_timer import CraftTimer
from ui_round import RoundFrame, RoundButton

SUB_PREFIX = "하위 재료_"

# 표시 순서 = 사용자가 지정한 순서
SUB_CATEGORIES = [
    ("연금 혈액류", ["광대의 혈액", "현자의 혈액", "폭군의 혈액", "죄인의 혈액", "신수의 혈액"]),
    ("오일류", ["불굴의 오일", "재생의 오일", "타락의 오일", "평온의 오일", "폭풍의 오일"]),
]

SUB_RECIPES = {
    "광대의 혈액": ["맑은 액체 시약 1", "늑대 피 2", "어둠의 가루 1", "정령의 잎사귀 1"],
    "현자의 혈액": ["맑은 액체 시약 1", "여우 피 2", "자연의 흔적 1", "수도사의 가지 1"],
    "폭군의 혈액": ["순수한가루시약 1", "곰 피 2", "자연의 흔적 1", "수도사의 가지 1"],
    "죄인의 혈액": ["맑은 액체 시약 1", "돼지 피 2", "화염의 가루 1", "핏빛 나무 옹이 1"],
    "신수의 혈액": ["순수한가루시약 1", "도마뱀 피 2", "자연의 흔적 1", "정령의 잎사귀 1"],
    "불굴의 오일": ["광대의 혈액 1", "자연의 열매 1", "화염의 가루 1", "수도사의 가지 1"],
    "재생의 오일": ["신수의 혈액 1", "자연의 열매 1", "균열의 가루 1", "붉은 나무혹 1"],   # 붉은 나무혹 또는 천년초
    "타락의 오일": ["죄인의 혈액 1", "자연의 열매 1", "어둠의 가루 1", "정령의 잎사귀 1"],
    "평온의 오일": ["현자의 혈액 1", "자연의 열매 1", "대지의 가루 1", "핏빛 나무 옹이 1"],
    "폭풍의 오일": ["폭군의 혈액 1", "자연의 열매 1", "세월의 가루 1", "고목나무 껍질 1"],
}
SUB_NOTES = {"재생의 오일": "붉은 나무혹 대신 천년초도 사용 가능"}

PER_CRAFT_MIN, PER_CRAFT_MAX = 3.0, 3.3          # 1회 제작당 획득 개수 (대략 3~3.3개)
MAIN_NORMAL_PER_CRAFT, MAIN_HIGH_PER_CRAFT = 3.42, 0.29   # 5000회 실측: 일반 17,100 / 고급 1,450


class SubRecipeMixin:
    def setup_sub_tab(self):
        self.sub_count_var = tk.IntVar(value=self._sub_count_boot)
        self.sub_wrappers = {}
        self.sub_qty_items = []
        self._flash_jobs = {}

        body = tk.Frame(self.tab_sub, bg=self.color_bg)
        body.pack(fill="both", expand=True, padx=2, pady=(15, 8))

        # 우측 제어 패널 (먼저 pack → 폭 고정)
        ctrl = RoundFrame(body, bg=self.color_panel, relief="ridge", width=300)
        ctrl.pack(side="right", fill="y", padx=2)
        ctrl.pack_propagate(False)

        left = tk.Frame(body, bg=self.color_bg)
        left.pack(side="left", fill="both", expand=True)

        before = len(self.recipe_reset_funcs)
        for cat, names in SUB_CATEGORIES:
            sec = RoundFrame(left, bg=self.color_panel, relief="ridge")
            sec.pack(fill="x", padx=2, pady=(0, 8))
            th = RoundFrame(sec, bg=self.color_border, height=44)
            th.pack_propagate(False)
            th.pack(fill="x", padx=3, pady=3)
            tk.Label(th, text=f"◈ {cat}", font=("맑은 고딕", 14, "bold"), fg=self.color_gold,
                     bg=self.color_border).place(relx=0.5, rely=0.5, anchor="center")
            row = tk.Frame(sec, bg=self.color_panel)
            row.pack(fill="x", padx=2, pady=(0, 4))
            for i, nm in enumerate(names):
                row.grid_columnconfigure(i, weight=1, uniform="subcard")
                self._build_sub_card(row, nm).grid(row=0, column=i, sticky="new", padx=2, pady=3)
        # 하위 탭 전용 해제 함수 분리 (영약 탭 '전체 해제'와 섞이지 않게)
        self.sub_reset_funcs = self.recipe_reset_funcs[before:]
        del self.recipe_reset_funcs[before:]

        th = RoundFrame(ctrl, bg=self.color_border, height=56)
        th.pack_propagate(False)
        th.pack(fill="x", padx=3, pady=3)
        tk.Label(th, text="⚗ 하위 재료 제작", font=("맑은 고딕", 14, "bold"), fg=self.color_gold,
                 bg=self.color_border).place(relx=0.5, rely=0.5, anchor="center")
        ib = tk.Frame(ctrl, bg=self.color_panel)
        ib.pack(fill="x", padx=3, pady=(16, 4))
        tk.Label(ib, text="제작 목표 (회)", font=("맑은 고딕", 14, "bold"),
                 fg=self.color_text, bg=self.color_panel).pack()
        tk.Entry(ib, textvariable=self.sub_count_var, width=9, font=("맑은 고딕", 16, "bold"),
                 justify="center", bg="#000000", fg=self.color_gold, insertbackground="white", bd=0).pack(pady=6)
        tk.Label(ib, text="카드 클릭: 선택(노란 테두리) → 제외(어둡게) → 해제",
                 font=("맑은 고딕", 9), fg="#888888", bg=self.color_panel,
                 wraplength=260, justify="center").pack()
        bf = tk.Frame(ctrl, bg=self.color_panel)
        bf.pack(side="bottom", fill="x", padx=10, pady=10)
        RoundButton(bf, text="↺ 레시피 전체 해제", font=("맑은 고딕", 11, "bold"), bg=self.color_btn,
                    fg=self.color_gold, activebackground=self.color_border, pady=6,
                    command=self.reset_sub_states).pack(fill="x")

        def expect(n):
            lo, hi = round(n * PER_CRAFT_MIN), round(n * PER_CRAFT_MAX)
            return [("예상 획득량", f"{lo:,} ~ {hi:,}개")]
        CraftTimer(self, "sub", "하위 재료", "제작 품목",
                   lambda: self.sub_count_var, self.sub_picked_items, expect,
                   "1회 제작당 약 3 ~ 3.3개 (제작 목표 × 3.0 ~ 3.3)\n1회 실제 소요 약 1.13초 (인게임 표기는 1초)").build(ctrl)

        self.sub_count_var.trace_add("write", lambda *a: self.update_sub_quantities())
        self.update_sub_quantities()

        # 체크리스트의 혈액/오일 이름 클릭 → 이 탭으로 이동
        for nm in SUB_RECIPES:
            ui = self.ui_items_dict.get(nm)
            if ui:
                ui["lbl_name"].bind("<Button-1>", lambda e, n=nm: self.goto_sub_recipe(n))
                ui["lbl_name"].config(font=("맑은 고딕", 11, "underline"))

    def _build_sub_card(self, parent, name):
        from recipe_card import RecipeCard
        rows = []
        for ing in SUB_RECIPES[name]:
            parts = ing.split()
            iname, base = " ".join(parts[:-1]), float(parts[-1])
            rows.append((self.load_icon(iname, size=(22, 22)), iname, base))
        wrap = RecipeCard(parent, self.color_panel, self.color_alt, self.color_text, name,
                          self.load_icon(name, size=(28, 28)), rows, note=SUB_NOTES.get(name, ""),
                          gold=self.color_gold)
        self.sub_wrappers[name] = wrap
        self.sub_qty_items.extend(wrap.qty_items)
        self.bind_card(SUB_PREFIX + name, wrap)
        return wrap

    # ---------- 수량 / 선택 / 초기화 ----------
    def sub_count_value(self):
        try:
            return int(self.sub_count_var.get())
        except (tk.TclError, ValueError):
            return 0

    def update_sub_quantities(self):
        n = self.sub_count_value()
        for it in self.sub_qty_items:
            t = it["base_qty"] * n
            it["lbl_qty"].config(text=f"{int(t):,}" if float(t).is_integer() else f"{t:,.2f}")
        self.save_state()

    def sub_picked_items(self):
        return [k[len(SUB_PREFIX):] for k, v in self.recipe_states.items()
                if v == 1 and k.startswith(SUB_PREFIX)]

    def main_picked_items(self):
        return [k.split("_", 1)[-1] for k, v in self.recipe_states.items()
                if v == 1 and not k.startswith(SUB_PREFIX)]

    def sub_count_for_save(self):
        if hasattr(self, 'sub_count_var'):
            return self.sub_count_value()
        return getattr(self, '_sub_count_boot', 5000)

    def reset_sub_states(self):
        for fn in self.sub_reset_funcs:
            fn()

    # ---------- 체크리스트 → 하위 재료 탭 이동 ----------
    def goto_sub_recipe(self, name):
        self.select_tab(self.tab_sub)
        w = self.sub_wrappers.get(name)
        if not w:
            return
        if name in self._flash_jobs:
            return
        orig = w.cget("highlightbackground")
        self._flash_jobs[name] = True

        def step(i):
            if i >= 6 or not w.winfo_exists():
                self._flash_jobs.pop(name, None)
                try:
                    w.config(highlightbackground=orig)
                except tk.TclError:
                    pass
                return
            w.config(highlightbackground="#4fc3f7" if i % 2 == 0 else orig)
            self.root.after(220, lambda: step(i + 1))
        step(0)
