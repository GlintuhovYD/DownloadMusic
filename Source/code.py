import os
import sys
import threading
import queue
import webbrowser
import re
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import yt_dlp

class DownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Music Downloader")
        self.root.geometry("620x580")
        self.root.resizable(False, False)

        self.input_file = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.tracks = []
        self.total_tracks = 0
        self.downloaded = 0
        self.failed_count = 0
        self.last_failed = ""
        self.current_track = ""
        self.stop_flag = False

        self.queue = queue.Queue()
        self.create_widgets()
        self.update_ui_from_queue()

        self.btn_folder.config(state="disabled")
        self.btn_download.config(state="disabled")
        self.btn_stop.config(state="disabled")

    def get_base_path(self):
        """Возвращает путь к папке с программой (для сохранения лога ошибок)."""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def log_failed_track(self, artist, title):
        """Записывает неудачный трек в файл failed_tracks.txt."""
        try:
            log_path = os.path.join(self.get_base_path(), "failed_tracks.txt")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{artist} - {title}\n")
        except Exception:
            pass  # не критично, если не удалось записать

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill="both", expand=True)

        # инструкция
        instr_frame = ttk.LabelFrame(main_frame, text="Инструкция", padding="5")
        instr_frame.pack(fill="x", pady=5)

        instr_text = tk.Text(instr_frame, height=8, wrap="word", font=("TkDefaultFont", 10),
                            borderwidth=0, highlightthickness=0)
        instr_text.pack(fill="x", padx=5, pady=5)

        instr_text.insert("end", "1. Переходите по ссылке ")
        instr_text.insert("end", "https://file.u-pov.ru/programs/YandexMusicExport/", ("link1",))
        instr_text.insert("end", ", если используете Я. Музыку, или ")
        instr_text.insert("end", "https://www.tunemymusic.com/ru/transfer", ("link2",))
        instr_text.insert("end", ", если любой другой.\n")
        instr_text.insert("end", "2. Укажите, с какого сервисы Вы хотите скопировать плейлист.\n")
        instr_text.insert("end", "3. Следуя указаниям, Вы должны получить txt файл с названиями всех треков из Вашего плейлиста.\n")
        instr_text.insert("end", "4. Укажите данный txt файл ниже.\n")
        instr_text.insert("end", "5. Укажите папку, в которую будут сохранены треки.\n")
        instr_text.insert("end", "6. Начните скачивание и ожидайте конца процесса.\n")

        instr_text.tag_config("link1", foreground="blue", underline=True)
        instr_text.tag_config("link2", foreground="blue", underline=True)

        def open_link1(event):
            webbrowser.open_new("https://file.u-pov.ru/programs/YandexMusicExport/")
        def open_link2(event):
            webbrowser.open_new("https://www.tunemymusic.com/ru/transfer")

        instr_text.tag_bind("link1", "<Button-1>", open_link1)
        instr_text.tag_bind("link2", "<Button-1>", open_link2)
        instr_text.config(state="disabled")

        # выбор файла
        file_frame = ttk.LabelFrame(main_frame, text="1. Файл со списком треков", padding="5")
        file_frame.pack(fill="x", pady=5)

        ttk.Label(file_frame, text="Файл:").grid(row=0, column=0, sticky="w")
        ttk.Entry(file_frame, textvariable=self.input_file, width=50).grid(row=0, column=1, padx=5)
        self.btn_file = ttk.Button(file_frame, text="Выбрать", command=self.select_file)
        self.btn_file.grid(row=0, column=2)

        # выбор папки
        folder_frame = ttk.LabelFrame(main_frame, text="2. Папка для сохранения", padding="5")
        folder_frame.pack(fill="x", pady=5)

        ttk.Label(folder_frame, text="Папка:").grid(row=0, column=0, sticky="w")
        ttk.Entry(folder_frame, textvariable=self.output_dir, width=50).grid(row=0, column=1, padx=5)
        self.btn_folder = ttk.Button(folder_frame, text="Выбрать", command=self.select_folder)
        self.btn_folder.grid(row=0, column=2)

        # кнопки старт/стоп
        action_frame = ttk.LabelFrame(main_frame, text="3. Управление", padding="5")
        action_frame.pack(fill="x", pady=5)

        self.btn_download = ttk.Button(action_frame, text="Начать скачивание", command=self.start_download)
        self.btn_download.pack(side="left", padx=5)

        self.btn_stop = ttk.Button(action_frame, text="Завершить", command=self.stop_download)
        self.btn_stop.pack(side="left", padx=5)

        # прогресс и логи
        progress_frame = ttk.LabelFrame(main_frame, text="4. Ход выполнения", padding="5")
        progress_frame.pack(fill="both", expand=True, pady=5)

        self.counter_label = ttk.Label(progress_frame, text="Скачано: 0 / 0")
        self.counter_label.pack(anchor="w")

        self.progress = ttk.Progressbar(progress_frame, orient="horizontal", length=550, mode="determinate")
        self.progress.pack(pady=5)

        log_frame = ttk.Frame(progress_frame)
        log_frame.pack(fill="both", expand=True)

        ttk.Label(log_frame, text="Не удалось скачать треков:").grid(row=0, column=0, sticky="w")
        self.failed_count_label = ttk.Label(log_frame, text="0")
        self.failed_count_label.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(log_frame, text="Последний неудачный трек:").grid(row=1, column=0, sticky="w")
        self.last_failed_label = ttk.Label(log_frame, text="", wraplength=400)
        self.last_failed_label.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(log_frame, text="Скачивается:").grid(row=2, column=0, sticky="w")
        self.current_label = ttk.Label(log_frame, text="", wraplength=400)
        self.current_label.grid(row=2, column=1, sticky="w", padx=5)

    def sanitize_filename(self, name):
        forbidden = r'[\\/*?:"<>|]'
        return re.sub(forbidden, ' ', name)

    def select_file(self):
        filename = filedialog.askopenfilename(
            title="Выберите текстовый файл со списком треков",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            self.input_file.set(filename)
            if self.parse_tracks_file(filename):
                self.btn_folder.config(state="normal")
                self.reset_progress()
            else:
                self.input_file.set("")
                self.btn_folder.config(state="disabled")
                self.btn_download.config(state="disabled")

    def parse_tracks_file(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать файл:\n{e}")
            return False

        self.tracks = []
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split(' - ', 1)
            if len(parts) != 2:
                messagebox.showwarning("Предупреждение", f"Строка {line_num} имеет неверный формат и будет пропущена:\n{line}")
                continue
            artist, title = parts
            self.tracks.append((artist.strip(), title.strip()))

        if not self.tracks:
            messagebox.showerror("Ошибка", "Файл не содержит корректных записей (формат: исполнитель - название).")
            return False

        self.total_tracks = len(self.tracks)
        self.counter_label.config(text=f"Скачано: 0 / {self.total_tracks}")
        self.progress["maximum"] = self.total_tracks
        self.progress["value"] = 0
        return True

    def select_folder(self):
        folder = filedialog.askdirectory(title="Выберите папку для сохранения музыки")
        if folder:
            self.output_dir.set(folder)
            self.btn_download.config(state="normal")

    def reset_progress(self):
        self.downloaded = 0
        self.failed_count = 0
        self.last_failed = ""
        self.current_track = ""
        self.update_counters()
        self.progress["value"] = 0
        self.stop_flag = False

    def update_counters(self):
        self.counter_label.config(text=f"Скачано: {self.downloaded} / {self.total_tracks}")
        self.failed_count_label.config(text=str(self.failed_count))
        self.last_failed_label.config(text=self.last_failed)
        self.current_label.config(text=self.current_track)
        self.progress["value"] = self.downloaded

    def start_download(self):
        if not self.tracks or not self.output_dir.get():
            messagebox.showerror("Ошибка", "Сначала выберите файл и папку.")
            return

        self.btn_file.config(state="disabled")
        self.btn_folder.config(state="disabled")
        self.btn_download.config(state="disabled")
        self.btn_stop.config(state="normal")

        self.reset_progress()
        self.stop_flag = False

        thread = threading.Thread(target=self.download_all, daemon=True)
        thread.start()

    def stop_download(self):
        self.stop_flag = True
        self.btn_stop.config(state="disabled")
        self.current_label.config(text="Останавливаемся после текущего трека...")

    def download_all(self):
        output_dir = self.output_dir.get()
        os.makedirs(output_dir, exist_ok=True)

        for idx, (artist, title) in enumerate(self.tracks, start=1):
            if self.stop_flag:
                break

            self.queue.put(("current", f"{artist} - {title}"))

            safe_artist = self.sanitize_filename(artist)
            safe_title = self.sanitize_filename(title)
            expected_mp3 = os.path.join(output_dir, f"{safe_artist} - {safe_title}.mp3")

            if os.path.exists(expected_mp3):
                self.downloaded += 1
                self.queue.put(("progress", self.downloaded, self.failed_count, self.last_failed))
                continue

            success = self.download_track(artist, title, output_dir, safe_artist, safe_title)
            if success:
                self.downloaded += 1
            else:
                self.failed_count += 1
                self.last_failed = f"{artist} - {title}"
                self.log_failed_track(artist, title)

            self.queue.put(("progress", self.downloaded, self.failed_count, self.last_failed))

        self.queue.put(("done",))

    def download_track(self, artist, title, output_dir, safe_artist, safe_title, retries=3):
        base_filename = os.path.join(output_dir, f"{safe_artist} - {safe_title}")
        query = f"{artist} {title} audio"

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': base_filename + '.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'noplaylist': True,
            'nocheckcertificate': True,
        }

        for attempt in range(1, retries + 1):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"ytsearch:{query}"])

                for fname in os.listdir(output_dir):
                    if fname.startswith(f"{safe_artist} - {safe_title}.") and not fname.endswith('.mp3'):
                        old_path = os.path.join(output_dir, fname)
                        new_path = base_filename + '.mp3'
                        if os.path.exists(new_path):
                            os.remove(new_path)
                        os.rename(old_path, new_path)
                        return True
                return False
            except Exception as e:
                if attempt < retries:
                    time.sleep(5)
                    continue
                else:
                    return False
        return False

    def update_ui_from_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                if msg[0] == "progress":
                    downloaded, failed, last_failed = msg[1], msg[2], msg[3]
                    self.downloaded = downloaded
                    self.failed_count = failed
                    self.last_failed = last_failed
                    self.update_counters()
                elif msg[0] == "current":
                    self.current_track = msg[1]
                    self.current_label.config(text=self.current_track)
                elif msg[0] == "done":
                    self.btn_file.config(state="normal")
                    self.btn_folder.config(state="normal")
                    self.btn_download.config(state="normal")
                    self.btn_stop.config(state="disabled")
                    if self.stop_flag:
                        messagebox.showinfo("Остановлено", "Скачивание прервано пользователем.")
                    else:
                        extra = ""
                        if self.failed_count > 0:
                            extra = f"\n\nНеудачные треки записаны в файл failed_tracks.txt"
                        messagebox.showinfo("Завершено", f"Скачивание завершено!{extra}")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.update_ui_from_queue)

if __name__ == "__main__":
    root = tk.Tk()
    app = DownloaderApp(root)
    root.mainloop()