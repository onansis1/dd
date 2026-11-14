"""Into the Dead: Our Darkest Days - 지도 도구 (창 + 버튼 방식, 공유용 지도 전용 배포판).
더블클릭하면 창이 열리고 [적용] / [원래대로 되돌리기] 버튼만 누르면 됩니다.
실제 작업은 apply_all.py 가 하고, 이 창은 옵션을 모아서 실행한 뒤 결과를 보여 줄 뿐입니다.
"""
import os
import re
import subprocess
import sys
import threading

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import launcher

SHOW = ("시드", "교역소", "거점", "유출구역", "어둠의 심연", "탐색 반경", "스토리", "완료", "되돌렸", "실패", "오류", "문제", "원본", "백업", "게임 파일")
FULL = not launcher.MAPONLY
OPTS = [
    ("map", "지도 건물 위치 랜덤 섞기", True),
    ("move_posts", "교역소 5곳을 지도 중앙부로 이동", False),
    ("shuffle_shelters", "거점(은신처) 위치 섞기", False),
    ("move_spillzone", "유출구역 세트(치프웨이즈) 통째 이동", False),
    ("trader_sure", "상인 방문 확률 제한 해제: 쿨다운마다 확정으로 방문 (자주 3일/기본 6일/드물게 10일)", False),
    ("bal", "총알 x5 / 가방·스테이션·시체 24칸 / 베일", False),
    ("vale_s12only", "베일 샷건만 판매 (위 항목 켠 경우)", False),
    ("leads", "탈출 퀘스트 조사 장소 3곳 -> 1곳", False),
    ("romance_all", "연애 제한 모두 해제", False),
    ("zombie", "죽은 생존자 좀비화 100%", False),
    ("quiet", "걷기/달리기 발소리 항상 없음 (아래 '발걸음 소리 무음' 옵션 줄과 같이 못 씀)", False),
    ("unarmed_crit", "맨손 무기(무술가/레슬링) 크리티컬 확률 2% -> 10%", False),
    ("hod_start", "어둠의 심연 단서 시작부터 보유", False),
    ("spillzone_start", "유출구역 단서 시작부터 보유", False),
    ("repair", "정비 작업대 레벨 제한 없이 모든 무기 수리", False),
    ("dismantle", "정비 작업대 레벨 제한 없이 모든 무기 분해", False),
    ("ammo_levels", "무기 작업대 1레벨부터 모든 총알 제작", False),
    ("random_traits", "모든 생존자 시작 특성 랜덤 (스토리 특성 고정)", False),
    ("random_skills", "모든 생존자 스킬 트리 티어별 랜덤", False),
    ("martial_h2h", "무술가/프로레슬러 특성 보유자는 4티어 맨손격투 전문가 보장", False),
    ("unarmed_sound", "맨손 처형 효과음을 모든 생존자에게 (효과음 번들 수정)", False),
    ("quiet_toggle", "게임 옵션에 '발걸음 소리 무음' 켜기/끄기 줄 추가 (접근성 맨 끝, 게임 파일 수정. 위 '발소리 항상 없음'과 같이 못 씀)", False),
    ("peek", "서서 문 엿보기 (게임 실행 파일 수정)", False),
    ("wheel_gold", "스테이션 휠: 내 생존자의 특기 작업 칸을 금색으로 (게임 실행 파일 수정)", False),
    ("shelter_move", "살았던 거점은 수색 없이 바로 이동 (게임 실행 파일 수정, 미확인)", False),
    ("random_start", "시나리오 랜덤 시작: 안 고르고 시작하면 랜덤 3명 + 새 버튼 '무술가 포함 뽑기' (게임 파일 수정)", False),
    ("panel", "지도 패널: 탐색에 유리한 내 생존자를 사진과 탭으로 표시 (게임 파일 수정)", False),
    ("lock_notes", "맵 정보 장소 설명에 락픽/볼트 절단기 개수 표시", False),
    ("june", "준(스킵의 스쿱) 방호복: 락픽 1개로 교환", False),
    ("otto", "오토 영입: 방호복 대신 락픽 1개 (관제실)", False),
]
# 화면에 묶어서 보여 줄 때의 그룹 (모든 OPTS 키가 정확히 한 번씩 들어 있어야 한다)
GROUPS = [
    ("지도 · 단서", ["map", "move_posts", "shuffle_shelters", "move_spillzone", "leads", "hod_start", "spillzone_start"]),
    ("물자 · 거래", ["bal", "vale_s12only", "ammo_levels", "june", "otto", "trader_sure"]),
    ("생존자", ["random_traits", "random_skills", "martial_h2h", "romance_all", "zombie", "quiet", "unarmed_crit"]),
    ("작업대 · 표시", ["repair", "dismantle", "lock_notes"]),
    ("게임 파일 직접 수정 (이 게임 빌드 전용)", ["peek", "wheel_gold", "shelter_move", "random_start", "panel", "unarmed_sound", "quiet_toggle"]),
]
assert sorted(k for _g, ks in GROUPS for k in ks) == sorted(k for k, _l, _d in OPTS), "GROUPS 와 OPTS 가 다릅니다"
BG = "#0c0e0b"          # 어두운 검정-이끼색
PANEL = "#151911"       # 카드 배경
EDGE = "#3b1114"        # 카드 테두리 (마른 핏빛)
FG = "#d9d4c4"          # 뼈 색 글자
MUTED = "#7f8a6b"       # 칙칙한 이끼색
ACCENT = "#b3121a"      # 피
ACCENT_HI = "#d8222c"
TOXIC = "#9ad24a"       # 독성 녹색 (강조)
FONT = "Malgun Gothic"


def _load_font():
    """같이 들어 있는 글꼴 파일(부산단디고딕M)을 이 프로그램에서만 쓰도록 불러온다. 실패하면 맑은 고딕 그대로."""
    global FONT
    path = os.path.join(launcher.HERE, "assets", "BusanDandiGothicM.ttf")
    if not os.path.exists(path):
        return
    try:
        if os.name == "nt":
            import ctypes
            if ctypes.windll.gdi32.AddFontResourceExW(path, 0x10, 0):    # FR_PRIVATE: 설치 없이 이 프로세스에서만
                FONT = "BusanDandiGothicM"
        else:
            FONT = "BusanDandiGothicM"       # 리눅스 등: 시스템에 설치돼 있으면 쓰이고, 없으면 기본 글꼴로 대체됨
    except Exception:
        pass


_load_font()


class App:
    def __init__(self, root):
        self.root = root
        root.title("Into the Dead: Our Darkest Days - 지도 도구")
        root.configure(bg=BG)
        self.W, self.H = (900, 1038) if FULL else (580, 647)
        if FULL:
            try:     # 화면보다 창이 크면 아래가 잘리므로, 화면 높이에 맞춰 줄인다 (옵션 영역은 스크롤)
                self.H = max(620, min(self.H, root.winfo_screenheight() - 96))
            except Exception:
                pass
        self.BH = 225 if FULL else 271      # 배너(게임 이미지) 높이
        if FULL and self.H < 800:
            self.BH = 150                   # 낮은 화면(예: 768): 배너 윗부분을 잘라 옵션 영역을 넓힌다
        root.geometry("%dx%d" % (self.W, self.H))
        root.resizable(False, False)
        self.opts = launcher.load_opts()
        self.busy = False
        self.var_ab = tk.StringVar(value=self.opts.get("gui_ab", "") or "")
        self.var_seed = tk.StringVar(value="")
        self.var_rmap = tk.BooleanVar(value=bool(self.opts.get("share_map", True)))        # 공유판: 선택지는 이 둘뿐
        self.var_rtrait = tk.BooleanVar(value=bool(self.opts.get("share_traits", False)))
        self.ov = {k: tk.BooleanVar(value=bool(self.opts.get(k, d))) for k, _l, d in OPTS}
        if self.ov["quiet"].get() and self.ov["quiet_toggle"].get():
            self.ov["quiet"].set(False)           # 두 옵션은 같이 쓸 수 없다 (항상 없음이 켜져 있으면 토글이 의미가 없음)
        def _excl(me, other, msg):
            def f(*_a):
                if self.ov[me].get() and self.ov[other].get():
                    self.ov[other].set(False)
                    try: self._say(msg)
                    except Exception: pass
            return f
        self.ov["quiet"].trace_add("write", _excl("quiet", "quiet_toggle", "'발소리 항상 없음'을 켜서 '발걸음 소리 무음' 옵션 줄 추가는 껐습니다 (같이 쓸 수 없음)."))
        self.ov["quiet_toggle"].trace_add("write", _excl("quiet_toggle", "quiet", "'발걸음 소리 무음' 옵션 줄 추가를 켜서 '발소리 항상 없음'은 껐습니다 (같이 쓸 수 없음)."))
        self.var_vale = tk.StringVar(value=str(self.opts.get("vale_start", 20)))
        self.var_trader = tk.StringVar(value=str(self.opts.get("trader_start", 10)))
        self.status = tk.StringVar(value="준비되었습니다.")
        self.seed_shown = tk.StringVar(value="")
        self._style()
        self._build()
        if not self.var_ab.get():
            threading.Thread(target=self._detect, daemon=True).start()

    # ------------------------------------------------------------------ 화면
    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=BG, foreground=FG, font=(FONT, 10))
        st.configure("TFrame", background=BG)
        st.configure("Card.TFrame", background=PANEL)
        st.configure("TLabel", background=BG, foreground=FG)
        st.configure("Card.TLabel", background=PANEL, foreground=FG)
        st.configure("Head.TLabel", background=PANEL, foreground=TOXIC, font=(FONT, 10, "bold"))
        st.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        st.configure("Sub.TLabel", background=BG, foreground=MUTED)
        st.configure("Seed.TLabel", background=BG, foreground=TOXIC, font=(FONT, 11, "bold"))
        st.configure("TCheckbutton", background=PANEL, foreground=FG)
        st.map("TCheckbutton", background=[("active", PANEL)], foreground=[("active", TOXIC)])
        st.configure("TEntry", fieldbackground="#0a0c08", foreground=FG, insertcolor=TOXIC, bordercolor=EDGE, lightcolor=EDGE, darkcolor=EDGE, padding=5)
        st.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)], darkcolor=[("focus", ACCENT)])
        st.configure("Go.TButton", background=ACCENT, foreground="#f4eadb", font=(FONT, 13, "bold"), padding=11, borderwidth=0, focuscolor=ACCENT)
        st.map("Go.TButton", background=[("active", ACCENT_HI), ("disabled", "#3a1013")], foreground=[("disabled", "#7a5a5c")])
        st.configure("Back.TButton", background="#232a1c", foreground=FG, font=(FONT, 11), padding=11, borderwidth=0, focuscolor="#232a1c")
        st.map("Back.TButton", background=[("active", "#323c28"), ("disabled", "#171b12")], foreground=[("disabled", "#5c6650")])
        st.configure("Small.TButton", background="#232a1c", foreground=FG, padding=5, borderwidth=0, focuscolor="#232a1c")
        st.map("Small.TButton", background=[("active", "#323c28")])
        st.configure("TCombobox", fieldbackground="#0a0c08", foreground=FG, background="#232a1c", arrowcolor=TOXIC, bordercolor=EDGE)
        st.map("TCombobox", fieldbackground=[("readonly", "#0a0c08"), ("disabled", "#0a0c08")], foreground=[("readonly", FG)],
               selectbackground=[("readonly", "#0a0c08")], selectforeground=[("readonly", FG)], background=[("active", "#323c28")])
        self.root.option_add("*TCombobox*Listbox.background", "#0a0c08")
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        st.configure("Vertical.TScrollbar", background="#2c3523", troughcolor="#0a0c08", bordercolor=EDGE, arrowcolor=TOXIC, lightcolor="#2c3523", darkcolor="#2c3523")
        st.map("Vertical.TScrollbar", background=[("active", "#3d4a30")])
        st.configure("Blood.Horizontal.TProgressbar", troughcolor="#1a0c0e", background=ACCENT, bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT)

    def _card(self, parent, title):
        border = tk.Frame(parent, bg=EDGE)
        border.pack(fill="x", pady=(0, 10))
        wrap = ttk.Frame(border, style="Card.TFrame", padding=(14, 10))
        wrap.pack(fill="x", padx=1, pady=1)
        ttk.Label(wrap, text=title, style="Head.TLabel").pack(anchor="w", pady=(0, 6))
        return wrap

    def _background(self):
        """창 전체 배경: 게임 대표 이미지(어둡게 가공한 것) + 제목 + 핏방울. 이미지가 없으면 단색."""
        import random
        W, H = self.W, self.H
        cv = tk.Canvas(self.root, width=W, height=H, bg=BG, highlightthickness=0)
        cv.pack(fill="both", expand=True)
        self._bgimg = None
        try:
            self._bgimg = tk.PhotoImage(file=os.path.join(launcher.HERE, "assets", "bg_full.png" if FULL else "bg_map.png"))
            cv.create_image(0, (self.BH - 225) if FULL else 0, image=self._bgimg, anchor="nw")
        except Exception:
            pass
        BH = self.BH
        cv.create_rectangle(0, BH - 20, W, BH - 14, fill="#7e0d13", outline="")
        cv.create_rectangle(0, BH - 20, W, BH - 18, fill="#a5121a", outline="")
        rnd = random.Random(7)
        x = 14
        while x < W:
            ln = rnd.choice((6, 10, 14, 18, 12))
            wd = rnd.choice((4, 5, 6))
            cv.create_rectangle(x, BH - 16, x + wd, BH - 14 + ln, fill="#7e0d13", outline="")
            cv.create_oval(x - 1, BH - 16 + ln, x + wd + 1, BH - 10 + ln, fill="#7e0d13", outline="")
            x += rnd.randint(26, 64)
        return cv

    def _shadow_text(self, cv, x, y, text="", fill=FG, size=10, bold=True, var=None, anchor="w"):
        f = (FONT, size, "bold" if bold else "normal")
        sh = cv.create_text(x + 1, y + 1, text=text, anchor=anchor, fill="#000000", font=f)
        tx = cv.create_text(x, y, text=text, anchor=anchor, fill=fill, font=f)
        if var is not None:
            def upd(*_a):
                cv.itemconfigure(sh, text=var.get())
                cv.itemconfigure(tx, text=var.get())
            var.trace_add("write", upd)
            upd()
        return tx

    def _build_map(self):
        """공유용(지도 전용): 이미지 위에 글자를 직접 쓰고 입력칸/버튼만 올린다."""
        cv = self._background()
        W = self.W
        Y = self.BH
        self._shadow_text(cv, 24, Y + 30, "게임 폴더 (AssetBundles)", TOXIC, 10)
        e1 = ttk.Entry(cv, textvariable=self.var_ab)
        cv.create_window(24, Y + 48, anchor="nw", window=e1, width=W - 150, height=30)
        b1 = ttk.Button(cv, text="찾아보기", style="Small.TButton", command=self._browse)
        cv.create_window(W - 112, Y + 48, anchor="nw", window=b1, width=88, height=30)
        self._shadow_text(cv, 24, Y + 104, "시드 (비우면 무작위)", TOXIC, 10)
        e2 = ttk.Entry(cv, textvariable=self.var_seed)
        cv.create_window(24, Y + 122, anchor="nw", window=e2, width=190, height=30)
        for i, (var, txt) in enumerate(((self.var_rmap, "랜덤 지도"), (self.var_rtrait, "랜덤 특성"))):
            cb = tk.Checkbutton(cv, text=txt, variable=var, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                                highlightthickness=0, bd=0, font=(FONT, 10, "bold"), anchor="w")
            cv.create_window(24 + 150 * i, Y + 162, anchor="nw", window=cb, width=140, height=26)
        self.btn_go = ttk.Button(cv, text="적용", style="Go.TButton", command=self._apply)
        cv.create_window(24, Y + 222, anchor="nw", window=self.btn_go, width=W - 220, height=48)
        self.btn_back = ttk.Button(cv, text="원래대로 되돌리기", style="Back.TButton", command=self._restore)
        cv.create_window(W - 184, Y + 222, anchor="nw", window=self.btn_back, width=160, height=48)
        self._shadow_text(cv, 24, Y + 294, "", TOXIC, 11, var=self.seed_shown)
        self._shadow_text(cv, 24, Y + 320, "", "#d9d4c4", 10, bold=False, var=self.status)
        self.prog = ttk.Progressbar(cv, mode="indeterminate", style="Blood.Horizontal.TProgressbar")
        self._prog_item = cv.create_window(24, Y + 346, anchor="nw", window=self.prog, width=W - 48, height=10, state="hidden")
        self._shadow_text(cv, W - 16, self.H - 18, "Made by 줿", "#b9b39d", 9, anchor="e")
        self._cv = cv
        self.log = None

    def _build(self):
        if not FULL:
            return self._build_map()
        cv = self._background()
        self._cv = cv
        outer = ttk.Frame(cv, padding=(14, 8))
        cv.create_window(18, self.BH + 8, anchor="nw", window=outer, width=self.W - 36, height=self.H - self.BH - 14)

        # ---- 아래쪽 고정 막대 (시드/버튼/상태/로그): 아래에서부터 쌓는다 ----
        logf = ttk.Frame(outer)
        logf.pack(side="bottom", fill="x")
        self.log = tk.Text(logf, height=3, bg="#0a0c08", fg=TOXIC, insertbackground=TOXIC, relief="flat", wrap="word", state="disabled", font=("Consolas", 10))
        sb = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="x", expand=True)
        infof = ttk.Frame(outer)
        infof.pack(side="bottom", fill="x", pady=(0, 4))
        st_lab = ttk.Label(infof, textvariable=self.status, style="Sub.TLabel")
        st_lab.pack(side="bottom", anchor="w")
        seed_lab = ttk.Label(infof, textvariable=self.seed_shown, style="Seed.TLabel")
        def _seed_vis(*_a):
            if self.seed_shown.get():
                seed_lab.pack(side="bottom", anchor="w", before=st_lab)
            else:
                seed_lab.pack_forget()
        self.seed_shown.trace_add("write", _seed_vis)
        self.progf = ttk.Frame(outer)
        self.progf.pack(side="bottom", fill="x")
        self.prog = ttk.Progressbar(self.progf, mode="indeterminate", style="Blood.Horizontal.TProgressbar", length=200)
        self.prog_pack = dict(fill="x", pady=(0, 6))
        btns = ttk.Frame(outer)
        btns.pack(side="bottom", fill="x", pady=(2, 6))
        self.btn_go = ttk.Button(btns, text="적용", style="Go.TButton", command=self._apply)
        self.btn_go.pack(side="left", fill="x", expand=True)
        self.btn_back = ttk.Button(btns, text="원래대로 되돌리기", style="Back.TButton", command=self._restore)
        self.btn_back.pack(side="left", padx=(10, 0))
        seedrow = ttk.Frame(outer)
        seedrow.pack(side="bottom", fill="x", pady=(2, 6))
        ttk.Label(seedrow, text="시드 (비우면 무작위)", style="Sub.TLabel").pack(side="left")
        ttk.Entry(seedrow, textvariable=self.var_seed, width=18).pack(side="left", padx=(10, 0))
        ttk.Button(seedrow, text="프리셋 도구 (새 창)", style="Small.TButton", command=self._preset).pack(side="left", padx=(16, 0))

        # ---- 위쪽: 스크롤되는 영역 (게임 폴더 + 항목들) ----
        area = tk.Frame(outer, bg=EDGE)
        area.pack(side="top", fill="both", expand=True, pady=(0, 6))
        holder = tk.Frame(area, bg=PANEL)
        holder.pack(fill="both", expand=True, padx=1, pady=1)
        self._sc = tk.Canvas(holder, bg=PANEL, highlightthickness=0, yscrollincrement=18)
        vs = ttk.Scrollbar(holder, orient="vertical", command=self._sc.yview)
        self._sc.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self._sc.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(self._sc, style="Card.TFrame", padding=(14, 10))
        win = self._sc.create_window(0, 0, window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: self._sc.configure(scrollregion=self._sc.bbox("all")))
        self._sc.bind("<Configure>", lambda e: self._sc.itemconfigure(win, width=e.width))

        def wheel(e):
            d = -1 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 1
            first, last = self._sc.yview()
            if (d < 0 and first <= 0.0) or (d > 0 and last >= 1.0):
                return
            self._sc.yview_scroll(d * 2, "units")
        def on_enter(_e):
            self._sc.bind_all("<MouseWheel>", wheel)
            self._sc.bind_all("<Button-4>", wheel)
            self._sc.bind_all("<Button-5>", wheel)
        def on_leave(_e):
            for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self._sc.unbind_all(ev)
        holder.bind("<Enter>", on_enter)
        holder.bind("<Leave>", on_leave)

        ttk.Label(inner, text="게임 폴더 (AssetBundles)", style="Head.TLabel").pack(anchor="w", pady=(0, 6))
        row = ttk.Frame(inner, style="Card.TFrame")
        row.pack(fill="x", pady=(0, 14))
        ttk.Entry(row, textvariable=self.var_ab).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="찾아보기", style="Small.TButton", command=self._browse).pack(side="left", padx=(8, 0))

        head = ttk.Frame(inner, style="Card.TFrame")
        head.pack(fill="x", pady=(0, 4))
        ttk.Label(head, text="적용할 항목  (탐색 반경 x1.5 는 항상 적용)", style="Head.TLabel").pack(side="left")
        ttk.Button(head, text="전체 해제", style="Small.TButton", command=lambda: self._set_all(False)).pack(side="right")
        ttk.Button(head, text="전체 선택", style="Small.TButton", command=lambda: self._set_all(True)).pack(side="right", padx=(0, 6))
        labels = {k: lab for k, lab, _d in OPTS}
        for gname, keys in GROUPS:
            ttk.Label(inner, text=gname, style="Muted.TLabel").pack(anchor="w", pady=(8, 1))
            grid = ttk.Frame(inner, style="Card.TFrame")
            grid.pack(fill="x")
            grid.columnconfigure(0, weight=1, uniform="c")
            grid.columnconfigure(1, weight=1, uniform="c")
            for i, k in enumerate(keys):
                ttk.Checkbutton(grid, text=labels[k], variable=self.ov[k], width=0).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 10))
        sub = ttk.Frame(inner, style="Card.TFrame")
        sub.pack(fill="x", pady=(12, 2))
        ttk.Label(sub, text="미스터 베일 첫 석궁/샷건 시점 (0=시작부터, 20=원래)", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Combobox(sub, textvariable=self.var_vale, values=["0", "10", "20"], width=5, state="readonly").grid(row=0, column=1, padx=8)
        ttk.Label(sub, text="상인 첫 등장 사이클 (0=시작부터, 10=원래)", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Combobox(sub, textvariable=self.var_trader, values=[str(i) for i in range(11)], width=5, state="readonly").grid(row=1, column=1, padx=8, pady=(4, 0))

    def _set_all(self, v):
        for var in self.ov.values():
            var.set(bool(v))
        if v:
            self.ov["quiet"].set(False)           # 같이 쓸 수 없는 쌍: 게임 안에서 끄고 켤 수 있는 쪽만 선택
            self.ov["quiet_toggle"].set(True)
        self._say("모든 항목을 선택했습니다." if v else "모든 항목을 해제했습니다.")

    # ------------------------------------------------------------------ 동작
    def _detect(self):
        ab = launcher.find_ab()
        if ab:
            self.root.after(0, lambda: (self.var_ab.set(ab), self._say("게임 폴더를 찾았습니다.")))
        else:
            self.root.after(0, lambda: self._say("게임 폴더를 자동으로 찾지 못했습니다. '찾아보기'로 직접 골라 주세요."))

    def _browse(self):
        p = filedialog.askdirectory(title="AssetBundles 폴더를 고르세요")
        if p:
            self.var_ab.set(os.path.normpath(p))

    def _say(self, msg):
        self.status.set(msg)

    def _log(self, text):
        if self.log is None:
            return
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip("\n") + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _valid_ab(self):
        ab = self.var_ab.get().strip().strip('"')
        if not ab or not os.path.isfile(os.path.join(ab, "data_levels")):
            messagebox.showwarning("게임 폴더", "게임 폴더(AssetBundles)를 찾을 수 없습니다.\n'찾아보기'로 ...\\StreamingAssets\\AssetBundles 폴더를 골라 주세요.")
            return None
        return ab

    def _save(self):
        self.opts.update({"gui_ab": self.var_ab.get().strip()})
        if not FULL:
            self.opts["share_map"] = self.var_rmap.get()
            self.opts["share_traits"] = self.var_rtrait.get()
        if FULL:
            for k, v in self.ov.items():
                self.opts[k] = v.get()
            self.opts["vale_start"] = int(self.var_vale.get() or 20)
            self.opts["trader_start"] = int(self.var_trader.get() or 10)
        launcher.save_opts(self.opts)

    def _set_busy(self, b):
        self.busy = b
        st = "disabled" if b else "normal"
        self.btn_go.configure(state=st)
        self.btn_back.configure(state=st)
        try:
            if b:
                self.prog.start(12)
            else:
                self.prog.stop()
            if FULL:
                self.prog.pack(**self.prog_pack) if b else self.prog.pack_forget()
            else:
                self._cv.itemconfigure(self._prog_item, state="normal" if b else "hidden")
        except Exception:
            pass

    def _apply(self):
        if self.busy:
            return
        ab = self._valid_ab()
        if not ab:
            return
        seed = self.var_seed.get().strip()
        if seed and not seed.isdigit():
            messagebox.showwarning("시드", "지도 번호는 숫자만 넣을 수 있습니다. 비워 두면 무작위입니다.")
            return
        if launcher.game_running():
            messagebox.showwarning("게임 실행 중", "게임이 실행 중입니다. 게임과 스팀을 완전히 끄고 다시 눌러 주세요.")
            return
        if not messagebox.askyesno("적용", "새 게임을 시작하기 전에만 사용하세요. 진행 중인 세이브에는 쓰지 마세요 (지도가 바뀝니다).\n\n지금 적용할까요?"):
            return
        if FULL:
            args = self._full_args()
        else:
            # 공유판: 선택지는 '랜덤 지도'/'랜덤 특성'뿐, 나머지(교역소/거점/유출구역 이동, 스테이션 휠 금색, 지도 패널, 맨손 처형 효과음)는 항상 켠다
            args = ["--only-map", "--wheel-gold", "--panel", "--unarmed-sound"]
            args += ["--move-posts", "--shuffle-shelters", "--move-spillzone"] if self.var_rmap.get() else ["--no-shuffle"]
            if self.var_rtrait.get():
                args += ["--random-traits", "--martial-h2h"]      # 랜덤 특성에는 '프로레슬러/무술가를 가진 생존자는 4티어에 맨손격투 전문가 보장'이 함께 들어간다
        if seed:
            args += ["--seed", seed]
        self._save()
        self._run(ab, args, "적용")

    def _full_args(self):
        o = {k: v.get() for k, v in self.ov.items()}
        vale, trader = int(self.var_vale.get() or 20), int(self.var_trader.get() or 10)
        a = []
        if not o["bal"]: a += ["--only-map"]
        if not o["map"]: a += ["--no-shuffle"]
        if o["leads"]: a += ["--leads", "1"]
        if trader != 10: a += ["--trader-start", str(trader)]
        if o["trader_sure"]: a += ["--trader-sure"]
        if o["unarmed_crit"]: a += ["--unarmed-crit"]
        if o["quiet_toggle"]: a += ["--quiet-toggle"]
        if o["quiet_toggle"]: o["quiet"] = False
        for k, f in (("move_posts", "--move-posts"), ("shuffle_shelters", "--shuffle-shelters"), ("move_spillzone", "--move-spillzone"),
                     ("romance_all", "--romance-all"), ("zombie", "--zombie"), ("quiet", "--quiet-steps"), ("hod_start", "--hod-start"),
                     ("spillzone_start", "--spillzone-start"), ("june", "--june-lockpick"), ("repair", "--repair-any-level"), ("dismantle", "--dismantle-any-level"), ("ammo_levels", "--ammo-all-levels"), ("random_traits", "--random-traits"), ("random_skills", "--random-skills"), ("martial_h2h", "--martial-h2h"), ("peek", "--peek-standing"), ("wheel_gold", "--wheel-gold"), ("shelter_move", "--shelter-move"), ("random_start", "--random-start"), ("panel", "--panel"), ("unarmed_sound", "--unarmed-sound"), ("otto", "--otto-lockpick"), ("lock_notes", "--lock-notes")):
            if o[k]: a.append(f)
        if o["bal"] and vale != 20: a += ["--vale-start", str(vale)]
        if o["bal"] and o["vale_s12only"]: a += ["--vale", "s12only"]
        return a

    def _preset(self):
        ab = self._valid_ab()
        if not ab:
            return
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0
        if launcher.FROZEN:
            cmd = [sys.executable, "--preset-menu", ab]
        else:
            cmd = [sys.executable, "-c", "import sys; sys.path.insert(0, %r); import preset_tool, launcher; preset_tool.menu(sys.argv[1], launcher.game_running); launcher.pause()" % launcher.HERE, ab]
        try:
            subprocess.Popen(cmd, creationflags=flags)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("프리셋 도구", "열지 못했습니다: %r" % (e,))

    def _restore(self):
        if self.busy:
            return
        ab = self._valid_ab()
        if not ab:
            return
        if launcher.game_running():
            messagebox.showwarning("게임 실행 중", "게임이 실행 중입니다. 게임과 스팀을 완전히 끄고 다시 눌러 주세요.")
            return
        if not messagebox.askyesno("되돌리기", "원본 상태로 되돌립니다. 계속할까요?"):
            return
        self._run(ab, ["--restore"], "되돌리기")

    def _run(self, ab, args, label):
        self._set_busy(True)
        self.seed_shown.set("")
        if self.log is not None:
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.configure(state="disabled")
        self._say("%s 중입니다. 1~2분 걸릴 수 있습니다..." % label)
        threading.Thread(target=self._worker, args=(ab, args, label), daemon=True).start()

    def _worker(self, ab, args, label):
        script = os.path.join(launcher.HERE, "apply_all.py")
        if launcher.FROZEN:
            cmd = [sys.executable, "--run-script", script, ab] + args
        else:
            cmd = [os.environ.get("ITD_PYTHON", sys.executable), "-X", "utf8", "-u", script, ab] + args
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        lines = []
        seed = None
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                 env=dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8"), creationflags=flags)
            for line in p.stdout:
                lines.append(line.rstrip("\n"))
                m = re.search(r"시드:\s*(\d+)", line)
                if m:
                    seed = m.group(1)
                if line.strip() and (FULL or any(k in line for k in SHOW)):
                    self.root.after(0, self._log, line)
            rc = p.wait()
        except Exception as e:  # noqa: BLE001
            rc = -1
            lines.append("실행하지 못했습니다: %r" % (e,))
        self.root.after(0, self._done, rc, label, seed, lines)

    def _done(self, rc, label, seed, lines):
        self._set_busy(False)
        if rc == 0:
            if label != "되돌리기":
                self.seed_shown.set("이번 지도 번호(시드): %s   (같은 지도를 다시 만들려면 이 숫자를 입력하세요)" % seed if seed else "")
                self._say("끝! 스팀에서 게임을 켜고 '새 게임'을 시작하세요.")
                messagebox.showinfo("완료", "적용이 끝났습니다.\n스팀에서 게임을 켜고 '새 게임'을 시작하세요.")
            else:
                self._say("원래대로 되돌렸습니다.")
                messagebox.showinfo("완료", "원래대로 되돌렸습니다.")
        else:
            self._say("문제가 생겼습니다. 아래 내용을 알려 주세요. (게임 파일은 바뀌지 않았습니다)")
            self._log("---- 오류 내용 (마지막 줄) ----")
            for l in lines[-14:]:
                self._log(l)
            tail = "" if FULL else "\n\n" + "\n".join(l[:160] for l in lines[-2:])
            messagebox.showerror("문제가 생겼습니다", "작업에 실패했습니다.\n" + ("창의 아래 내용과, " if FULL else "") + "exe 와 같은 폴더의 apply_all.log 를 알려 주세요.\n(게임 파일은 바뀌지 않았습니다)" + tail)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


def selftest():
    """창을 만들었다가 바로 닫는다 (빌드 확인용)."""
    root = tk.Tk()
    root.withdraw()
    App(root)
    root.update()
    root.destroy()
    return 0


if __name__ == "__main__":
    main()
