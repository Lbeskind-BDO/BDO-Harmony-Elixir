# -*- coding: utf-8 -*-
"""레시피 카드: 위젯 수십 개 대신 Canvas 하나로 그리는 카드 (색 변경 시 깜빡임 없이 한 번에 갱신)"""
import tkinter as tk
import tkinter.font as tkfont

from ui_round import _aa_image

F_TITLE = ("맑은 고딕", 12, "bold")
F_NAME = ("맑은 고딕", 10)
F_NAME_S = ("맑은 고딕", 9)
F_QTY = ("맑은 고딕", 10, "bold")
F_NOTE = ("맑은 고딕", 8)


class _Qty:
    """기존 Label.config(text=...) 호출과 호환되는 수량 표시 핸들"""
    def __init__(self, cv, item):
        self.cv, self.item = cv, item

    def config(self, **kw):
        if "text" in kw:
            self.cv.itemconfigure(self.item, text=kw["text"])

    configure = config

    def cget(self, k):
        return self.cv.itemcget(self.item, "text") if k == "text" else ""


class RecipeCard(tk.Canvas):
    """rows: [(아이콘 PhotoImage|None, 재료명, 기본수량(float)), ...]
    colors = (테두리, 카드 배경, 제목줄 배경, 제목 글자, 재료명 글자, 수량 글자)"""

    def __init__(self, master, color_panel, color_alt, color_text, title, icon, rows,
                 n_rows=None, note="", gold="#d4af37"):
        self._r, self._lw = 12, 2
        self._pbg = master.cget("bg")
        self._panel, self._alt, self._text = color_panel, color_alt, color_text
        self._icon, self._rows = icon, rows
        self._n = n_rows or len(rows)
        ft = tkfont.Font(font=F_TITLE)
        fn = tkfont.Font(font=F_NAME)
        self._tbh = max(32, ft.metrics("linespace") + 4)
        self._rh = max(24, fn.metrics("linespace") + 2)
        self._fh = (tkfont.Font(font=F_NOTE).metrics('linespace') + 8) if note else 0
        self._H = 4 + self._tbh + 3 + self._n * self._rh + self._fh + 5
        super().__init__(master, width=1, height=self._H, bg=self._pbg, highlightthickness=0, bd=0,
                         cursor="hand2")
        self._c = (color_panel, color_panel, color_alt, color_text, "#aaaaaa", "#888888")
        self._sig = None
        self.i_bg = self.create_image(0, 0, anchor="nw")
        self.i_tb = self.create_image(0, 0, anchor="nw")
        if icon:
            self.i_icon = self.create_image(0, 0, image=icon, anchor="center")
        else:
            self.i_icon = self.create_text(0, 0, text="▶", fill=gold, font=("Arial", 10), anchor="center")
        self.i_title = self.create_text(0, 0, text=title, font=F_TITLE, fill=color_text, anchor="w")
        self.i_note = self.create_text(0, 0, text=f"※ {note}" if note else "", font=F_NOTE,
                                       fill="#888888", anchor="w")
        self.i_rows = []
        self.qty_items = []
        for k, (ic, name, base) in enumerate(rows):
            a = self.create_image(0, 0, image=ic, anchor="center") if ic else \
                self.create_text(0, 0, text="·", fill="#777777", anchor="center")
            b = self.create_text(0, 0, text=name, font=F_NAME, fill="#aaaaaa", anchor="w")
            q = self.create_text(0, 0, text=f"{int(base)}" if float(base).is_integer() else f"{base}",
                                 font=F_QTY, fill="#888888", anchor="e")
            self.i_rows.append((a, b, q))
            self.qty_items.append({"base_qty": float(base), "lbl_qty": _Qty(self, q)})
        self.bind("<Configure>", lambda e: self._layout(), add="+")

    # ---- 호환: RoundFrame 처럼 highlightbackground 로 테두리색 변경 (깜빡임 효과 등) ----
    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        if "highlightbackground" in kw:
            self.set_colors((kw.pop("highlightbackground"),) + self._c[1:])
        if kw:
            super().configure(**kw)

    config = configure

    def cget(self, key):
        if key == "highlightbackground":
            return self._c[0]
        return super().cget(key)

    def set_colors(self, c):
        self._c = tuple(c)
        border, panel, alt, tfg, nfg, qfg = self._c
        self.itemconfigure(self.i_title, fill=tfg)
        for a, b, q in self.i_rows:
            self.itemconfigure(b, fill=nfg)
            self.itemconfigure(q, fill=qfg)
        if self._icon is None:
            pass
        self._layout(force=True)

    def _images(self, w, h, c):
        border, panel, alt = c[0], c[1], c[2]
        bg = _aa_image(w, h, self._r, panel, border, self._lw, self._pbg)
        tbw = max(8, w - 12)
        tb = _aa_image(tbw, self._tbh, 9, alt, alt, 0, panel)
        return bg, tb

    def prewarm(self, states):
        w, h = self.winfo_width(), self.winfo_height()
        if w > 20 and h > 20:
            for c in states:
                self._images(w, h, c)

    def _layout(self, force=False):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or h < 20:
            return
        sig = (w, h, self._c)
        if sig == self._sig and not force:
            return
        geo_changed = self._sig is None or self._sig[:2] != (w, h)
        self._sig = sig
        self._bg_ph, self._tb_ph = self._images(w, h, self._c)
        self.itemconfigure(self.i_bg, image=self._bg_ph)
        self.itemconfigure(self.i_tb, image=self._tb_ph)
        if not geo_changed and not force:
            return
        if geo_changed:
            self.coords(self.i_bg, 0, 0)
            self.coords(self.i_tb, 6, 4)
            ty = 4 + self._tbh / 2
            self.coords(self.i_icon, 25, ty)
            self.coords(self.i_title, 45, ty)
            y0 = 4 + self._tbh + 3
            self.coords(self.i_note, 18, y0 + self._n * self._rh + self._fh / 2)
            for k, (a, b, q) in enumerate(self.i_rows):
                cy = y0 + k * self._rh + self._rh / 2
                self.coords(a, 29, cy)
                self.coords(b, 46, cy)
                self.coords(q, w - 25, cy)
                qb = self.bbox(q)
                avail = (qb[0] if qb else w - 70) - 8 - 46
                nm = self.itemcget(b, "text")
                self.itemconfigure(b, font=F_NAME)
                if tkfont.Font(font=F_NAME).measure(nm) > avail:
                    self.itemconfigure(b, font=F_NAME_S)
            for it in (self.i_icon, self.i_title, self.i_note):
                self.tag_raise(it)
            for a, b, q in self.i_rows:
                for it in (a, b, q):
                    self.tag_raise(it)
