"""Into the Dead: Our Darkest Days - 지도 도구 (창 + 버튼 방식, 공유용 지도 전용 배포판).
더블클릭하면 창이 열리고 [새 지도 적용] / [원래대로 되돌리기] 버튼만 누르면 됩니다.
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
BG = "#14181f"
PANEL = "#1c222c"
FG = "#e8ecf5"
MUTED = "#8a94ab"
ACCENT = "#ff7a45"


class App:
    def __init__(self, root):
        self.root = root
        root.title("Into the Dead: Our Darkest Days - 지도 도구")
        root.configure(bg=BG)
        root.geometry("700x700")
        root.minsize(620, 640)
        self.opts = launcher.load_opts()
        self.busy = False
        self.var_ab = tk.StringVar(value=self.opts.get("gui_ab", "") or "")
        self.var_seed = tk.StringVar(value="")
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
        st.configure(".", background=BG, foreground=FG)
        st.configure("TFrame", background=BG)
        st.configure("Card.TFrame", background=PANEL)
        st.configure("TLabel", background=BG, foreground=FG)
        st.configure("Card.TLabel", background=PANEL, foreground=FG)
        st.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        st.configure("Title.TLabel", background=BG, foreground=FG, font=("Segoe UI", 17, "bold"))
        st.configure("Sub.TLabel", background=BG, foreground=MUTED)
        st.configure("Warn.TLabel", background=BG, foreground="#ffcf6b")
        st.configure("TCheckbutton", background=PANEL, foreground=FG)
        st.map("TCheckbutton", background=[("active", PANEL)])
        st.configure("Go.TButton", background=ACCENT, foreground="#1a1006", font=("Segoe UI", 12, "bold"), padding=10, borderwidth=0)
        st.map("Go.TButton", background=[("active", "#ff9468"), ("disabled", "#5a4a42")])
        st.configure("Back.TButton", background="#2a3242", foreground=FG, font=("Segoe UI", 11), padding=10, borderwidth=0)
        st.map("Back.TButton", background=[("active", "#3a4560"), ("disabled", "#232a37")])
        st.configure("Small.TButton", background="#2a3242", foreground=FG, padding=4, borderwidth=0)
        st.map("Small.TButton", background=[("active", "#3a4560")])

    def _card(self, parent, title):
        wrap = ttk.Frame(parent, style="Card.TFrame", padding=(14, 10))
        wrap.pack(fill="x", pady=(0, 10))
        ttk.Label(wrap, text=title, style="Card.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))
        return wrap

    def _build(self):
        outer = ttk.Frame(self.root, padding=(18, 14))
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="지도 도구", style="Title.TLabel").pack(anchor="w")
        ttk.Frame(outer, height=8).pack()

        c1 = self._card(outer, "게임 폴더 (AssetBundles)")
        row = ttk.Frame(c1, style="Card.TFrame")
        row.pack(fill="x")
        ent = ttk.Entry(row, textvariable=self.var_ab)
        ent.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="찾아보기", style="Small.TButton", command=self._browse).pack(side="left", padx=(8, 0))

        c3 = self._card(outer, "시드 (비우면 무작위)")
        row3 = ttk.Frame(c3, style="Card.TFrame")
        row3.pack(fill="x")
        ttk.Entry(row3, textvariable=self.var_seed, width=18).pack(side="left")

        btns = ttk.Frame(outer)
        btns.pack(fill="x", pady=(2, 8))
        self.btn_go = ttk.Button(btns, text="새 지도 적용", style="Go.TButton", command=self._apply)
        self.btn_go.pack(side="left", fill="x", expand=True)
        self.btn_back = ttk.Button(btns, text="원래대로 되돌리기", style="Back.TButton", command=self._restore)
        self.btn_back.pack(side="left", padx=(10, 0))

        ttk.Label(outer, textvariable=self.seed_shown, foreground=ACCENT, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(outer, textvariable=self.status, style="Sub.TLabel").pack(anchor="w", pady=(0, 6))
        logf = ttk.Frame(outer)
        logf.pack(fill="both", expand=True)
        self.log = tk.Text(logf, height=8, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", wrap="word", state="disabled", font=("Consolas", 10))
        sb = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

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
        launcher.save_opts(self.opts)

    def _set_busy(self, b):
        self.busy = b
        st = "disabled" if b else "normal"
        self.btn_go.configure(state=st)
        self.btn_back.configure(state=st)

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
        if not messagebox.askyesno("적용", "새 게임을 시작하기 전에만 사용하세요. 진행 중인 세이브에는 쓰지 마세요 (지도가 바뀝니다).\n\n지금 새 지도를 적용할까요?"):
            return
        args = ["--only-map"]
        if seed:
            args += ["--seed", seed]
        args += ["--move-posts", "--shuffle-shelters", "--move-spillzone"]
        self._save()
        self._run(ab, args, "적용")

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
                if line.strip() and any(k in line for k in SHOW):
                    self.root.after(0, self._log, line)
            rc = p.wait()
        except Exception as e:  # noqa: BLE001
            rc = -1
            lines.append("실행하지 못했습니다: %r" % (e,))
        self.root.after(0, self._done, rc, label, seed, lines)

    def _done(self, rc, label, seed, lines):
        self._set_busy(False)
        if rc == 0:
            if label == "적용":
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
            messagebox.showerror("문제가 생겼습니다", "작업에 실패했습니다.\n창의 아래 내용과, exe 와 같은 폴더의 apply_all.log 를 알려 주세요.\n(게임 파일은 바뀌지 않았습니다)")


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
