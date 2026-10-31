import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import re
import threading
import requests
import subprocess
import webbrowser
from PIL import Image, ImageTk
from kakao_notify import KakaoClient, NotifierMixin

from app_core import (APP_TITLE, CURRENT_VERSION, UpdaterMixin, get_data_dir,
                      acquire_single_instance)

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

if getattr(sys, 'frozen', False):
    SAVE_DIR = get_data_dir()
else:
    SAVE_DIR = os.path.dirname(os.path.abspath(__file__))

ICON_DIR = get_resource_path('icons')

def get_clean_string(text):
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', text)

class HarmonyElixirApp(NotifierMixin, UpdaterMixin):
    def __init__(self, root):
        self.root = root
        self.root.geometry("1680x1045") 
        
        self.color_bg = "#12110e"          
        self.color_panel = "#1c1a16"       
        self.color_alt = "#24211c"         
        self.color_text = "#c8b997"        
        self.color_gold = "#e6ce8a"        
        self.color_checked = "#4a4437"     
        self.color_border = "#3d3221"      
        self.color_btn = "#523c22"
        self.color_check_mark = "#ffffff"  
        self.color_titlebar = "#12110e" 
        
        self.root.configure(bg=self.color_bg)
        self.save_file = os.path.join(SAVE_DIR, "elixir_save.json")
        self.all_selected = False

        if getattr(sys, 'frozen', False):
            cleanup_files = [
                "updater.bat", "updater.vbs", 
                os.path.basename(sys.executable) + ".new", 
                os.path.basename(sys.executable) + ".old"
            ]
            for leftover in cleanup_files:
                p = os.path.join(SAVE_DIR, leftover)
                if os.path.exists(p):
                    try: os.remove(p)
                    except: pass
        
        self.setup_custom_titlebar()
        self.setup_resizing()
        self.root.after(100, self.apply_win11_round_corners)

        self.master_item_catalog = {
            "기본 재료류": ["정제수", "맑은 액체 시약", "순수한가루시약", "생명력 회복제(소형)", "블랙스톤 가루"],
            "오일류": ["재생의 오일", "타락의 오일", "평온의 오일", "폭풍의 오일", "불굴의 오일"],
            "연금 혈액류": ["광대의 혈액", "현자의 혈액", "폭군의 혈액", "죄인의 혈액", "신수의 혈액"],
            "혈액류": ["곰 피 / 사자 피", "늑대 피 / 코뿔소 피", "돼지 피", "여우 피"],
            "상점 버섯류": ["구름 버섯", "유령 버섯", "하늘 버섯", "화살 버섯", "황제 버섯", "난쟁이 버섯", "점쟁이 버섯", "호랑이 버섯"],
            "채집 버섯류": ["특상품 혹 버섯", "특상품 광대 버섯", "송로 버섯", "특상품 태고 버섯", "특상품 허풍선이"],
            "채집/노드류": ["야생 들풀", "은빛 철쭉", "화염비늘꽃", "여명초", "어둠의 가루", "붉은 나무혹", "정령의 잎사귀", "화염의 가루", "세월의 가루", "고목나무 껍질", "수도사의 가지", "핏빛 나무 옹이", "자연의 흔적", "그리폰의 발톱"],
            "수액류": ["삼나무 수액", "카프라스나무수액", "소나무 수액", "단풍나무 수액", "측백나무 수액", "자작나무 수액", "물푸레나무 수액", "설원 삼나무 수액", "전나무 수액"],
            "간이연금": ["마력이 깃든 촉매제", "이벨랍의 정수"]
        }
        
        self.category_cols = {
            "기본 재료류": 0, "오일류": 0, "연금 혈액류": 1, "혈액류": 1,
            "상점 버섯류": 2, "채집 버섯류": 2, "채집/노드류": 3,
            "수액류": 4, "간이연금": 4
        }

        self.recipes_detailed = {
            "격노의 영약": {
                "분노의 비약": ["물푸레나무 수액 1", "난쟁이 버섯 4", "곰 피 4", "정제수 3"], 
                "광란의 비약": ["재생의 오일 1", "맑은 액체 시약 5", "유령 버섯 2", "자연의 흔적 3", "삼나무 수액 5"],
                "집중의 비약": ["맑은 액체 시약 1", "구름 버섯 3", "곰 피 3", "야생 들풀 2"],
                "파괴의 비약": ["폭풍의 오일 1", "자연의 흔적 3", "맑은 액체 시약 5", "화염의 가루 5", "설원 삼나무 수액 7"]
            },
            "적응의 영약": {
                "나선의 비약": ["측백나무 수액 6", "수도사의 가지 3", "광대의 혈액 2", "화염의 가루 2", "정제수 3"], 
                "방어의 비약": ["맑은 액체 시약 1", "물푸레나무 수액 6", "돼지 피 5", "정제수 3"], 
                "생명력의 비약": ["순수한가루시약 1", "생명력 회복제(소형) 3", "은빛 철쭉 3", "여우 피 5"], 
                "기력의 비약": ["순수한가루시약 1", "자작나무 수액 5", "곰 피 4", "난쟁이 버섯 2"]
            },
            "잠재의 영약": {
                "바람의 비약": ["현자의 혈액 1", "점쟁이 버섯 5", "어둠의 가루 2", "소나무 수액 5"], 
                "주문의 비약": ["폭군의 혈액 1", "화염비늘꽃 5", "어둠의 가루 2", "단풍나무 수액 3"], 
                "충격의 비약": ["광대의 혈액 1", "호랑이 버섯 5", "세월의 가루 3", "삼나무 수액 7"], 
                "신속의 비약": ["신수의 혈액 1", "화살 버섯 5", "어둠의 가루 2", "자작나무 수액 5"]
            },
            "타락의 영약": {
                "관통의 비약": ["타락의 오일 1", "맑은 액체 시약 4", "특상품 허풍선이 1", "자연의 흔적 2", "소나무 수액 5"], 
                "죽음의 비약": ["평온의 오일 1", "맑은 액체 시약 6", "특상품 태고 버섯 1", "자연의 흔적 2", "물푸레나무 수액 7"], 
                "사신의 비약": ["불굴의 오일 1", "순수한가루시약 4", "하늘 버섯 2", "자연의 흔적 4", "수도사의 가지 2"],
                "약탈의 비약": ["불굴의 오일 1", "맑은 액체 시약 4", "특상품 혹 버섯 1", "자연의 흔적 2", "자작나무 수액 4"]
            },
            "광폭의 영약": {
                "암살자의 비약": ["재생의 오일 1", "순수한가루시약 5", "특상품 광대 버섯 1", "자연의 흔적 2", "붉은 나무혹 2"], 
                "간파의 비약": ["폭풍의 오일 1", "순수한가루시약 6", "송로 버섯 3", "자연의 흔적 3", "고목나무 껍질 2"], 
                "학살자의 비약": ["타락의 오일 1", "순수한가루시약 7", "호랑이 버섯 2", "자연의 흔적 3", "정령의 잎사귀 2"], 
                "하늘의 비약": ["평온의 오일 1", "순수한가루시약 6", "황제 버섯 1", "자연의 흔적 4", "핏빛 나무 옹이 2"]
            }
        }

        self.variant_recipes = {
            "아인": {
                "아인 사냥의 비약": ["죄인의 혈액 1", "화살 버섯 4", "블랙스톤 가루 3", "전나무 수액 4"],
                "의지의 비약": ["순수한가루시약 1", "여명초 4", "늑대 피 6", "정제수 3"]
            },
            "카마실비아": {
                "그리폰의 비약": ["그리폰의 발톱 1", "삼나무 수액 6", "자연의 흔적 3", "정제수 3", "죄인의 혈액 2"],
                "의지의 비약": ["순수한가루시약 1", "여명초 4", "늑대 피 6", "정제수 3"]
            },
            "인간": {
                "인간 사냥의 비약": ["광대의 혈액 1", "점쟁이 버섯 4", "블랙스톤 가루 3", "단풍나무 수액 4"],
                "의지의 비약": ["순수한가루시약 1", "여명초 4", "늑대 피 6", "정제수 3"]
            },
            "에다니아": {
                "에다니아의 비약": ["죄인의 혈액 2", "자연의 흔적 4", "고목나무 껍질 5", "맑은 액체 시약 5", "카프라스나무수액 6"], 
                "의지의 비약": ["순수한가루시약 1", "여명초 4", "늑대 피 6", "정제수 3"]
            }
        }

        self.icon_cache = {}
        self.available_icons = {}
        self.scan_icons_folder()
        self.preload_all_icons()
        self.set_app_icon()

        self.load_save_data()
        self.notify_init_state()
        
        # 🚨 [초고속 아키텍처] 모든 재료를 한 번에 변수로 등록 (재생성 금지)
        self.global_materials = {}
        for cat_name, items in self.master_item_catalog.items():
            for item in items:
                is_checked = bool(self.saved_state.get(item, False))
                self.global_materials[item] = {"name": item, "base_qty": 0, "is_done": tk.BooleanVar(value=is_checked)}

        self.watermark_label = tk.Label(self.root, text="by 리베스킨트", font=("맑은 고딕", 10, "italic"), bg=self.color_bg, fg="#666666")
        self.watermark_label.pack(side="bottom", anchor="e", fill="x", padx=25, pady=(0, 10))

        self.setup_variant_selector()

        style = ttk.Style()
        style.theme_use('default')
        style.layout("Tab", [('Notebook.tab', {'sticky': 'nswe', 'children': [('Notebook.padding', {'side': 'top', 'sticky': 'nswe', 'children': [('Notebook.label', {'side': 'top', 'sticky': ''})], })], })])
        style.configure("TNotebook", background=self.color_bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.color_panel, foreground=self.color_text, font=("맑은 고딕", 17, "bold"), padding=[35, 18], focuscolor=self.color_bg)
        style.map("TNotebook.Tab", background=[("selected", self.color_border)], foreground=[("selected", self.color_gold)])

        self.notebook = ttk.Notebook(self.root, takefocus=False)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=(15, 5))
        
        self.tab_checklist = tk.Frame(self.notebook, bg=self.color_bg)
        self.tab_recipe = tk.Frame(self.notebook, bg=self.color_bg)
        
        self.notebook.add(self.tab_checklist, text="☑ 재료 체크리스트")
        self.notebook.add(self.tab_recipe, text="📜 영약 & 비약 레시피")
        self.notebook.select(self.tab_checklist)
        self.build_tab_actions()

        # 🚨 단 한 번만 UI를 그립니다. (파괴/재생성 X)
        self.setup_checklist_top_bar()
        self.setup_checklist_grid()
        self.setup_recipe_grid()

        self.active_materials = []
        self.change_variant(self.saved_variant)
        self.notify_start()

    def setup_custom_titlebar(self):
        self.root.overrideredirect(True) 
        self.root.config(highlightbackground=self.color_border, highlightcolor=self.color_gold, highlightthickness=1)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        self.title_bar = tk.Frame(self.root, bg=self.color_titlebar, relief="flat", bd=0)
        self.title_bar.pack(fill="x", side="top")

        self.tb_icon_label = tk.Label(self.title_bar, bg=self.color_titlebar)
        self.tb_icon_label.pack(side="left", padx=(10, 5), pady=6)
        
        self.title_label = tk.Label(self.title_bar, text=f"[파티] 조화의 영약 (v{CURRENT_VERSION})", font=("맑은 고딕", 10, "bold"), bg=self.color_titlebar, fg=self.color_gold)
        self.title_label.pack(side="left", padx=5)

        self.close_btn = tk.Button(self.title_bar, text="✕", font=("Arial", 11), bg=self.color_titlebar, fg=self.color_text, bd=0, activebackground="#d32f2f", activeforeground="#ffffff", command=self.close_app)
        self.close_btn.pack(side="right", ipadx=12, ipady=4)
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(bg="#d32f2f", fg="#ffffff"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(bg=self.color_titlebar, fg=self.color_text))

        self.min_btn = tk.Button(self.title_bar, text="─", font=("Arial", 11, "bold"), bg=self.color_titlebar, fg=self.color_text, bd=0, activebackground=self.color_border, activeforeground=self.color_gold, command=self.minimize_app)
        self.min_btn.pack(side="right", ipadx=12, ipady=4)
        self.min_btn.bind("<Enter>", lambda e: self.min_btn.config(bg=self.color_border, fg=self.color_gold))
        self.min_btn.bind("<Leave>", lambda e: self.min_btn.config(bg=self.color_titlebar, fg=self.color_text))

        self.title_bar.bind("<ButtonPress-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)
        self.title_label.bind("<ButtonPress-1>", self.start_move)
        self.title_label.bind("<B1-Motion>", self.do_move)
        self.tb_icon_label.bind("<ButtonPress-1>", self.start_move)
        self.tb_icon_label.bind("<B1-Motion>", self.do_move)

        self.root.after(10, self.set_appwindow)
        self.root.bind("<Map>", self.frame_mapped)

    def start_move(self, event):
        self._click_x = event.x_root - self.root.winfo_rootx()
        self._click_y = event.y_root - self.root.winfo_rooty()

    def do_move(self, event):
        x = event.x_root - self._click_x
        y = event.y_root - self._click_y
        self.root.geometry(f"+{x}+{y}")

    def close_app(self):
        self.save_state()
        self.root.destroy()

    def minimize_app(self):
        self.root.update_idletasks()
        self.root.overrideredirect(False)
        self.root.state('iconic')

    def frame_mapped(self, event):
        if event.widget == self.root:
            if self.root.state() == 'normal':
                self.root.update_idletasks()
                self.root.overrideredirect(True)

    def set_appwindow(self):
        if os.name == 'nt':
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                style = style & ~0x00000080
                style = style | 0x00040000
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
                self.root.withdraw()
                self.root.deiconify()
            except: pass

    def setup_resizing(self):
        self.right_grip = tk.Frame(self.root, bg=self.color_bg, cursor="sb_h_double_arrow")
        self.right_grip.place(relx=1.0, rely=0.0, relheight=1.0, width=5, anchor="ne")
        self.right_grip.bind("<ButtonPress-1>", lambda e: self.start_resize(e, 'e'))
        self.right_grip.bind("<B1-Motion>", self.do_resize)

        self.bottom_grip = tk.Frame(self.root, bg=self.color_bg, cursor="sb_v_double_arrow")
        self.bottom_grip.place(relx=0.0, rely=1.0, relwidth=1.0, height=5, anchor="sw")
        self.bottom_grip.bind("<ButtonPress-1>", lambda e: self.start_resize(e, 's'))
        self.bottom_grip.bind("<B1-Motion>", self.do_resize)

        self.corner_canvas = tk.Canvas(self.root, bg=self.color_bg, width=15, height=15, highlightthickness=0, cursor="size_nw_se")
        self.corner_canvas.place(relx=1.0, rely=1.0, anchor="se")
        
        self.corner_canvas.create_line(10, 15, 15, 10, fill=self.color_gold, width=2)
        self.corner_canvas.create_line(5, 15, 15, 5, fill=self.color_gold, width=2)
        self.corner_canvas.create_line(0, 15, 15, 0, fill=self.color_gold, width=2)

        self.corner_canvas.bind("<ButtonPress-1>", lambda e: self.start_resize(e, 'se'))
        self.corner_canvas.bind("<B1-Motion>", self.do_resize)

    def start_resize(self, event, direction):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._start_width = self.root.winfo_width()
        self._start_height = self.root.winfo_height()
        self._resize_dir = direction

    def do_resize(self, event):
        dx = event.x_root - self._resize_start_x
        dy = event.y_root - self._resize_start_y
        new_width = self._start_width
        new_height = self._start_height
        if 'e' in self._resize_dir: new_width = max(1100, self._start_width + dx)
        if 's' in self._resize_dir: new_height = max(700, self._start_height + dy)
        self.root.geometry(f"{new_width}x{new_height}")

    def apply_win11_round_corners(self):
        if os.name == 'nt':
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_ROUND = 2  # 🚨 윈도우 11 기본 최대 둥글기로 복구
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(ctypes.c_int(DWMWCP_ROUND)),
                    ctypes.sizeof(ctypes.c_int)
                )
            except Exception:
                pass

    def setup_variant_selector(self):
        self.variant_selection_frame = tk.Frame(self.root, bg=self.color_bg)
        self.variant_selection_frame.pack(fill="x", padx=15, pady=(15, 0))

        variants = ["아인", "카마실비아", "인간", "에다니아"]
        self.variant_btn_frames = {}

        for var in variants:
            v_frame = tk.Frame(self.variant_selection_frame, bg=self.color_panel, bd=0, highlightthickness=2, highlightbackground=self.color_bg, cursor="hand2")
            v_frame.pack(side="left", expand=True, fill="x", padx=5)

            handler = lambda e, v_name=var: self.change_variant(v_name)
            v_frame.bind("<Button-1>", handler)

            inner_frame = tk.Frame(v_frame, bg=self.color_panel)
            inner_frame.pack(pady=10)
            inner_frame.bind("<Button-1>", handler)

            icon = self.load_icon(f"조화의 영약-{var}", size=(40, 40))
            if icon:
                lbl_icon = tk.Label(inner_frame, image=icon, bg=self.color_panel)
                lbl_icon.pack(side="left", padx=5)
                lbl_icon.bind("<Button-1>", handler)

            lbl_text = tk.Label(inner_frame, text=f"조화의 영약 - {var}", font=("맑은 고딕", 14, "bold"), fg=self.color_gold, bg=self.color_panel)
            lbl_text.pack(side="left", padx=5)
            lbl_text.bind("<Button-1>", handler)

            self.variant_btn_frames[var] = v_frame

    # 🚨 [완벽 최적화] 위젯 파괴 대신 숨김(Hide) & 표시(Show) 기능만으로 0초만에 렌더링
    def change_variant(self, variant):
        self.current_variant = variant
        new_title = f"[파티] 조화의 영약 - {variant} (v{CURRENT_VERSION})"
        if hasattr(self, 'title_label'):
            self.title_label.config(text=new_title)

        for v, frame in self.variant_btn_frames.items():
            bg_c = self.color_border if v == variant else self.color_panel
            hl_c = self.color_gold if v == variant else self.color_bg
            frame.config(bg=bg_c, highlightbackground=hl_c)
            for child in frame.winfo_children(): child.config(bg=bg_c)
            for child in frame.winfo_children()[0].winfo_children(): child.config(bg=bg_c)

        self.update_ui_for_variant(variant)
        self.update_progress()
        self.update_quantities()
        self.save_state()

    def update_ui_for_variant(self, variant):
        # 1. 탭에 맞는 재료 총량 계산
        totals = {item: 0 for cat in self.master_item_catalog.values() for item in cat}
        totals["마력이 깃든 촉매제"] = 8.58
        totals["이벨랍의 정수"] = 0.143

        def map_item_name(name):
            if name == "곰 피": return "곰 피 / 사자 피"
            if name == "늑대 피": return "늑대 피 / 코뿔소 피"
            return name

        active_recipes = {}
        for k, v in self.recipes_detailed.items(): active_recipes[k] = v
        active_recipes["기타 비약"] = self.variant_recipes[variant]

        for sub_dict in active_recipes.values():
            for ingredients in sub_dict.values():
                for ing in ingredients:
                    parts = ing.split()
                    qty = float(parts[-1])
                    name = " ".join(parts[:-1]).strip()
                    totals[map_item_name(name)] += qty

        # 2. 체크리스트 UI 업데이트 (위젯 재활용)
        self.active_materials = []
        
        # 컬럼 내부 초기화 (순서를 위해 숨기기)
        for col in self.cols:
            for slave in col.pack_slaves(): slave.pack_forget()

        for cat_name, items in self.master_item_catalog.items():
            active_items = [item for item in items if totals.get(item, 0) > 0]
            if active_items:
                col_idx = self.category_cols[cat_name]
                target_col = self.cols[col_idx]
                
                self.checklist_cat_frames[cat_name].pack(in_=target_col, fill="x", pady=(10, 0))
                
                visible_index = 0
                for item in active_items:
                    mat = self.global_materials[item]
                    mat["base_qty"] = totals[item]
                    self.active_materials.append(mat)
                    
                    val = int(mat["base_qty"]) if float(mat["base_qty"]).is_integer() else mat["base_qty"]
                    self.ui_items_dict[item]["lbl_base"].config(text=f"x{val}")
                    
                    # 줄무늬 배경색 동적 업데이트
                    bg_color = self.color_panel if visible_index % 2 == 0 else self.color_alt
                    frame = self.checklist_item_frames[item]
                    frame.config(bg=bg_color)
                    for child in frame.winfo_children():
                        if isinstance(child, tk.Label): child.config(bg=bg_color)
                    
                    frame.pack(in_=target_col, fill="x")
                    visible_index += 1

        # 3. 레시피 UI 업데이트 (기타 비약 부분만 재활용)
        active_gita = self.variant_recipes[variant].keys()
        all_gita = ["에다니아의 비약", "아인 사냥의 비약", "그리폰의 비약", "인간 사냥의 비약", "의지의 비약"]
        
        for recipe_name in all_gita:
            self.recipe_wrappers[recipe_name].pack_forget()
            
        for recipe_name in all_gita:
            if recipe_name in active_gita or recipe_name == "의지의 비약":
                self.recipe_wrappers[recipe_name].pack(fill="x", padx=2, pady=3)

    def set_app_icon(self):
        target_name = get_clean_string("mainicon") 
        icon_path = None
        if target_name in self.available_icons: icon_path = self.available_icons[target_name]
        else:
            for name in ["조화의 영약", "icon"]:
                clean_name = get_clean_string(name)
                if clean_name in self.available_icons:
                    icon_path = self.available_icons[clean_name]
                    break
        if icon_path:
            try:
                img = Image.open(icon_path).convert("RGBA")
                icon_photo = ImageTk.PhotoImage(img)
                self.root.iconphoto(False, icon_photo)
                self.app_icon = icon_photo 

                if hasattr(self, 'tb_icon_label'):
                    img_small = img.resize((20, 20), Image.BICUBIC)
                    tb_photo = ImageTk.PhotoImage(img_small)
                    self.tb_icon_label.config(image=tb_photo)
                    self.tb_icon_photo = tb_photo 
            except: pass

    def scan_icons_folder(self):
        if not os.path.exists(ICON_DIR): return
        for root_dir, dirs, files in os.walk(ICON_DIR):
            for filename in files:
                if filename.lower().endswith(('.png', '.webp', '.jpg', '.jpeg', '.gif', '.ico')):
                    name_without_ext = os.path.splitext(filename)[0]
                    clean_name = get_clean_string(name_without_ext)
                    self.available_icons[clean_name] = os.path.join(root_dir, filename)

    def preload_all_icons(self):
        all_names = set()
        for items in self.master_item_catalog.values(): all_names.update(items)
        for sub_dict in self.recipes_detailed.values():
            for sub_elixir, ingredients in sub_dict.items():
                all_names.add(sub_elixir)
                for ing in ingredients: all_names.add(" ".join(ing.split()[:-1]).strip())
        for var_dict in self.variant_recipes.values():
            for sub_elixir, ingredients in var_dict.items():
                all_names.add(sub_elixir)
                for ing in ingredients: all_names.add(" ".join(ing.split()[:-1]).strip())

        for name in all_names:
            self.load_icon(name, size=(28, 28))
            self.load_icon(name, size=(22, 22))
            self.load_icon(name, size=(40, 40))

    def load_save_data(self):
        self.saved_state = {}
        self.recipe_states = {}
        self.saved_target_count = 5000 
        self.saved_variant = "에다니아"
        
        if os.path.exists(self.save_file):
            try:
                with open(self.save_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "checklist" in data:
                        self.saved_state = data.get("checklist", {})
                        self.recipe_states = data.get("recipes", {})
                        self.saved_target_count = data.get("target_count", 5000)
                        self.saved_variant = data.get("variant", "에다니아")
                    else:
                        self.saved_state = data
            except: pass

    def save_state(self):
        for mat in getattr(self, 'active_materials', []):
            self.saved_state[mat["name"]] = mat["is_done"].get()

        state_to_save = {
            "checklist": getattr(self, 'saved_state', {}), 
            "recipes": getattr(self, 'recipe_states', {}),
            "target_count": getattr(self, 'count_var', tk.IntVar(value=5000)).get(),
            "variant": getattr(self, 'current_variant', "에다니아"),
            "notify": getattr(self, 'notify_settings', {}),
            "timer": getattr(self, 'timer_state', None)
        }
        
        if os.name == 'nt' and os.path.exists(self.save_file):
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(self.save_file, 128)
            except: pass 
                
        try:
            with open(self.save_file, 'w', encoding='utf-8') as f:
                json.dump(state_to_save, f, ensure_ascii=False, indent=4)
        except Exception: pass 

    def load_icon(self, name, size=(28, 28)):
        cache_key = name + str(size)
        if cache_key in self.icon_cache: return self.icon_cache[cache_key]

        target_clean = get_clean_string(name)
        aliases = {
            "곰피사자피": ["곰피", "사자피"], "늑대피코뿔소피": ["늑대피", "코뿔소피"],
            "특상품 태고 버섯": ["특상품태고버섯", "태고버섯"], "특상품 혹버섯": ["특상품혹버섯", "혹버섯"],
            "특상품허풍선이": ["특상품허풍선이버섯", "고급허풍선이", "허풍선이버섯"],
            "특상품 광대버섯": ["특상품광대버섯", "광대버섯"],
            "생명력회복제소형": ["생명력회복제"], "맑은액체시약": ["맑은액체시약"],
            "곰피": ["곰피사자피"], "사자피": ["곰피사자피"], "늑대피": ["늑대피코뿔소피"], "코뿔소피": ["늑대피코뿔소피"],
            "특상품 태고 버섯": ["특상품태고의버섯", "태고버섯"], "특상품 혹버섯": ["특상품혹버섯", "혹버섯"],
            "특상품풍선이버섯": ["특상품허풍선이", "허풍선이버섯"], "특상품 광대 버섯": ["특상품광대버섯", "광대버섯"],
            "마력이깃든촉매제": ["마력촉매제", "촉매제"], "카프라스나무수액": ["카프라스 나무 수액"],
            "전나무수액": ["전나무 수액"], "블랙스톤가루": ["블랙스톤 가루"],
            "그리폰의발톱": ["그리폰의 발톱"], "그리폰의비약": ["그리폰의 비약"],
            "인간사냥의비약": ["인간 사냥의 비약"], "아인사냥의비약": ["아인 사냥의 비약"]
        }
        
        search_keys = [target_clean]
        if target_clean in aliases: search_keys.extend(aliases[target_clean])
            
        found_path = None
        for key in search_keys:
            if key in self.available_icons:
                found_path = self.available_icons[key]
                break
                
        if found_path:
            try:
                img = Image.open(found_path).convert("RGBA").resize(size, Image.BICUBIC)
                tk_img = ImageTk.PhotoImage(img)
                self.icon_cache[cache_key] = tk_img 
                return tk_img
            except: pass
        return None

    def setup_checklist_top_bar(self):
        self.checklist_top_frame = tk.Frame(self.tab_checklist, pady=18, bg=self.color_panel, bd=1, relief="ridge")
        self.checklist_top_frame.pack(fill="x", padx=10, pady=8)
        
        self.toggle_btn = tk.Button(self.checklist_top_frame, text="✓ 전체 선택 / 해제", font=("맑은 고딕", 13, "bold"), 
                                    bg=self.color_btn, fg=self.color_gold, activebackground=self.color_border,
                                    activeforeground=self.color_gold, relief="flat", padx=18, pady=5, command=self.toggle_all)
        self.toggle_btn.pack(side="left", padx=25)

        self.update_btn = tk.Button(self.checklist_top_frame, text="↻ 업데이트 확인", font=("맑은 고딕", 12, "bold"), 
                                    bg="#2980b9", fg="#ffffff", activebackground="#3498db",
                                    activeforeground="#ffffff", relief="flat", padx=15, pady=5, command=self.check_for_updates_thread)
        self.update_btn.pack(side="left", padx=10)

        input_frame = tk.Frame(self.checklist_top_frame, bg=self.color_panel)
        input_frame.pack(side="left", padx=40)
        tk.Label(input_frame, text="제작 목표 (회) : ", font=("맑은 고딕", 15, "bold"), fg=self.color_text, bg=self.color_panel).pack(side="left")
        
        self.count_var = tk.IntVar(value=getattr(self, 'saved_target_count', 5000))
        self.count_entry = tk.Entry(input_frame, textvariable=self.count_var, width=9, font=("맑은 고딕", 16, "bold"), 
                                    justify="center", bg="#000000", fg=self.color_gold, insertbackground="white", bd=0)
        self.count_entry.pack(side="left")
        self.count_var.trace_add("write", lambda *args: self.update_quantities())

        progress_frame = tk.Frame(self.checklist_top_frame, bg=self.color_panel)
        progress_frame.pack(side="right", padx=35)
        self.progress_label = tk.Label(progress_frame, text="진행률: 0.0%", font=("맑은 고딕", 14, "bold"), fg=self.color_gold, bg=self.color_panel)
        self.progress_label.pack(side="top", anchor="e")
        self.progress_var = tk.DoubleVar()
        
        style = ttk.Style()
        style.configure("Horizontal.TProgressbar", background=self.color_gold, troughcolor="#222222")
        self.progress_bar = ttk.Progressbar(progress_frame, style="Horizontal.TProgressbar", variable=self.progress_var, maximum=100, length=250)
        self.progress_bar.pack(side="bottom", pady=5)

        self.checklist_grid_frame = tk.Frame(self.tab_checklist, bg=self.color_bg)
        self.checklist_grid_frame.pack(fill="both", expand=True, padx=10, pady=5)

    def setup_checklist_grid(self):
        self.cols = [tk.Frame(self.checklist_grid_frame, bg=self.color_bg) for _ in range(5)]
        for col in self.cols: col.pack(side="left", fill="both", expand=True, padx=6)

        self.checklist_cat_frames = {}
        self.checklist_item_frames = {}
        self.ui_items_dict = {}

        for cat_name, items in self.master_item_catalog.items():
            target_col = self.cols[self.category_cols[cat_name]]
            
            cat_header = tk.Frame(target_col, bg=self.color_border, pady=6)
            tk.Label(cat_header, text=f"◈ {cat_name}", font=("맑은 고딕", 13, "bold"), fg=self.color_gold, bg=self.color_border).pack(anchor="w", padx=12)
            self.checklist_cat_frames[cat_name] = cat_header

            for item in items:
                mat = self.global_materials[item]
                item_frame = tk.Frame(target_col, bg=self.color_panel, pady=4, cursor="hand2")
                
                click_handler = lambda e, m=mat: self.toggle_single_check(m)
                item_frame.bind("<Button-1>", click_handler)
                
                chk_btn = tk.Label(item_frame, text="☐", font=("맑은 고딕", 16, "bold"), bg=self.color_panel, fg="#666666", cursor="hand2")
                chk_btn.pack(side="left", padx=(5, 3))
                chk_btn.bind("<Button-1>", click_handler)
                
                icon = self.load_icon(mat["name"], size=(28, 28))
                if icon: 
                    img_lbl = tk.Label(item_frame, image=icon, bg=self.color_panel, cursor="hand2")
                    img_lbl.pack(side="left", padx=2)
                    img_lbl.bind("<Button-1>", click_handler)
                else: 
                    img_lbl = tk.Label(item_frame, text="▪", fg=self.color_checked, bg=self.color_panel, font=("Arial", 12), cursor="hand2")
                    img_lbl.pack(side="left", padx=4)
                    img_lbl.bind("<Button-1>", click_handler)

                lbl_name = tk.Label(item_frame, text=mat["name"], anchor="w", font=("맑은 고딕", 11), bg=self.color_panel, fg=self.color_text, cursor="hand2")
                lbl_name.pack(side="left", padx=(4, 0))
                lbl_name.bind("<Button-1>", click_handler)

                lbl_base = tk.Label(item_frame, text="x0", anchor="w", font=("맑은 고딕", 10), fg="#777777", bg=self.color_panel, cursor="hand2")
                lbl_base.pack(side="left", padx=(4, 0))
                lbl_base.bind("<Button-1>", click_handler)
                
                lbl_qty = tk.Label(item_frame, text="0", anchor="e", font=("맑은 고딕", 12, "bold"), bg=self.color_panel, fg=self.color_gold, cursor="hand2")
                lbl_qty.pack(side="right", padx=10)
                lbl_qty.bind("<Button-1>", click_handler)
                
                self.checklist_item_frames[item] = item_frame
                self.ui_items_dict[item] = {"mat": mat, "lbl_name": lbl_name, "lbl_qty": lbl_qty, "btn_chk": chk_btn, "lbl_base": lbl_base}

    def setup_recipe_grid(self):
        recipe_grid = tk.Frame(self.tab_recipe, bg=self.color_bg)
        recipe_grid.pack(fill="both", expand=True, padx=2, pady=(15, 10))

        self.recipe_wrappers = {}
        self.recipe_ui_items_list = []
        self.recipe_reset_funcs = []

        all_recipes_master = {
            "격노의 영약": self.recipes_detailed["격노의 영약"],
            "적응의 영약": self.recipes_detailed["적응의 영약"],
            "잠재의 영약": self.recipes_detailed["잠재의 영약"],
            "타락의 영약": self.recipes_detailed["타락의 영약"],
            "광폭의 영약": self.recipes_detailed["광폭의 영약"],
            "기타 비약": {
                "에다니아의 비약": self.variant_recipes["에다니아"]["에다니아의 비약"],
                "아인 사냥의 비약": self.variant_recipes["아인"]["아인 사냥의 비약"],
                "그리폰의 비약": self.variant_recipes["카마실비아"]["그리폰의 비약"],
                "인간 사냥의 비약": self.variant_recipes["인간"]["인간 사냥의 비약"],
                "의지의 비약": self.variant_recipes["에다니아"]["의지의 비약"],
            }
        }

        for main_elixir, sub_dict in all_recipes_master.items():
            col_frame = tk.Frame(recipe_grid, bg=self.color_panel, bd=1, relief="ridge")
            col_frame.pack(side="left", fill="both", expand=True, padx=2)
            
            title_f = tk.Frame(col_frame, bg=self.color_border, height=56)
            title_f.pack_propagate(False)
            title_f.pack(fill="x")
            
            center_f = tk.Frame(title_f, bg=self.color_border)
            center_f.place(relx=0.5, rely=0.5, anchor="center")
            
            tk.Frame(center_f, width=1, height=40, bg=self.color_border).pack(side="left")
            
            m_icon = self.load_icon(main_elixir, size=(40, 40))
            if m_icon: tk.Label(center_f, image=m_icon, bg=self.color_border).pack(side="left", padx=(0, 6))
            tk.Label(center_f, text=main_elixir, font=("맑은 고딕", 14, "bold"), fg=self.color_gold, bg=self.color_border).pack(side="left")

            container = tk.Frame(col_frame, bg=self.color_panel)
            container.pack(fill="both", expand=True)

            for sub_elixir, ingredients in sub_dict.items():
                sub_wrapper = tk.Frame(container, bg=self.color_panel, bd=0, highlightthickness=2, highlightbackground=self.color_panel, cursor="hand2")
                self.recipe_wrappers[sub_elixir] = sub_wrapper
                if main_elixir != "기타 비약": sub_wrapper.pack(fill="x", padx=2, pady=3)

                sub_f = tk.Frame(sub_wrapper, bg=self.color_panel, pady=4)
                sub_f.pack(fill="x")
                
                sub_title_f = tk.Frame(sub_f, bg=self.color_alt)
                sub_title_f.pack(fill="x")
                s_icon = self.load_icon(sub_elixir, size=(28, 28))
                
                bg_panel_widgets = [sub_wrapper, sub_f]
                bg_alt_widgets = [sub_title_f]
                title_lbls, name_lbls, qty_lbls = [], [], []
                
                icon_container = tk.Frame(sub_title_f, bg=self.color_alt, width=28, height=28)
                icon_container.pack_propagate(False)
                icon_container.pack(side="left", padx=(6, 6))
                bg_alt_widgets.append(icon_container)

                if s_icon: 
                    icon_lbl = tk.Label(icon_container, image=s_icon, bg=self.color_alt)
                    icon_lbl.pack(expand=True, fill="both")
                    bg_alt_widgets.append(icon_lbl)
                else: 
                    icon_lbl = tk.Label(icon_container, text="▶", fg=self.color_gold, bg=self.color_alt, font=("Arial", 10))
                    icon_lbl.pack(expand=True, fill="both")
                    bg_alt_widgets.append(icon_lbl)
                
                title_lbl = tk.Label(sub_title_f, text=sub_elixir, font=("맑은 고딕", 12, "bold"), fg=self.color_text, bg=self.color_alt)
                title_lbl.pack(side="left", pady=3)
                title_lbls.append(title_lbl)
                
                ing_count = 0
                for ing in ingredients:
                    ing_count += 1
                    ing_parts = ing.split()
                    ing_name = " ".join(ing_parts[:-1]).strip()
                    try: ing_base_qty = float(ing_parts[-1])
                    except: ing_base_qty = 1.0
                    
                    ing_row = tk.Frame(sub_f, bg=self.color_panel)
                    ing_row.pack(fill="x", padx=10, pady=1)
                    bg_panel_widgets.append(ing_row)
                    
                    i_icon = self.load_icon(ing_name, size=(22, 22))
                    i_icon_container = tk.Frame(ing_row, bg=self.color_panel, width=22, height=22)
                    i_icon_container.pack_propagate(False)
                    i_icon_container.pack(side="left", padx=3)
                    bg_panel_widgets.append(i_icon_container)

                    if i_icon: 
                        i_lbl = tk.Label(i_icon_container, image=i_icon, bg=self.color_panel)
                        i_lbl.pack(expand=True, fill="both")
                        bg_panel_widgets.append(i_lbl)
                    else: 
                        i_lbl = tk.Label(i_icon_container, text="·", fg="#777777", bg=self.color_panel)
                        i_lbl.pack(expand=True, fill="both")
                        bg_panel_widgets.append(i_lbl)
                    
                    ing_name_lbl = tk.Label(ing_row, text=ing_name, font=("맑은 고딕", 10), fg="#aaaaaa", bg=self.color_panel, width=14, anchor="w")
                    ing_name_lbl.pack(side="left", padx=(6, 5))
                    name_lbls.append(ing_name_lbl)
                    
                    display_qty = int(ing_base_qty) if ing_base_qty.is_integer() else ing_base_qty
                    ing_qty_lbl = tk.Label(ing_row, text=f"{display_qty}", font=("맑은 고딕", 10, "bold"), fg="#888888", bg=self.color_panel)
                    ing_qty_lbl.pack(side="right", padx=(0, 10)) 
                    qty_lbls.append(ing_qty_lbl)
                    
                    self.recipe_ui_items_list.append({"base_qty": ing_base_qty, "lbl_qty": ing_qty_lbl})

                for _ in range(5 - ing_count):
                    empty_row = tk.Frame(sub_f, bg=self.color_panel)
                    empty_row.pack(fill="x", padx=10, pady=1)
                    bg_panel_widgets.append(empty_row)
                    
                    e_icon_container = tk.Frame(empty_row, bg=self.color_panel, width=22, height=22)
                    e_icon_container.pack_propagate(False)
                    e_icon_container.pack(side="left", padx=3)
                    bg_panel_widgets.append(e_icon_container)
                    
                    dummy_name = tk.Label(empty_row, text=" ", font=("맑은 고딕", 10), bg=self.color_panel, width=14)
                    dummy_name.pack(side="left", padx=(6, 5))
                    bg_panel_widgets.append(dummy_name)

                self.bind_recipe_click(f"{main_elixir}_{sub_elixir}", sub_wrapper, bg_panel_widgets, bg_alt_widgets, title_lbls, name_lbls, qty_lbls)

            if main_elixir == "기타 비약":
                btn_frame = tk.Frame(col_frame, bg=self.color_panel)
                btn_frame.pack(side="bottom", fill="x", padx=10, pady=15) 

                reset_btn = tk.Button(btn_frame, text="↺ 레시피 전체 해제", font=("맑은 고딕", 11, "bold"), 
                                      bg=self.color_btn, fg=self.color_gold, activebackground=self.color_border,
                                      relief="flat", pady=6, command=self.reset_recipe_states)
                reset_btn.pack(fill="x")
                self.build_timer_controls(col_frame) 

    def bind_recipe_click(self, recipe_key, main_wrapper, bg_panel_widgets, bg_alt_widgets, title_lbls, name_lbls, qty_lbls):
        state = {"val": self.recipe_states.get(recipe_key, 0)} 
        def apply_state(val):
            state["val"] = val
            self.recipe_states[recipe_key] = val 
            
            if val == 0:
                border_color, panel_bg, alt_bg = self.color_panel, self.color_panel, self.color_alt
                title_fg, name_fg, qty_fg = self.color_text, "#aaaaaa", "#888888"
            elif val == 1:
                border_color, panel_bg, alt_bg = "#d4af37", "#353229", "#4a4437"
                title_fg, name_fg, qty_fg = "#ffffff", "#e0e0e0", "#ffd700"
            else:
                border_color, panel_bg, alt_bg = "#111111", "#111111", "#111111"
                title_fg, name_fg, qty_fg = "#444444", "#444444", "#444444"
            
            main_wrapper.config(highlightbackground=border_color)
            for w in bg_panel_widgets:
                try: w.config(bg=panel_bg)
                except: pass
            for w in bg_alt_widgets:
                try: w.config(bg=alt_bg)
                except: pass
            for lbl in title_lbls: lbl.config(fg=title_fg, bg=alt_bg)
            for lbl in name_lbls: lbl.config(fg=name_fg, bg=panel_bg)
            for lbl in qty_lbls: lbl.config(fg=qty_fg, bg=panel_bg)

        def toggle_state(event):
            apply_state((state["val"] + 1) % 3)
            self.save_state() 
            
        for w in [main_wrapper] + bg_panel_widgets + bg_alt_widgets + title_lbls + name_lbls + qty_lbls:
            w.bind("<Button-1>", toggle_state)
            
        self.recipe_reset_funcs.append(lambda: [apply_state(0), self.save_state()])
        apply_state(state["val"])

    def reset_recipe_states(self):
        for func in self.recipe_reset_funcs: func()

    def toggle_single_check(self, mat):
        mat["is_done"].set(not mat["is_done"].get())
        self.update_progress()
        self.save_state()

    def toggle_all(self):
        self.all_selected = not self.all_selected
        for mat in self.active_materials: mat["is_done"].set(self.all_selected)
        self.update_progress()
        self.save_state()

    def update_quantities(self, *args):
        try: target_count = self.count_var.get()
        except tk.TclError: target_count = 0
            
        for mat in getattr(self, 'active_materials', []):
            total_needed = mat["base_qty"] * target_count
            qty_str = f"{int(total_needed):,}" if float(total_needed).is_integer() else f"{total_needed:,.2f}"
            self.ui_items_dict[mat["name"]]["lbl_qty"].config(text=qty_str)
            
        for r_item in getattr(self, 'recipe_ui_items_list', []):
            total_needed = r_item["base_qty"] * target_count
            qty_str = f"{int(total_needed):,}" if float(total_needed).is_integer() else f"{total_needed:,.2f}"
            r_item["lbl_qty"].config(text=qty_str)
            
        self.save_state()

    def update_progress(self):
        total = len(self.active_materials)
        done = sum(1 for m in self.active_materials if m["is_done"].get())
        pct = (done / total) * 100 if total > 0 else 0
        
        self.progress_var.set(pct)
        self.progress_label.config(text=f"진행률: {pct:.1f}%")

        for mat in self.active_materials:
            ui = self.ui_items_dict[mat["name"]]
            if mat["is_done"].get():
                ui["btn_chk"].config(text="☑", fg=self.color_check_mark)
                ui["lbl_name"].config(fg="#888888")
                ui["lbl_qty"].config(fg="#888888")
            else:
                ui["btn_chk"].config(text="☐", fg="#666666")
                ui["lbl_name"].config(fg=self.color_text)
                ui["lbl_qty"].config(fg=self.color_gold)

if __name__ == "__main__":
    if not acquire_single_instance():   # 이미 실행 중이면 기존 창을 앞으로 가져오고 종료
        sys.exit(0)
    root = tk.Tk()
    root.title(APP_TITLE)
    app = HarmonyElixirApp(root)
    root.after(5000, lambda: app.check_for_updates_thread(silent=True))   # 시작 5초 뒤 조용히 업데이트 확인
    root.mainloop()
