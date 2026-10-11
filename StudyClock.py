"""StudyClock: a small, offline desktop time tracker built with Tkinter."""

from __future__ import annotations

import sqlite3
import time
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk


APP_DIR = Path.home() / "AppData" / "Local" / "StudyClock"
DB_PATH = APP_DIR / "studyclock.db"
PALETTE = ["#5b7cfa", "#20a783", "#f19b38", "#d96783", "#8866d9", "#1598b5", "#b48735", "#6e9d50"]
BG = "#101319"
INK = "#f2f4f8"
MUTED = "#9ba5b3"
WHITE = "#191e27"
TEXT = "#f7f8fb"
GRID = "#303744"


class StudyClock(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("StudyClock")
        self.geometry("960x700")
        self.minsize(760, 600)
        self.configure(bg=BG)
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(DB_PATH)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL COLLATE NOCASE UNIQUE,
                color TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                started_at TEXT NOT NULL,
                seconds INTEGER NOT NULL CHECK(seconds > 0)
            );
            CREATE TABLE IF NOT EXISTS session_hours (
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                day TEXT NOT NULL,
                hour INTEGER NOT NULL CHECK(hour BETWEEN 0 AND 23),
                seconds INTEGER NOT NULL CHECK(seconds > 0),
                PRIMARY KEY(session_id, day, hour)
            );
        """)
        self.db.commit()
        self.running = False
        self.paused = False
        self.deadline = 0.0
        self.remaining = 0
        self.active_task_id: int | None = None
        self.session_started: datetime | None = None
        self.hourly_segments: list[tuple[datetime, int]] = []
        self.segment_started_at: datetime | None = None
        self.segment_started_mono = 0.0
        self.after_id: str | None = None
        self.page = "timer"
        self._style()
        self._build_shell()
        self.show_page("timer")
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", padding=8, fieldbackground=WHITE, background=WHITE, foreground=INK)
        style.map("TCombobox", fieldbackground=[("readonly", WHITE)], foreground=[("readonly", INK)])
        style.configure("TButton", font=("Segoe UI", 10), padding=(13, 9), borderwidth=0)
        style.map("TButton", background=[("active", "#252b36")])

    def _build_shell(self) -> None:
        top = tk.Frame(self, bg=WHITE, height=72, highlightbackground=GRID, highlightthickness=1)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="◷", bg=WHITE, fg="#536ff5", font=("Segoe UI", 23, "bold")).pack(side="left", padx=(25, 8))
        tk.Label(top, text="StudyClock", bg=WHITE, fg=INK, font=("Segoe UI", 15, "bold")).pack(side="left")
        self.nav = tk.Frame(top, bg=WHITE)
        self.nav.pack(side="right", padx=24)
        self.nav_timer = tk.Button(self.nav, text="Timer", command=lambda: self.show_page("timer"), relief="flat", bd=0, padx=15, pady=10, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.nav_dash = tk.Button(self.nav, text="Dashboard", command=lambda: self.show_page("dashboard"), relief="flat", bd=0, padx=15, pady=10, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.nav_timer.pack(side="left", padx=3)
        self.nav_dash.pack(side="left", padx=3)
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True)

    def show_page(self, page: str) -> None:
        self.page = page
        for child in self.body.winfo_children():
            child.destroy()
        for key, button in (("timer", self.nav_timer), ("dashboard", self.nav_dash)):
            button.configure(bg="#252d43" if page == key else WHITE, fg="#aab8ff" if page == key else MUTED)
        if page == "timer":
            self._timer_page()
        else:
            self._dashboard_page()

    def _panel(self, parent: tk.Widget, **kwargs) -> tk.Frame:
        frame = tk.Frame(parent, bg=WHITE, highlightbackground=GRID, highlightthickness=1, **kwargs)
        return frame

    def _title(self, parent: tk.Widget, text: str, size: int = 20) -> None:
        tk.Label(parent, text=text, bg=parent.cget("bg"), fg=INK, font=("Segoe UI", size, "bold")).pack(anchor="w")

    def _timer_page(self) -> None:
        wrap = tk.Frame(self.body, bg=BG)
        wrap.pack(fill="both", expand=True, padx=32, pady=26)
        self._title(wrap, "Your focus, one session at a time")
        tk.Label(wrap, text="Choose a task and set a timer. Your completed time is saved on this device.", bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 19))
        card = self._panel(wrap)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=WHITE)
        inner.pack(fill="x", padx=24, pady=22)
        tk.Label(inner, text="TASK", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(inner, text="SESSION LENGTH", bg=WHITE, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=(18, 0))
        taskline = tk.Frame(inner, bg=WHITE)
        taskline.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        self.task_combo = ttk.Combobox(taskline, state="readonly", width=30, font=("Segoe UI", 11))
        self.task_combo.pack(side="left", fill="x", expand=True)
        tk.Button(taskline, text="＋ Add task", command=self._add_task_dialog, bg="#252d43", fg="#aab8ff", relief="flat", bd=0, padx=13, pady=10, font=("Segoe UI", 10, "bold"), cursor="hand2").pack(side="left", padx=(9, 0))
        durationline = tk.Frame(inner, bg=WHITE)
        durationline.grid(row=1, column=1, sticky="w", padx=(18, 0), pady=(7, 0))
        self.duration_var = tk.StringVar(value="25 min")
        self.duration_combo = ttk.Combobox(durationline, textvariable=self.duration_var, state="readonly", values=["25 min", "30 min", "45 min", "1 hr", "2 hr", "Custom…"], width=12, font=("Segoe UI", 11))
        self.duration_combo.pack(side="left")
        self.duration_combo.bind("<<ComboboxSelected>>", self._duration_selected)
        self.duration_custom: int | None = None
        inner.columnconfigure(0, weight=1)

        timer = self._panel(wrap)
        timer.pack(fill="both", expand=True, pady=(16, 0))
        self.timer_label = tk.Label(timer, text="25:00", bg=WHITE, fg=INK, font=("Segoe UI Light", 76))
        self.timer_label.pack(pady=(28, 0))
        self.status_label = tk.Label(timer, text="Ready when you are", bg=WHITE, fg=MUTED, font=("Segoe UI", 10))
        self.status_label.pack(pady=(0, 22))
        controls = tk.Frame(timer, bg=WHITE)
        controls.pack()
        self.start_button = tk.Button(controls, text="Start focus", command=self._start, bg="#536ff5", fg=TEXT, activebackground="#405ce2", activeforeground=TEXT, relief="flat", bd=0, padx=25, pady=12, font=("Segoe UI", 11, "bold"), cursor="hand2")
        self.start_button.pack(side="left", padx=5)
        self.pause_button = tk.Button(controls, text="Pause", command=self._pause, bg="#252b36", fg=INK, relief="flat", bd=0, padx=22, pady=12, font=("Segoe UI", 10, "bold"), cursor="hand2", state="disabled")
        self.pause_button.pack(side="left", padx=5)
        self.stop_button = tk.Button(controls, text="Finish early", command=self._stop, bg="#252b36", fg=INK, relief="flat", bd=0, padx=22, pady=12, font=("Segoe UI", 10, "bold"), cursor="hand2", state="disabled")
        self.stop_button.pack(side="left", padx=5)
        self._refresh_tasks()

    def _duration_selected(self, _event=None) -> None:
        if self.duration_var.get() == "Custom…":
            popup = tk.Toplevel(self)
            popup.title("Custom timer")
            popup.configure(bg=BG)
            popup.resizable(False, False)
            popup.transient(self)
            popup.grab_set()
            tk.Label(popup, text="Set minutes", bg=BG, fg=INK, font=("Segoe UI", 12, "bold")).pack(padx=24, pady=(20, 8))
            value = tk.StringVar(value="40")
            entry = tk.Entry(popup, textvariable=value, width=10, font=("Segoe UI", 12), justify="center", relief="solid", bd=1, bg=WHITE, fg=INK, insertbackground=INK)
            entry.pack(padx=24, pady=8)
            def save():
                try:
                    n = int(value.get())
                    if not 1 <= n <= 600:
                        raise ValueError
                except ValueError:
                    messagebox.showerror("Invalid length", "Enter a whole number from 1 to 600 minutes.", parent=popup)
                    return
                self.duration_custom = n
                self.duration_var.set(f"{n} min (custom)")
                popup.destroy()
            tk.Button(popup, text="Use timer", command=save, bg="#536ff5", fg=TEXT, relief="flat", padx=15, pady=8).pack(pady=(6, 18))
            entry.focus_set()

    def _refresh_tasks(self) -> None:
        rows = self.db.execute("SELECT id, title, color FROM tasks ORDER BY title COLLATE NOCASE").fetchall()
        self.task_rows = rows
        if not hasattr(self, "task_combo"):
            return
        self.task_combo["values"] = [row[1] for row in rows]
        if rows and self.task_combo.get() not in [row[1] for row in rows]:
            self.task_combo.current(0)
        if not rows:
            self.task_combo.set("")

    def _add_task_dialog(self) -> None:
        popup = tk.Toplevel(self)
        popup.title("Add a task")
        popup.configure(bg=BG)
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()
        tk.Label(popup, text="What are you focusing on?", bg=BG, fg=INK, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=24, pady=(20, 7))
        name = tk.StringVar()
        entry = tk.Entry(popup, textvariable=name, width=31, font=("Segoe UI", 11), relief="solid", bd=1, bg=WHITE, fg=INK, insertbackground=INK)
        entry.pack(padx=24, pady=6, ipady=7)
        def save():
            title = name.get().strip()
            if not title or len(title) > 60:
                messagebox.showerror("Task name", "Enter a task name (up to 60 characters).", parent=popup)
                return
            try:
                count = self.db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
                color = PALETTE[count % len(PALETTE)]
                cur = self.db.execute("INSERT INTO tasks(title,color) VALUES(?,?)", (title, color))
                self.db.commit()
                self._refresh_tasks()
                self.task_combo.current(next(i for i, row in enumerate(self.task_rows) if row[0] == cur.lastrowid))
                popup.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Task already exists", "Choose a different task name.", parent=popup)
        tk.Button(popup, text="Add task", command=save, bg="#536ff5", fg=TEXT, relief="flat", padx=16, pady=8, font=("Segoe UI", 10, "bold")).pack(pady=(10, 20))
        entry.focus_set()
        entry.bind("<Return>", lambda _e: save())

    def _selected_duration(self) -> int:
        if self.duration_custom and "custom" in self.duration_var.get():
            return self.duration_custom * 60
        text = self.duration_var.get()
        if text == "1 hr":
            return 3600
        if text == "2 hr":
            return 7200
        return int(text.split()[0]) * 60

    def _start(self) -> None:
        if self.running:
            return
        if not self.task_rows:
            messagebox.showinfo("Add a task first", "Add a task so your study time has somewhere to go.", parent=self)
            return
        title = self.task_combo.get()
        row = next((r for r in self.task_rows if r[1] == title), None)
        if not row:
            return
        self.active_task_id = row[0]
        self.session_started = datetime.now()
        self.hourly_segments = []
        self._begin_segment()
        self.remaining = self._selected_duration()
        self.deadline = time.monotonic() + self.remaining
        self.running = True
        self.paused = False
        self.start_button.configure(text="In focus", state="disabled")
        self.pause_button.configure(state="normal", text="Pause")
        self.stop_button.configure(state="normal")
        self.task_combo.configure(state="disabled")
        self.duration_combo.configure(state="disabled")
        self.status_label.configure(text=f"Focusing on {title}")
        self._tick()

    def _tick(self) -> None:
        if not self.running or self.paused:
            return
        self.remaining = max(0, int(self.deadline - time.monotonic() + 0.999))
        self.timer_label.configure(text=f"{self.remaining // 60:02d}:{self.remaining % 60:02d}")
        if self.remaining <= 0:
            self._finish_session(completed=True)
        else:
            self.after_id = self.after(250, self._tick)

    def _pause(self) -> None:
        if not self.running:
            return
        if self.paused:
            self._begin_segment()
            self.deadline = time.monotonic() + self.remaining
            self.paused = False
            self.pause_button.configure(text="Pause")
            self.status_label.configure(text=f"Focusing on {self.task_combo.get()}")
            self._tick()
        else:
            self.remaining = max(0, int(self.deadline - time.monotonic() + 0.999))
            self._record_segment()
            self.paused = True
            if self.after_id:
                self.after_cancel(self.after_id)
            self.pause_button.configure(text="Resume")
            self.status_label.configure(text="Paused")
            self.timer_label.configure(text=f"{self.remaining // 60:02d}:{self.remaining % 60:02d}")

    def _stop(self) -> None:
        if self.running:
            self._finish_session(completed=False)

    def _begin_segment(self) -> None:
        self.segment_started_at = datetime.now()
        self.segment_started_mono = time.monotonic()

    def _record_segment(self) -> None:
        if self.segment_started_at is None:
            return
        seconds = max(0, int(time.monotonic() - self.segment_started_mono))
        if seconds:
            self.hourly_segments.append((self.segment_started_at, seconds))
        self.segment_started_at = None

    def _save_hourly_segments(self, session_id: int) -> None:
        buckets: dict[tuple[str, int], int] = {}
        for started, seconds in self.hourly_segments:
            cursor = started
            remaining = seconds
            while remaining:
                boundary = cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                part = min(remaining, max(1, int((boundary - cursor).total_seconds())))
                key = (cursor.date().isoformat(), cursor.hour)
                buckets[key] = buckets.get(key, 0) + part
                cursor += timedelta(seconds=part)
                remaining -= part
        self.db.executemany(
            "INSERT INTO session_hours(session_id,day,hour,seconds) VALUES(?,?,?,?)",
            [(session_id, day, hour, seconds) for (day, hour), seconds in buckets.items() if seconds > 0],
        )

    def _finish_session(self, completed: bool) -> None:
        if not self.paused:
            self._record_segment()
        elapsed = sum(seconds for _, seconds in self.hourly_segments)
        if elapsed > 0 and self.active_task_id:
            cur = self.db.execute("INSERT INTO sessions(task_id,started_at,seconds) VALUES(?,?,?)", (self.active_task_id, (self.session_started or datetime.now()).isoformat(timespec="seconds"), elapsed))
            self._save_hourly_segments(cur.lastrowid)
            self.db.commit()
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.running = self.paused = False
        self.active_task_id = None
        self.session_started = None
        self.segment_started_at = None
        self.hourly_segments = []
        self.start_button.configure(text="Start focus", state="normal")
        self.pause_button.configure(state="disabled", text="Pause")
        self.stop_button.configure(state="disabled")
        self.task_combo.configure(state="readonly")
        self.duration_combo.configure(state="readonly")
        if completed:
            self.timer_label.configure(text="00:00")
            self.status_label.configure(text=f"Session complete · {self._format_duration(elapsed)} saved")
            self.bell()
        else:
            self.timer_label.configure(text=self._duration_display())
            self.status_label.configure(text=f"Session saved · {self._format_duration(elapsed)}")

    def _duration_display(self) -> str:
        sec = self._selected_duration()
        return f"{sec // 60:02d}:{sec % 60:02d}"

    @staticmethod
    def _format_duration(seconds: int) -> str:
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} min"
        hours, mins = divmod(minutes, 60)
        return f"{hours} hr" + (f" {mins} min" if mins else "")

    def _dashboard_page(self) -> None:
        wrap = tk.Frame(self.body, bg=BG)
        wrap.pack(fill="both", expand=True, padx=32, pady=26)
        header = tk.Frame(wrap, bg=BG)
        header.pack(fill="x")
        self.dashboard_title = tk.Label(header, text="Focus by hour — today", bg=BG, fg=INK, font=("Segoe UI", 20, "bold"))
        self.dashboard_title.pack(side="left")
        self.period_var = tk.StringVar(value="Daily")
        period = ttk.Combobox(header, textvariable=self.period_var, state="readonly", values=["Daily", "Weekly", "Monthly"], width=12, font=("Segoe UI", 10))
        period.pack(side="right")
        period.bind("<<ComboboxSelected>>", self._period_changed)
        tk.Label(header, text="VIEW", bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(side="right", padx=(0, 9))
        self.summary_var = tk.StringVar(value="")
        tk.Label(wrap, textvariable=self.summary_var, bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 16))
        chartcard = self._panel(wrap)
        chartcard.pack(fill="both", expand=True)
        self.chart = tk.Canvas(chartcard, bg=WHITE, highlightthickness=0, height=380)
        self.chart.pack(fill="both", expand=True, padx=18, pady=(18, 2))
        self.legend = tk.Frame(chartcard, bg=WHITE)
        self.legend.pack(fill="x", padx=24, pady=(8, 18))
        self.chart.bind("<Configure>", lambda _e: self._draw_chart())
        self._draw_chart()

    def _period_changed(self, _event=None) -> None:
        title = {"Daily": "Focus by hour — today", "Weekly": "Focus by day — this week", "Monthly": "Focus by month — last 6 months"}
        self.dashboard_title.configure(text=title[self.period_var.get()])
        self._draw_chart()

    def _periods(self):
        today = date.today()
        mode = self.period_var.get()
        if mode == "Daily":
            return [(hour, "12am" if hour == 0 else (f"{hour}am" if hour < 12 else ("12pm" if hour == 12 else f"{hour - 12}pm"))) for hour in range(24)]
        if mode == "Weekly":
            start = today - timedelta(days=today.weekday())
            return [(start + timedelta(days=i), (start + timedelta(days=i)).strftime("%a")) for i in range(7)]
        first_this_month = today.replace(day=1)
        months = []
        for ago in reversed(range(6)):
            y, m = first_this_month.year, first_this_month.month - ago
            while m <= 0:
                y -= 1
                m += 12
            months.append((date(y, m, 1), date(y, m, 1).strftime("%b")))
        return months

    def _draw_chart(self) -> None:
        if not hasattr(self, "chart") or not self.chart.winfo_exists():
            return
        canvas = self.chart
        canvas.delete("all")
        for child in self.legend.winfo_children():
            child.destroy()
        periods = self._periods()
        tasks = self.db.execute("SELECT id,title,color FROM tasks ORDER BY title COLLATE NOCASE").fetchall()
        values = {row[0]: [0] * len(periods) for row in tasks}
        rows = self.db.execute("SELECT id,task_id,started_at,seconds FROM sessions").fetchall()
        total = 0
        mode = self.period_var.get()
        for session_id, task_id, stamp, seconds in rows:
            try:
                started = datetime.fromisoformat(stamp)
            except ValueError:
                continue
            if task_id not in values:
                continue
            if mode in ("Daily", "Weekly"):
                hourly = self.db.execute("SELECT day,hour,seconds FROM session_hours WHERE session_id=?", (session_id,)).fetchall()
                # Older sessions have no hour detail; keep them at their start time.
                if not hourly:
                    hourly = [(started.date().isoformat(), started.hour, seconds)]
                for day_text, hour, amount in hourly:
                    d = date.fromisoformat(day_text)
                    if mode == "Daily" and d == date.today():
                        values[task_id][hour] += amount
                        total += amount
                    elif mode == "Weekly":
                        for i, (period_day, _label) in enumerate(periods):
                            if d == period_day:
                                values[task_id][i] += amount
                                total += amount
                                break
            else:
                d = started.date()
                for i, (period_start, _label) in enumerate(periods):
                    if d.year == period_start.year and d.month == period_start.month:
                        values[task_id][i] += seconds
                        total += seconds
                        break
        self.summary_var.set(f"{self._format_duration(total)} tracked in this view")
        width, height = max(canvas.winfo_width(), 300), max(canvas.winfo_height(), 250)
        left, right, top, bottom = 54, 18, 20, 47
        plot_h = height - top - bottom
        plot_w = width - left - right
        n = len(periods)
        observed_max = max((sum(values[t[0]][i] for t in tasks) for i in range(n)), default=0)
        if mode == "Daily":
            maxval = 60 * 60  # 60 minutes per clock hour
        elif mode == "Weekly":
            maxval = 24 * 60 * 60  # at most 24 focus hours in one day
        else:
            maxval = 31 * 24 * 60 * 60  # longest calendar month
        ticks = 4
        for j in range(ticks + 1):
            y = top + plot_h - plot_h * j / ticks
            canvas.create_line(left, y, width - right, y, fill=GRID)
            amount = maxval * j / ticks
            axis_label = f"{int(amount // 60)}m" if mode == "Daily" else f"{amount / 3600:g}h"
            canvas.create_text(left - 9, y, text=axis_label, fill=MUTED, font=("Segoe UI", 8), anchor="e")
        for i, (d, label) in enumerate(periods):
            xcenter = left + plot_w * (i + .5) / n
            stack = 0
            for task in tasks:
                val = values[task[0]][i]
                if val <= 0:
                    continue
            val = min(val, max(0, maxval - stack))
                if val <= 0:
                    continue
                bar_h = plot_h * val / maxval
                x1, x2 = xcenter - min(23, plot_w / n * .32), xcenter + min(23, plot_w / n * .32)
                y2 = top + plot_h - plot_h * stack / maxval
                y1 = y2 - bar_h
                canvas.create_rectangle(x1, y1, x2, y2, fill=task[2], outline="")
                stack += val
            canvas.create_text(xcenter, top + plot_h + 20, text=label, fill=MUTED, font=("Segoe UI", 7 if mode == "Daily" else 9))
        if not tasks:
            canvas.create_text(width / 2, height / 2, text="Add a task and start a session to see your time here.", fill=MUTED, font=("Segoe UI", 11))
        elif total == 0:
            canvas.create_text(width / 2, top + plot_h / 2, text="No tracked time in this view yet", fill=MUTED, font=("Segoe UI", 11))
        for task in tasks:
            item = tk.Frame(self.legend, bg=WHITE)
            item.pack(side="left", padx=(0, 19), pady=4)
            tk.Label(item, text="●", bg=WHITE, fg=task[2], font=("Segoe UI", 11)).pack(side="left")
            tk.Label(item, text=task[1], bg=WHITE, fg=INK, font=("Segoe UI", 9)).pack(side="left", padx=(5, 0))

    def _close(self) -> None:
        if self.running:
            if not messagebox.askyesno("Timer is running", "Close the app? The current session will not be saved.", parent=self):
                return
            if self.after_id:
                self.after_cancel(self.after_id)
        self.db.close()
        self.destroy()


if __name__ == "__main__":
    StudyClock().mainloop()
