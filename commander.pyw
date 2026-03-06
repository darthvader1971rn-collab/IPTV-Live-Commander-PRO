import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json, threading, requests, gzip, os, re, subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
from database import DVRDatabase
from engine import RecordingEngine
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

class IPTVCommanderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IPTV Live Commander PRO")
        
        self.db = DVRDatabase()
        self.engine = RecordingEngine(logger_callback=self.add_log, finish_callback=self.on_recording_finished)
        self.load_settings()
        
        saved_geometry = self.settings.get("ui", {}).get("geometry", "1450x1000")
        self.root.geometry(saved_geometry)
        
        self.apply_theme_and_font()
        self.setup_ui()
        
        self.root.protocol('WM_DELETE_WINDOW', self.hide_window)
        self.setup_tray()

        threading.Thread(target=self.main_scheduler_loop, daemon=True).start()
        self.refresh_channel_list(); self.refresh_queue_view()

    def on_recording_finished(self, t_id, status):
        self.db.update_timer_status(t_id, status)
        self.root.after(0, self.refresh_queue_view)

    def setup_tray(self):
        img = Image.new('RGB', (64, 64), (26, 26, 26))
        ImageDraw.Draw(img).ellipse([10, 10, 54, 54], fill=(255, 204, 0))
        menu = pystray.Menu(item('Pokaż', self.show_window), item('Wyjdź', self.quit_app))
        self.tray = pystray.Icon("iptv_dvr", img, "IPTV DVR", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def hide_window(self): self.root.withdraw()
    def show_window(self): self.root.after(0, self.root.deiconify)
    def quit_app(self):
        self.save_settings() 
        if messagebox.askyesno("Wyjście", "Zamknąć system DVR?"):
            self.tray.stop(); self.root.destroy(); os._exit(0)

    def browse_file(self, entry_widget, file_types):
        filename = filedialog.askopenfilename(filetypes=file_types)
        if filename: entry_widget.delete(0, tk.END); entry_widget.insert(0, filename)

    def browse_dir(self, entry_widget):
        dirname = filedialog.askdirectory()
        if dirname: entry_widget.delete(0, tk.END); entry_widget.insert(0, dirname)

    def load_settings(self):
        if os.path.exists("settings.json"):
            with open("settings.json", "r", encoding="utf-8") as f: self.settings = json.load(f)
            if "audio_track" not in self.settings.get("recording", {}): self.settings["recording"]["audio_track"] = "Wszystkie"
            if "ui" not in self.settings: self.settings["ui"] = {"font_size": 10, "geometry": "1450x1000"}
            if "pre_padding_min" not in self.settings["recording"]: self.settings["recording"]["pre_padding_min"] = 2
            if "post_padding_min" not in self.settings["recording"]: self.settings["recording"]["post_padding_min"] = 5
            if "overlap_s" not in self.settings["recording"]: self.settings["recording"]["overlap_s"] = 0
            if "archive_night_only" not in self.settings["recording"]: self.settings["recording"]["archive_night_only"] = True
            if "m3u_arch" not in self.settings: self.settings["m3u_arch"] = {"source": ""}
        else:
            self.settings = {"m3u": {"source": ""}, "m3u_arch": {"source": ""}, "epg": {"source": ""}, "recording": {"save_path": "Nagrania", "pre_padding_min": 2, "post_padding_min": 5, "overlap_s": 0, "audio_track": "Wszystkie", "archive_night_only": True}, "ui": {"font_size": 10, "geometry": "1450x1000"}}

        if "channel_audio_defaults" not in self.settings:
            self.settings["channel_audio_defaults"] = {"Kccc": {}, "OtoPay": {}}
        if "Kccc" not in self.settings["channel_audio_defaults"]:
            self.settings["channel_audio_defaults"]["Kccc"] = self.settings["channel_audio_defaults"].pop("Live", {})
        if "OtoPay" not in self.settings["channel_audio_defaults"]:
            self.settings["channel_audio_defaults"]["OtoPay"] = self.settings["channel_audio_defaults"].pop("Archiwum", {})

    def save_settings(self):
        self.settings["m3u"]["source"] = self.ent_m3u.get()
        self.settings["m3u_arch"]["source"] = self.ent_m3u_arch.get()
        self.settings["epg"]["source"] = self.ent_epg.get()
        self.settings["recording"]["save_path"] = self.ent_save.get()
        self.settings["recording"]["audio_track"] = self.combo_audio.get()
        if hasattr(self, 'combo_font'): self.settings["ui"]["font_size"] = int(self.combo_font.get())
        self.settings["ui"]["geometry"] = self.root.geometry() 
        if hasattr(self, 'chk_night_var'): self.settings["recording"]["archive_night_only"] = self.chk_night_var.get()
        try:
            self.settings["recording"]["pre_padding_min"] = int(self.spin_pre.get())
            self.settings["recording"]["post_padding_min"] = int(self.spin_post.get())
            self.settings["recording"]["overlap_s"] = int(self.spin_overlap.get())
        except ValueError: pass
        with open("settings.json", "w", encoding="utf-8") as f: json.dump(self.settings, f, indent=4)
        self.apply_theme_and_font()

    def apply_theme_and_font(self):
        f_size = self.settings["ui"].get("font_size", 10)
        style = ttk.Style()
        
        if "clam" in style.theme_names():
            style.theme_use("clam")
            
        style.configure("Treeview", font=('Arial', f_size), rowheight=f_size*2+5, 
                        background="#ffffff", fieldbackground="#ffffff", bordercolor="#d3d3d3")
        style.configure("Treeview.Heading", font=('Arial', f_size, 'bold'), 
                        background="#e0e0e0", bordercolor="#d3d3d3")
        
        my_font = ('Arial', f_size)
        if hasattr(self, 'txt_desc'):
            self.txt_desc.configure(font=my_font)
            self.ent_m3u.configure(font=my_font)
            self.ent_m3u_arch.configure(font=my_font)
            self.ent_epg.configure(font=my_font)
            self.ent_save.configure(font=my_font)
            self.ent_s.configure(font=my_font)

    def clean_channel_name(self, name):
        name = re.sub(r'^[A-Za-z]{2,3}[:|]\s*', '', name)
        name = re.sub(r'^(?:PL|UK|US|DE|FR|IT|ES|RU|RO|TR|NL)\s+', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+(?:HD|FHD|4K|SD|UHD|1080p|720p)(?:\+)?$', '', name, flags=re.IGNORECASE)
        return name.strip()

    def setup_ui(self):
        cfg = tk.LabelFrame(self.root, text=" KONFIGURACJA ", padx=10, pady=5)
        cfg.pack(fill=tk.X, padx=10, pady=5)
        
        self.ent_m3u = tk.Entry(cfg); self.ent_m3u.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.ent_m3u.insert(0, self.settings["m3u"]["source"])
        tk.Button(cfg, text="📁 M3U Kccc (Live)", command=lambda: self.browse_file(self.ent_m3u, [("M3U", "*.m3u"), ("Wszystkie", "*.*")])).grid(row=0, column=2, padx=2)

        self.ent_m3u_arch = tk.Entry(cfg); self.ent_m3u_arch.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.ent_m3u_arch.insert(0, self.settings.get("m3u_arch", {}).get("source", ""))
        tk.Button(cfg, text="📁 M3U OtoPay (Arch)", command=lambda: self.browse_file(self.ent_m3u_arch, [("M3U", "*.m3u"), ("Wszystkie", "*.*")])).grid(row=1, column=2, padx=2)

        self.ent_epg = tk.Entry(cfg); self.ent_epg.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        self.ent_epg.insert(0, self.settings["epg"]["source"])
        tk.Button(cfg, text="📁 EPG", command=lambda: self.browse_file(self.ent_epg, [("EPG", "*.xml *.gz"), ("Wszystkie", "*.*")])).grid(row=2, column=2, padx=2)

        self.ent_save = tk.Entry(cfg); self.ent_save.grid(row=3, column=1, sticky="ew", padx=5, pady=2)
        self.ent_save.insert(0, self.settings["recording"].get("save_path", "Nagrania"))
        tk.Button(cfg, text="📁 Zapis", command=lambda: self.browse_dir(self.ent_save)).grid(row=3, column=2, padx=2)
        
        self.chk_night_var = tk.BooleanVar(value=self.settings["recording"].get("archive_night_only", True))
        tk.Checkbutton(cfg, text="Globalnie: Pobieraj Archiwum tylko w nocy (03:00-05:00)", variable=self.chk_night_var).grid(row=4, column=1, columnspan=2, sticky="w", padx=5)
        
        tk.Label(cfg, text="Czcionka:").grid(row=0, column=3, padx=5, sticky="e")
        self.combo_font = ttk.Combobox(cfg, values=["8", "10", "12", "14", "16"], width=5, state="readonly")
        self.combo_font.set(str(self.settings.get("ui", {}).get("font_size", 10)))
        self.combo_font.grid(row=0, column=4, padx=5, pady=2, sticky="w")

        tk.Label(cfg, text="Zapas przed (min):").grid(row=1, column=3, padx=5, sticky="e")
        self.spin_pre = ttk.Spinbox(cfg, from_=0, to=120, width=5)
        self.spin_pre.set(self.settings["recording"].get("pre_padding_min", 2))
        self.spin_pre.grid(row=1, column=4, padx=5, pady=2, sticky="w")

        tk.Label(cfg, text="Zapas po (min):").grid(row=2, column=3, padx=5, sticky="e")
        self.spin_post = ttk.Spinbox(cfg, from_=0, to=300, width=5)
        self.spin_post.set(self.settings["recording"].get("post_padding_min", 5))
        self.spin_post.grid(row=2, column=4, padx=5, pady=2, sticky="w")

        tk.Label(cfg, text="Overlap (s):").grid(row=3, column=3, padx=5, sticky="e")
        self.spin_overlap = ttk.Spinbox(cfg, from_=0, to=300, width=5)
        self.spin_overlap.set(self.settings["recording"].get("overlap_s", 0))
        self.spin_overlap.grid(row=3, column=4, padx=5, pady=2, sticky="w")

        tk.Button(cfg, text="ZAPISZ I SYNC", command=self.sync_all).grid(row=0, column=5, rowspan=5, padx=10, sticky="nsew")
        cfg.columnconfigure(1, weight=1)

        main_p = ttk.PanedWindow(self.root, orient=tk.VERTICAL); main_p.pack(fill=tk.BOTH, expand=True, padx=10)
        
        top_p = ttk.PanedWindow(main_p, orient=tk.HORIZONTAL); main_p.add(top_p, weight=3)
        
        ch_frame = tk.Frame(top_p)
        top_p.add(ch_frame, weight=1)
        
        # Zmiana nazw w Menu Rozwijanym
        self.combo_list_type = ttk.Combobox(ch_frame, values=["Kccc", "OtoPay"], state="readonly")
        self.combo_list_type.set("Kccc")
        self.combo_list_type.pack(fill=tk.X, pady=(0, 2))
        self.combo_list_type.bind("<<ComboboxSelected>>", lambda e: self.on_list_type_change())

        self.tree_ch = ttk.Treeview(ch_frame, columns=("N", "URL"), show="headings")
        self.tree_ch.heading("N", text="KANAŁY")
        self.tree_ch.column("N", anchor="w")
        self.tree_ch.column("URL", width=0, stretch=tk.NO)
        self.tree_ch.pack(fill=tk.BOTH, expand=True)
        self.tree_ch.bind("<<TreeviewSelect>>", self.on_channel_click)
        self.tree_ch.bind("<Double-1>", self.open_vlc_preview) 
        
        self.ch_menu = tk.Menu(self.root, tearoff=0)
        self.ch_menu.add_command(label="Ustaw domyślne audio dla kanału...", command=self.open_channel_audio_window)
        self.ch_menu.add_separator()
        self.ch_menu.add_command(label="Ręczny Alias EPG...", command=self.open_alias_window)
        self.tree_ch.bind("<Button-3>", lambda e: self.ch_menu.post(e.x_root, e.y_root) if self.tree_ch.identify_row(e.y) else None)

        epg_f = tk.Frame(top_p); top_p.add(epg_f, weight=2)
        self.ent_s = tk.Entry(epg_f); self.ent_s.pack(fill=tk.X)
        self.ent_s.bind("<KeyRelease>", lambda e: self.perform_search())
        
        self.tree_epg = ttk.Treeview(epg_f, columns=("T", "P"), show="headings")
        self.tree_epg.heading("T", text="Czas"); self.tree_epg.column("T", width=140, anchor="center")
        self.tree_epg.heading("P", text="Program"); self.tree_epg.column("P", anchor="w")
        self.tree_epg.pack(fill=tk.BOTH, expand=True); self.tree_epg.bind("<<TreeviewSelect>>", self.on_epg_click)
        
        self.epg_menu = tk.Menu(self.root, tearoff=0)
        self.epg_menu.add_command(label="Dodaj zadanie do kolejki", command=self.add_manual_timer)
        self.tree_epg.bind("<Button-3>", lambda e: self.show_epg_menu(e))

        det_p = ttk.PanedWindow(top_p, orient=tk.VERTICAL)
        top_p.add(det_p, weight=1)
        
        self.txt_desc = tk.Text(det_p, wrap=tk.WORD, state=tk.DISABLED); det_p.add(self.txt_desc, weight=1)
        
        ctrl_f = tk.Frame(det_p); det_p.add(ctrl_f, weight=0)
        
        tk.Label(ctrl_f, text="Wybierz Format:").pack(anchor="w", pady=(5,0))
        self.combo_fmt = ttk.Combobox(ctrl_f, values=[".mkv", ".mp4", ".ts"], state="readonly"); self.combo_fmt.set(".mkv"); self.combo_fmt.pack(fill=tk.X, pady=2)
        
        tk.Label(ctrl_f, text="Wybierz Audio (Globalne):").pack(anchor="w", pady=(5,0))
        self.combo_audio = ttk.Combobox(ctrl_f, values=["Wszystkie", "Ścieżka 1", "Ścieżka 2"], state="readonly")
        self.combo_audio.set(self.settings["recording"].get("audio_track", "Wszystkie")); self.combo_audio.pack(fill=tk.X, pady=2)

        tk.Button(ctrl_f, text="+ TIMER (EPG)", command=self.add_manual_timer, bg="#27ae60", fg="white", font=("Arial", 10, "bold")).pack(fill=tk.X, pady=10)
        tk.Button(ctrl_f, text="+ AUTOTIMER (FILTRY)", command=self.open_advanced_at_window).pack(fill=tk.X, pady=2)
        tk.Button(ctrl_f, text="ZARZĄDZAJ REGUŁAMI", command=self.open_rules_window).pack(fill=tk.X, pady=10)

        bot_p = ttk.PanedWindow(main_p, orient=tk.VERTICAL); main_p.add(bot_p, weight=2)
        
        q_frame = tk.Frame(bot_p); bot_p.add(q_frame, weight=3)
        self.tree_q = ttk.Treeview(q_frame, columns=("ID", "T", "C", "S", "E", "St", "F", "Aud", "L", "Tr"), show="headings", selectmode="extended")
        
        self.tree_q.heading("ID", text="ID"); self.tree_q.column("ID", width=40, anchor="center")
        self.tree_q.heading("T", text="Tytuł"); self.tree_q.column("T", anchor="w")
        self.tree_q.heading("C", text="Kanał"); self.tree_q.column("C", width=120, anchor="w")
        self.tree_q.heading("S", text="Start"); self.tree_q.column("S", width=140, anchor="center")
        self.tree_q.heading("E", text="Koniec"); self.tree_q.column("E", width=140, anchor="center")
        self.tree_q.heading("St", text="Status"); self.tree_q.column("St", width=110, anchor="center")
        self.tree_q.heading("F", text="Format"); self.tree_q.column("F", width=50, anchor="center")
        self.tree_q.heading("Aud", text="Audio"); self.tree_q.column("Aud", width=70, anchor="center")
        # Nowe kolumny: Lista i Tryb
        self.tree_q.heading("L", text="Lista"); self.tree_q.column("L", width=60, anchor="center") 
        self.tree_q.heading("Tr", text="Tryb"); self.tree_q.column("Tr", width=80, anchor="center")
        self.tree_q.pack(fill=tk.BOTH, expand=True)
        
        self.tree_epg.tag_configure('evenrow', background='#f5f6fa')
        self.tree_epg.tag_configure('oddrow', background='#ffffff')
        self.tree_q.tag_configure('evenrow', background='#f5f6fa')
        self.tree_q.tag_configure('oddrow', background='#ffffff')
        self.tree_ch.tag_configure('evenrow', background='#f5f6fa')
        self.tree_ch.tag_configure('oddrow', background='#ffffff')
        
        self.q_menu = tk.Menu(self.root, tearoff=0)
        self.q_menu.add_command(label="Wymuś start (Dla zaznaczonych)", command=self.start_manual_recording)
        self.q_menu.add_command(label="Zatrzymaj (Dla zaznaczonych)", command=self.stop_manual_recording)
        self.q_menu.add_separator()
        # Dwie nowe wspaniałe opcje
        self.q_menu.add_command(label="Konwertuj na Live i nagrywaj natychmiast (z linku OtoPay)", command=self.convert_and_force_live)
        self.q_menu.add_command(label="Przełącz tryb Archiwum (Noc / Teraz)", command=self.toggle_archive_mode)
        self.q_menu.add_separator()
        self.q_menu.add_command(label="Zmień status na: Oczekujący", command=self.reset_status_to_waiting)
        self.q_menu.add_separator()
        self.q_menu.add_command(label="Edytuj pojedyncze zadanie", command=self.open_edit_timer_window)
        self.q_menu.add_command(label="Pokaż w folderze", command=self.open_output_folder)
        self.q_menu.add_command(label="Usuń (Dla zaznaczonych)", command=self.delete_selected_timer)
        self.q_menu.add_command(label="Wyczyść zakończone", command=self.clear_completed)
        self.tree_q.bind("<Button-3>", lambda e: self.show_q_menu(e))

        self.log_box = tk.Text(bot_p, height=6, bg="black", fg="#00ff00", font=("Consolas", 9)); bot_p.add(self.log_box, weight=1)

    def on_list_type_change(self):
        self.refresh_channel_list()
        self.perform_search() 

    def show_epg_menu(self, event):
        item = self.tree_epg.identify_row(event.y)
        if item:
            self.tree_epg.selection_set(item)
            self.epg_menu.post(event.x_root, event.y_root)

    def open_channel_audio_window(self):
        sel = self.tree_ch.selection()
        if not sel: return
        name = self.tree_ch.item(sel[0])['values'][0]
        list_type = self.combo_list_type.get() # 'Kccc' lub 'OtoPay'

        win = tk.Toplevel(self.root); win.title(f"Audio: {name}"); win.geometry("300x150")
        tk.Label(win, text=f"Domyślne audio dla kanału:\n{name} ({list_type})").pack(pady=10)

        current_val = self.settings.get("channel_audio_defaults", {}).get(list_type, {}).get(name, "Domyślne (Konfiguracja)")

        c_audio = ttk.Combobox(win, values=["Domyślne (Konfiguracja)", "Wszystkie", "Ścieżka 1", "Ścieżka 2"], state="readonly")
        c_audio.set(current_val)
        c_audio.pack(fill=tk.X, padx=20, pady=5)

        def save():
            val = c_audio.get()
            if val == "Domyślne (Konfiguracja)":
                self.settings["channel_audio_defaults"][list_type].pop(name, None)
                self.add_log(f"Usunięto wyjątek audio dla {name} ({list_type})")
            else:
                self.settings["channel_audio_defaults"][list_type][name] = val
                self.add_log(f"Zapisano wyjątek audio dla {name} ({list_type}): {val}")
            
            self.save_settings()
            win.destroy()

        tk.Button(win, text="ZAPISZ", command=save, bg="#3498db", fg="white", font=("Arial", 10, "bold")).pack(pady=10)

    def open_vlc_preview(self, event):
        sel = self.tree_ch.selection()
        if not sel: return
        url = self.tree_ch.item(sel[0])['values'][1]
        if not url: return
        
        vlc_paths = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
        ]
        
        vlc_exe = next((p for p in vlc_paths if os.path.exists(p)), None)
        
        if vlc_exe:
            try: subprocess.Popen([vlc_exe, url], creationflags=0x08000000)
            except Exception as e: self.add_log(f"Błąd uruchamiania VLC: {e}")
        else:
            messagebox.showerror("Brak VLC", "Nie znaleziono odtwarzacza VLC w standardowych lokalizacjach Windows.\nZainstaluj darmowy program VLC Media Player, aby używać podglądu.")

    def open_output_folder(self):
        sel = self.tree_q.selection()
        if sel:
            save_dir = self.settings["recording"].get("save_path", "Nagrania")
            if os.path.exists(save_dir): os.startfile(save_dir)
            else: messagebox.showwarning("Błąd", "Folder nagrań jeszcze nie istnieje.")

    def show_q_menu(self, event):
        item = self.tree_q.identify_row(event.y)
        if item:
            if item not in self.tree_q.selection():
                self.tree_q.selection_set(item)
            self.q_menu.post(event.x_root, event.y_root)

    def convert_and_force_live(self):
        sel = self.tree_q.selection()
        if not sel: return
        for item in sel:
            t_id = self.tree_q.item(item)['values'][0]
            status = self.tree_q.item(item)['values'][5]
            details = self.db.get_timer_details(t_id)
            if details and details[6] == 1: # Jeśli to jest zadanie Archiwum
                if status == 'Nagrywanie':
                    self.engine.stop_recording(t_id) # Zatrzymuje aktualne pobieranie, żeby zresetować silnik
                with self.db._get_connection() as conn:
                    # Po prostu usuwa znacznik 'is_archive'. Zostawia link z OtoPay!
                    conn.execute("UPDATE timers SET is_archive = 0, status = 'Oczekujący' WHERE id = ?", (t_id,))
                    conn.commit()
                self.add_log(f"Zadanie ID {t_id} zrzuciło flagę Arch. Startuje jako Live z linku OtoPay!")
                self.trigger_recording(t_id)
        self.refresh_queue_view()

    def toggle_archive_mode(self):
        sel = self.tree_q.selection()
        if not sel: return
        for item in sel:
            t_id = self.tree_q.item(item)['values'][0]
            details = self.db.get_timer_details(t_id)
            if details and details[6] == 1: # Tylko jeśli to zadanie Arch
                current_night = details[8]
                new_night = 0 if current_night == 1 else 1 # Przełącza 0 na 1 i odwrotnie
                with self.db._get_connection() as conn:
                    conn.execute("UPDATE timers SET night_mode = ? WHERE id = ?", (new_night, t_id))
                    conn.commit()
        self.refresh_queue_view()

    def reset_status_to_waiting(self):
        sel = self.tree_q.selection()
        if not sel: return
        for item in sel:
            t_id = self.tree_q.item(item)['values'][0]
            status = self.tree_q.item(item)['values'][5]
            if status != 'Nagrywanie': 
                self.db.update_timer_status(t_id, 'Oczekujący')
        self.refresh_queue_view()

    def start_manual_recording(self):
        for item in self.tree_q.selection():
            t_id = self.tree_q.item(item)['values'][0]
            status = self.tree_q.item(item)['values'][5]
            if status in ['Wstrzymany', 'Oczekujący', 'Błąd', 'Ocz. na zakończenie']:
                self.trigger_recording(t_id)

    def stop_manual_recording(self):
        for item in self.tree_q.selection():
            t_id = self.tree_q.item(item)['values'][0]
            status = self.tree_q.item(item)['values'][5]
            if status == 'Nagrywanie':
                self.engine.stop_recording(t_id)

    def delete_selected_timer(self):
        sel = self.tree_q.selection()
        if not sel: return
        if messagebox.askyesno("Potwierdzenie", f"Czy na pewno usunąć wybrane zadania ({len(sel)})?"):
            for item in sel:
                timer_id = self.tree_q.item(item)['values'][0]
                self.engine.stop_recording(timer_id)
                self.db.delete_timer(timer_id)
            self.refresh_queue_view()

    def clear_completed(self):
        self.db.clear_completed_timers()
        self.refresh_queue_view()

    def open_edit_timer_window(self):
        sel = self.tree_q.selection()
        if len(sel) > 1:
            messagebox.showinfo("Informacja", "Edycja parametrów możliwa jest tylko dla pojedynczego zadania naraz. Wybierz tylko jeden wiersz.")
            return
        if not sel: return
        
        timer_id = self.tree_q.item(sel[0])['values'][0]
        details = self.db.get_timer_details(timer_id)
        if not details: return
        
        # Rozpakowanie wszystkich wartości z bazy
        title, start_time, end_time, is_archive, current_audio, night_mode = details[5], details[2], details[3], details[6], details[7], details[8]

        win = tk.Toplevel(self.root); win.title("Edytuj Zadanie"); win.geometry("420x350"); win.configure(padx=20, pady=20)
        tk.Label(win, text="Tytuł:").pack(anchor="w")
        ent_title = tk.Entry(win); ent_title.insert(0, title); ent_title.pack(fill=tk.X, pady=5)
        
        tk.Label(win, text="Start (YYYY-MM-DD HH:MM:SS):").pack(anchor="w")
        ent_start = tk.Entry(win); ent_start.insert(0, start_time); ent_start.pack(fill=tk.X, pady=5)
        
        tk.Label(win, text="Koniec (YYYY-MM-DD HH:MM:SS):").pack(anchor="w")
        ent_end = tk.Entry(win); ent_end.insert(0, end_time); ent_end.pack(fill=tk.X, pady=5)
        
        tk.Label(win, text="Ścieżka Audio:").pack(anchor="w")
        c_audio = ttk.Combobox(win, values=["Wszystkie", "Ścieżka 1", "Ścieżka 2"], state="readonly")
        c_audio.set(current_audio if current_audio else "Wszystkie"); c_audio.pack(fill=tk.X, pady=5)

        chk_night_var = tk.IntVar(value=night_mode)
        if is_archive == 1:
            chk_night = tk.Checkbutton(win, text="Pobieraj z archiwum w oknie nocnym (03:00-05:00)", variable=chk_night_var)
            chk_night.pack(anchor="w", pady=5)

        def save_changes():
            new_title = ent_title.get()
            new_start_str = ent_start.get()
            new_end_str = ent_end.get()
            new_audio_track = c_audio.get()
            new_night_mode = chk_night_var.get()
            
            self.db.update_timer_details(timer_id, new_title, new_start_str, new_end_str, new_audio_track, new_night_mode)
            
            status = self.tree_q.item(sel[0])['values'][5]
            if status == 'Nagrywanie':
                try:
                    new_end_dt = datetime.strptime(new_end_str, "%Y-%m-%d %H:%M:%S")
                    # Oparcie wprost na danych z bazy
                    if is_archive == 1:
                        self.engine.update_end_time(timer_id, new_end_dt)
                    else:
                        post_pad = self.settings["recording"].get("post_padding_min", 5)
                        self.engine.update_end_time(timer_id, new_end_dt + timedelta(minutes=post_pad))
                    
                    if new_audio_track != current_audio:
                        self.engine.change_audio_track(timer_id, new_audio_track)
                        
                except Exception as e:
                    self.add_log(f"Błąd aktualizacji w locie: {e}")

            self.refresh_queue_view()
            win.destroy()

        tk.Button(win, text="ZAPISZ ZMIANY", command=save_changes, bg="#3498db", fg="white", font=("Arial", 10, "bold")).pack(fill=tk.X, pady=15)

    def add_log(self, m): self.log_box.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {m}\n"); self.log_box.see(tk.END)

    def sync_all(self):
        self.save_settings()
        if not os.path.exists("data"): os.makedirs("data")
        def _task():
            try:
                m3u_src = self.settings["m3u"]["source"]
                self.add_log(f"Wczytywanie M3U Kccc: {m3u_src}")
                if m3u_src.startswith(("http://", "https://")):
                    r = requests.get(m3u_src, timeout=30); m3u_text = r.text
                else:
                    try:
                        with open(m3u_src, 'r', encoding='utf-8') as f: m3u_text = f.read()
                    except:
                        with open(m3u_src, 'r', encoding='cp1250') as f: m3u_text = f.read()

                ch_matches = re.findall(r'#EXTINF:.*?,(.*?)\r?\n(http.*?)(?:\r?\n|$)', m3u_text, re.M)
                prepared = []
                for name, url in ch_matches:
                    tvg_match = re.search(r'tvg-id="(.*?)"', m3u_text.split(url)[0].split('#EXTINF')[-1])
                    tid = tvg_match.group(1).strip() if tvg_match else name.strip()
                    c_name = self.clean_channel_name(name)
                    prepared.append((c_name, tid, url.strip()))
                
                if prepared:
                    prepared.sort(key=lambda x: x[0].lower())
                    self.db.sync_channels(prepared)
                    self.root.after(0, self.refresh_channel_list)
                    self.add_log(f"M3U Kccc OK: {len(prepared)} kanałów.")
                else:
                    self.add_log("M3U Kccc: Nie znaleziono kanałów!")
            except Exception as e_m3u:
                self.add_log(f"BŁĄD M3U Kccc: {e_m3u}")
                
            try:
                m3u_arch_src = self.settings["m3u_arch"]["source"]
                if m3u_arch_src:
                    self.add_log(f"Wczytywanie M3U OtoPay: {m3u_arch_src}")
                    if m3u_arch_src.startswith(("http://", "https://")):
                        r = requests.get(m3u_arch_src, timeout=30); m3u_arch_text = r.text
                    else:
                        with open(m3u_arch_src, 'r', encoding='utf-8', errors='ignore') as f: m3u_arch_text = f.read()
                    
                    arch_matches = re.findall(r'#EXTINF:.*?,(.*?)\r?\n(http.*?)(?:\r?\n|$)', m3u_arch_text, re.M)
                    arch_prepared = []
                    for name, url in arch_matches:
                        tvg_match = re.search(r'tvg-id="(.*?)"', m3u_arch_text.split(url)[0].split('#EXTINF')[-1])
                        tid = tvg_match.group(1).strip() if tvg_match else name.strip()
                        c_name = self.clean_channel_name(name)
                        arch_prepared.append((c_name, tid, url.strip()))
                    
                    if arch_prepared:
                        arch_prepared.sort(key=lambda x: x[0].lower())
                        self.db.sync_channels_archive(arch_prepared)
                        self.add_log(f"M3U OtoPay OK: {len(arch_prepared)} kanałów.")
            except Exception as e_arch:
                self.add_log(f"BŁĄD M3U OtoPay: {e_arch}")

            try:
                epg_src = self.settings["epg"]["source"]; lx = "data/guide.xml"
                self.add_log(f"Wczytywanie EPG: {epg_src}")
                if epg_src.startswith(("http://", "https://")):
                    with requests.get(epg_src, timeout=120, stream=True) as r_epg:
                        r_epg.raise_for_status()
                        temp_epg = "data/temp_epg"
                        with open(temp_epg, "wb") as f:
                            for chunk in r_epg.iter_content(chunk_size=5*1024*1024):
                                if chunk: f.write(chunk)
                        
                        with open(temp_epg, "rb") as f_check:
                            header = f_check.read(2)
                        
                        if header == b'\x1f\x8b':
                            with gzip.open(temp_epg, "rb") as f_in:
                                with open(lx, "wb") as f_out: f_out.write(f_in.read())
                        else:
                            import shutil
                            if os.path.exists(lx): os.remove(lx)
                            shutil.move(temp_epg, lx)
                else:
                    if epg_src.lower().endswith(".gz"):
                        with gzip.open(epg_src, "rb") as f_in:
                            with open(lx, "wb") as f_out: f_out.write(f_in.read())
                    else:
                        import shutil; shutil.copy2(epg_src, lx)
                
                if os.path.exists(lx) and os.path.getsize(lx) > 0:
                    self.parse_epg(lx); 
                    
                    global_night = 1 if self.chk_night_var.get() else 0
                    added = self.db.run_autotimer_hunter(
                        self.combo_fmt.get(), 
                        self.combo_audio.get(), 
                        self.settings.get("channel_audio_defaults", {}),
                        global_night
                    )
                    
                    self.add_log(f"EPG OK. AutoTimer dodał {added} nagrań."); self.root.after(0, self.refresh_queue_view)
            except Exception as e_epg:
                self.add_log(f"BŁĄD EPG: {e_epg}")

        threading.Thread(target=_task, daemon=True).start()

    def parse_epg(self, path):
        progs = []
        for _, el in ET.iterparse(path, events=('end',)):
            if el.tag == 'programme':
                s = datetime.strptime(el.get('start')[:14], "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
                e = datetime.strptime(el.get('stop')[:14], "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
                progs.append((el.get('channel'), el.get('channel'), el.findtext('title'), el.findtext('desc') or "", s, e)); el.clear()
        self.db.sync_epg_data(progs)

    def add_manual_timer(self):
        sel = self.tree_epg.selection()
        if not sel: return
        v = self.tree_epg.item(sel[0])['values']; s_t = v[0]; d = self.tree_epg.item(sel[0])['tags'][1]
        m = re.match(r'\[(.*?)\] (.*)', v[1])
        if m:
            cid, t = m.groups()
            ft = self.db._format_series_title(t, d)
            ft = re.sub(r'[\\/*?:"<>|]', '', ft).strip()
            
            list_type = self.combo_list_type.get() # 'Kccc' lub 'OtoPay'
            is_archive = 1 if list_type == "OtoPay" else 0
            global_audio = self.combo_audio.get()
            global_night = 1 if self.chk_night_var.get() else 0
            
            s_dt = datetime.strptime(s_t, "%Y-%m-%d %H:%M:%S")
            now_dt = datetime.now()
            
            with self.db._get_connection() as conn:
                res = conn.execute("SELECT end_time FROM epg_programs WHERE channel_id = ? AND title = ? AND start_time = ?", (cid, t, s_t)).fetchone()
                et = res[0] if res else (s_dt + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
                e_dt = datetime.strptime(et, "%Y-%m-%d %H:%M:%S")
                
                if is_archive == 1:
                    ft = f"[ARCH] {ft}"
                    arch_data = self.db.get_archive_url_and_name(cid)
                    if not arch_data or not arch_data[0]:
                        messagebox.showerror("Błąd", "Nie znaleziono tego kanału na liście M3U OtoPay.")
                        return

                    arch_url, real_name = arch_data
                    selected_audio = self.settings.get("channel_audio_defaults", {}).get("OtoPay", {}).get(real_name, global_audio)

                    if now_dt >= (e_dt + timedelta(seconds=300)):
                        status = 'Oczekujący'
                    else:
                        status = 'Ocz. na zakończenie'
                    
                    self.db.add_timer(ft, cid, arch_url, s_t, et, self.combo_fmt.get(), status, 1, selected_audio, global_night, "OtoPay")
                else:
                    status = 'Wstrzymany' if s_dt <= now_dt else 'Oczekujący'
                    url_row = conn.execute('''SELECT url, name FROM channels WHERE tvg_id = ? OR name = ? 
                                              OR tvg_id = (SELECT m3u_tvg_id FROM channel_aliases WHERE epg_channel_id = ?)''', (cid, cid, cid)).fetchone()
                    if url_row:
                        real_name = url_row[1]
                        selected_audio = self.settings.get("channel_audio_defaults", {}).get("Kccc", {}).get(real_name, global_audio)
                        self.db.add_timer(ft, cid, url_row[0], s_t, et, self.combo_fmt.get(), status, 0, selected_audio, 1, "Kccc")
                    else:
                        messagebox.showerror("Błąd", "Nie znaleziono tego kanału na liście M3U Kccc.\nSprawdź czy nie musisz dopisać Ręcznego Aliasu.")
                        return
                        
            self.refresh_queue_view()

    def open_advanced_at_window(self):
        kw = self.ent_s.get(); channels = [c[0] for c in self.db.get_channels()]; sel_epg = self.tree_epg.selection()
        if sel_epg:
            m = re.match(r'\[(.*?)\] (.*)', self.tree_epg.item(sel_epg[0])['values'][1])
            if m: ch_id, kw = m.groups(); kw = re.sub(r'(\sS\d+E\d+.*|\d+\.\s.*)', '', kw).strip()
        win = tk.Toplevel(self.root); win.title("Konfiguracja Serii"); win.geometry("480x600"); win.configure(padx=20, pady=20)
        tk.Label(win, text="TYTUŁ:", font=("Arial", 10, "bold")).pack(anchor="w")
        e_kw = tk.Entry(win); e_kw.pack(fill=tk.X, pady=5); e_kw.insert(0, kw)
        tk.Label(win, text="KANAŁ (ALL):").pack(anchor="w")
        c_ch = ttk.Combobox(win, values=["ALL"] + sorted(channels)); c_ch.set("ALL"); c_ch.pack(fill=tk.X, pady=5)
        hf = tk.Frame(win); hf.pack(fill=tk.X, pady=10); e_sh = tk.Entry(hf, width=5); e_sh.pack(side=tk.LEFT); tk.Label(hf, text=" do ").pack(side=tk.LEFT); e_eh = tk.Entry(hf, width=5); e_eh.pack(side=tk.LEFT)
        df = tk.Frame(win); df.pack(fill=tk.X); e_sd = tk.Entry(df, width=12); e_sd.pack(side=tk.LEFT); tk.Label(df, text=" do ").pack(side=tk.LEFT); e_ed = tk.Entry(df, width=12); e_ed.pack(side=tk.LEFT)
        tk.Label(win, text="WYKLUCZ SŁOWO:").pack(anchor="w"); e_ex = tk.Entry(win); e_ex.pack(fill=tk.X, pady=5)
        def save():
            self.db.add_advanced_autotimer(e_kw.get(), c_ch.get(), e_sh.get(), e_eh.get(), e_sd.get(), e_ed.get(), e_ex.get()); 
            global_night = 1 if self.chk_night_var.get() else 0
            self.db.run_autotimer_hunter(self.combo_fmt.get(), self.combo_audio.get(), self.settings.get("channel_audio_defaults", {}), global_night); 
            self.refresh_queue_view(); win.destroy()
        tk.Button(win, text="ZAPISZ I SZUKAJ", command=save).pack(fill=tk.X, pady=20)

    def open_rules_window(self):
        win = tk.Toplevel(self.root); tree = ttk.Treeview(win, columns=("ID", "KW", "CH", "S", "E", "DS", "DE", "EX"), show="headings")
        for c in ("ID", "KW", "CH", "S", "E", "DS", "DE", "EX"): tree.heading(c, text=c); tree.column(c, width=60)
        tree.pack(fill=tk.BOTH, expand=True)
        for r in self.db.get_autotimers(): tree.insert("", tk.END, values=r)
        def delete():
            if tree.selection(): self.db.delete_autotimer(tree.item(tree.selection()[0])['values'][0]); tree.delete(tree.selection())
        tk.Button(win, text="USUŃ", command=delete).pack()

    def trigger_recording(self, t_id):
        details = self.db.get_timer_details(t_id)
        if details:
            ch_name, url, s, e, fmt, title, is_archive, audio_track, n_mode, src_list = details
            if url:
                save_dir = self.settings["recording"].get("save_path", "Nagrania")
                if not os.path.exists(save_dir): os.makedirs(save_dir)
                
                clean_title = re.sub(r'[\\/*?:"<>|]', '', title).strip()
                suffix = f"_{src_list}" if is_archive == 1 else f"_{src_list}{t_id}" # np. _OtoPay albo _Kccc1
                p = os.path.join(save_dir, f"{clean_title}{suffix}")
                
                s_dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                e_dt = datetime.strptime(e, "%Y-%m-%d %H:%M:%S")
                
                overlap_val = self.settings["recording"].get("overlap_s", 0)
                
                if is_archive == 1:
                    self.engine.start_recording(t_id, url, p, e_dt, fmt, audio_track, 20, 1, s_dt, overlap_val)
                else:
                    post_pad = self.settings["recording"].get("post_padding_min", 5)
                    real_e_dt = e_dt + timedelta(minutes=post_pad)
                    
                    if real_e_dt <= datetime.now():
                        real_e_dt = datetime.now() + timedelta(seconds=60)
                        
                    self.engine.start_recording(t_id, url, p, real_e_dt, fmt, audio_track, 20, 0, None, 0)
                
                self.db.update_timer_status(t_id, 'Nagrywanie')
                self.refresh_queue_view()

    def main_scheduler_loop(self):
        while True:
            now = datetime.now()
            
            all_timers = self.db.get_active_timers()
            active_live = len([t for t in all_timers if t[5] == 'Nagrywanie' and t[7] == 0])
            active_arch = len([t for t in all_timers if t[5] == 'Nagrywanie' and t[7] == 1])
            
            for t_id, title, ch_name, s, e, st, fmt, is_archive, a_track, n_mode, src_list in all_timers:
                s_dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                e_dt = datetime.strptime(e, "%Y-%m-%d %H:%M:%S")
                
                if is_archive == 1:
                    if st == 'Ocz. na zakończenie':
                        if now >= (e_dt + timedelta(seconds=300)):
                            self.db.update_timer_status(t_id, 'Oczekujący')
                            self.root.after(0, self.refresh_queue_view)
                    elif st == 'Oczekujący':
                        if now >= (e_dt + timedelta(seconds=300)):
                            is_night = 3 <= now.hour < 5
                            if n_mode == 0 or (n_mode == 1 and is_night):
                                if active_arch < 1:
                                    self.trigger_recording(t_id)
                                    active_arch += 1
                                    time.sleep(5)
                else:
                    if st == 'Oczekujący':
                        pre_pad = self.settings["recording"].get("pre_padding_min", 2)
                        if now >= (s_dt - timedelta(minutes=pre_pad)) and now < e_dt:
                            if active_live < 3:
                                self.trigger_recording(t_id)
                                active_live += 1
                                time.sleep(5)
            time.sleep(30)

    def on_channel_click(self, e):
        sel = self.tree_ch.selection()
        if sel:
            name = self.tree_ch.item(sel[0])['values'][0]
            list_type = self.combo_list_type.get()
            table = "channels_archive" if list_type == "OtoPay" else "channels"
            with self.db._get_connection() as conn:
                row = conn.execute(f"SELECT tvg_id FROM {table} WHERE name = ?", (name,)).fetchone()
                if row:
                    alias = self.db.get_alias_for(row[0])
                    self.ent_s.delete(0, tk.END); self.ent_s.insert(0, alias if alias else row[0]); self.perform_search()

    def perform_search(self):
        ph = self.ent_s.get()
        if len(ph) < 2: return
        
        list_type = self.combo_list_type.get()
        if list_type == "OtoPay":
            min_time = (datetime.now() - timedelta(hours=84)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            min_time = (datetime.now() - timedelta(minutes=60)).strftime("%Y-%m-%d %H:%M:%S")

        for i in self.tree_epg.get_children(): self.tree_epg.delete(i)
        for idx, r in enumerate(self.db.search_epg(ph, min_time)):
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.tree_epg.insert("", tk.END, values=(r[5], f"[{r[2]}] {r[3]}"), tags=(tag, r[4]))

    def on_epg_click(self, e):
        sel = self.tree_epg.selection()
        if sel:
            tags = self.tree_epg.item(sel[0])['tags']
            if len(tags) > 1: 
                self.txt_desc.config(state=tk.NORMAL); self.txt_desc.delete(1.0, tk.END); self.txt_desc.insert(tk.END, tags[1]); self.txt_desc.config(state=tk.DISABLED)

    def open_alias_window(self):
        sel = self.tree_ch.selection()
        if not sel: return
        name = self.tree_ch.item(sel[0])['values'][0]
        list_type = self.combo_list_type.get()
        table = "channels_archive" if list_type == "OtoPay" else "channels"
        
        with self.db._get_connection() as conn: 
            row = conn.execute(f"SELECT tvg_id FROM {table} WHERE name = ?", (name,)).fetchone()
            if not row: return
            mid = row[0]
            
        win = tk.Toplevel(self.root); win.geometry("300x400")
        ent = tk.Entry(win); ent.pack(fill=tk.X); lb = tk.Listbox(win); lb.pack(fill=tk.BOTH, expand=True)
        def search():
            lb.delete(0, tk.END); [lb.insert(tk.END, r[0]) for r in self.db._get_connection().execute("SELECT DISTINCT channel_id FROM epg_programs WHERE channel_id LIKE ?", (f'%{ent.get()}%',)).fetchall()]
        tk.Button(win, text="SZUKAJ", command=search).pack()
        def save():
            if lb.curselection(): self.db.set_channel_alias(mid, lb.get(lb.curselection())); win.destroy(); self.on_channel_click(None)
        tk.Button(win, text="ZAPISZ", command=save).pack()

    def refresh_channel_list(self):
        for i in self.tree_ch.get_children(): self.tree_ch.delete(i)
        if hasattr(self, 'combo_list_type') and self.combo_list_type.get() == "OtoPay":
            channels = self.db.get_archive_channels()
        else:
            channels = self.db.get_channels()
        for idx, r in enumerate(channels): 
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.tree_ch.insert("", tk.END, values=(r[0], r[2]), tags=(tag,))

    def refresh_queue_view(self):
        for i in self.tree_q.get_children(): self.tree_q.delete(i)
        # r = id(0), title(1), ch(2), s(3), e(4), st(5), fmt(6), is_archive(7), audio(8), night_mode(9), source_list(10)
        for idx, r in enumerate(self.db.get_active_timers()):
            source_list = r[10] if len(r) > 10 and r[10] else ("OtoPay" if r[7] == 1 else "Kccc")
            
            if r[7] == 1:
                type_str = "Arch (Noc)" if r[9] == 1 else "Arch (Teraz)"
            else:
                type_str = "Live"
                
            disp_row = [r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[8], source_list, type_str]
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.tree_q.insert("", tk.END, values=disp_row, tags=(tag,))

if __name__ == "__main__":
    root = tk.Tk(); app = IPTVCommanderApp(root); root.mainloop()