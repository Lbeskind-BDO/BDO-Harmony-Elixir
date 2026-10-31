# -*- coding: utf-8 -*-
"""둥근 모서리 위젯 (Windows 11 탐색기 느낌의 작은 라운드값)
RoundFrame : tk.Frame 대용. 안에 pack/grid/place 로 위젯을 넣어 사용. bg / highlightbackground 설정이 곧 채움색 / 테두리색.
RoundButton: tk.Button 대용 (text, command, state, bg, fg, activebackground 지원)"""
import tkinter as tk
import tkinter.font as tkfont

RADIUS = 12
OUTLINE = "#3d3221"


_cache = {}


def _aa_image(w, h, r, fill, line, lw, pbg):
    """PIL 4배 슈퍼샘플링으로 안티앨리어싱된 둥근 사각형 이미지 생성 (Tk 캔버스 도형은 계단 현상이 심함)"""
    from PIL import Image, ImageDraw, ImageTk
    key = (w, h, r, fill, line, lw, pbg)
    if key in _cache:
        return _cache[key]
    S = 4
    r = max(0, min(r, w // 2, h // 2))
    im = Image.new("RGB", (w * S, h * S), pbg)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=r * S, fill=line)
    if line != fill and lw > 0:
        d.rounded_rectangle((lw * S, lw * S, w * S - 1 - lw * S, h * S - 1 - lw * S),
                            radius=max(0, r - lw) * S, fill=fill)
    elif line != fill:
        d.rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=r * S, fill=fill)
    ph = ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS))
    if len(_cache) > 900:
        _cache.clear()
    _cache[key] = ph
    return ph


def _rr(cv, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class RoundFrame(tk.Canvas):
    def __init__(self, master, bg="#000000", highlightbackground=None, radius=RADIUS,
                 pady=0, padx=0, **kw):
        ridge = kw.get("relief") == "ridge"
        for k in ("bd", "borderwidth", "relief", "highlightthickness", "background"):
            kw.pop(k, None)
        try:
            pbg = master.cget("bg")
        except tk.TclError:
            pbg = "#000000"
        self._fill = bg
        self._line = highlightbackground or (OUTLINE if ridge else bg)
        self._lw = 1 if (ridge and not highlightbackground) else 2
        self._r = radius
        kw.setdefault("width", 1)
        kw.setdefault("height", 1)
        super().__init__(master, bg=pbg, highlightthickness=0, bd=0, **kw)
        self.bind("<Configure>", lambda e: self._draw(), add="+")
        self._spacers = []
        if pady:
            for sd in ("top", "bottom"):
                sp = tk.Frame(self, height=pady, bg=bg)
                sp.pack(side=sd)
                self._spacers.append(sp)

    def _draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        try:
            pbg = self.master.cget("bg")
        except tk.TclError:
            return
        sig = (w, h, self._fill, self._line, self._lw, self._r, pbg)
        if sig == getattr(self, "_sig", None):
            return
        self._sig = sig
        try:
            if pbg != getattr(self, "_pbg_set", None):
                super().configure(bg=pbg)
                self._pbg_set = pbg
            self._ph = _aa_image(w, h, self._r, self._fill, self._line, self._lw, pbg)
            if getattr(self, "_item", None):
                self.itemconfigure(self._item, image=self._ph)
            else:
                self._item = self.create_image(0, 0, anchor="nw", image=self._ph, tags="rf")
                self.tag_lower("rf")
        except Exception:
            self.delete("rf")
            self._item = None
            m = self._lw / 2.0
            _rr(self, m, m, w - m - 1, h - m - 1, self._r, fill=self._fill, outline=self._line,
                width=self._lw, tags="rf")
            self.tag_lower("rf")

    def _redraw_children(self):
        for c in self.winfo_children():
            if isinstance(c, RoundFrame):
                c._draw()
                c._redraw_children()

    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        redraw = False
        for k in ("bg", "background"):
            if k in kw:
                self._fill = kw.pop(k)
                redraw = True
                for sp in self._spacers:
                    sp.config(bg=self._fill)
        if "highlightbackground" in kw:
            self._line = kw.pop("highlightbackground")
            redraw = True
        for k in ("highlightthickness", "bd", "relief", "borderwidth", "pady", "padx"):
            kw.pop(k, None)
        if kw:
            super().configure(**kw)
        if redraw:
            self._draw()
            self._redraw_children()

    config = configure

    def cget(self, key):
        if key in ("bg", "background"):
            return self._fill
        if key == "highlightbackground":
            return self._line
        return super().cget(key)


class RoundButton(tk.Canvas):
    def __init__(self, master, text="", command=None, font=("Arial", 10), bg="#333333", fg="#ffffff",
                 activebackground=None, activeforeground=None, padx=14, pady=6, radius=9,
                 state="normal", cursor="hand2", **kw):
        try:
            pbg = master.cget("bg")
        except tk.TclError:
            pbg = "#000000"
        self._text, self._cmd, self._font = text, command, font
        self._bg, self._fg = bg, fg
        self._abg = activebackground or bg
        self._afg = activeforeground or fg
        self._state, self._r, self._hover = state, radius, False
        f = tkfont.Font(font=font)
        w = f.measure(text) + 2 * padx
        h = f.metrics("linespace") + 2 * pady
        super().__init__(master, width=w, height=h, bg=pbg, highlightthickness=0, bd=0, cursor=cursor)
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._release)

    def _set_hover(self, v):
        self._hover = v
        self._draw()

    def _release(self, e):
        if self._state == "normal" and 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            self.invoke()

    def invoke(self):
        if self._state == "normal" and self._cmd:
            self._cmd()

    def _draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        dis = self._state == "disabled"
        fill = self._abg if (self._hover and not dis) else self._bg
        fg = "#8a8a8a" if dis else (self._afg if self._hover else self._fg)
        try:
            pbg = self.master.cget("bg")
        except tk.TclError:
            return
        sig = (w, h, fill, fg, pbg, self._text, self._font)
        if sig == getattr(self, "_sig", None):
            return
        self._sig = sig
        self.delete("all")
        try:
            super().configure(bg=pbg)
            self._ph = _aa_image(w, h, self._r, fill, fill, 0, pbg)
            self.create_image(0, 0, anchor="nw", image=self._ph)
        except Exception:
            _rr(self, 0, 0, w - 1, h - 1, self._r, fill=fill, outline=fill)
        self.create_text(w // 2, h // 2, text=self._text, fill=fg, font=self._font)

    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        for k, attr in (("text", "_text"), ("command", "_cmd"), ("font", "_font"), ("state", "_state"),
                        ("bg", "_bg"), ("background", "_bg"), ("fg", "_fg"), ("foreground", "_fg"),
                        ("activebackground", "_abg"), ("activeforeground", "_afg")):
            if k in kw:
                setattr(self, attr, kw.pop(k))
        for k in list(kw):
            if k in ("width", "height", "cursor"):
                super().configure(**{k: kw.pop(k)})
        self._draw()

    config = configure

    def cget(self, key):
        m = {"text": self._text, "state": self._state, "bg": self._bg, "fg": self._fg,
             "activebackground": self._abg, "font": self._font}
        return m[key] if key in m else super().cget(key)


_tab_imgs = []


def apply_round_tabs(style, bg, normal, selected, hover="#2a251d", radius=14):
    """ttk.Notebook 탭을 위쪽 모서리가 둥근 이미지 탭으로 교체"""
    from PIL import Image, ImageDraw, ImageTk
    S, W = 4, radius * 3

    def mk(col):
        im = Image.new("RGB", (W * S, (W + radius) * S), bg)
        ImageDraw.Draw(im).rounded_rectangle((0, 0, W * S - 1, (W + radius) * S - 1), radius=radius * S, fill=col)
        return ImageTk.PhotoImage(im.crop((0, 0, W * S, W * S)).resize((W, W), Image.LANCZOS))
    n, s, h = mk(normal), mk(selected), mk(hover)
    _tab_imgs.extend([n, s, h])
    try:
        style.element_create("RTab.tab", "image", n, ("selected", s), ("active", h),
                             border=(radius + 2, radius + 2, radius + 2, 2), padding=(0, 0, 0, 0), sticky="nswe")
    except tk.TclError:
        return
    style.layout("TNotebook.Tab", [("RTab.tab", {"sticky": "nswe", "children": [
        ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
            ("Notebook.label", {"side": "top", "sticky": ""})]})]})])
    style.configure("TNotebook", tabmargins=[2, 0, 2, 0])
