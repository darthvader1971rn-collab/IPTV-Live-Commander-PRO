import tkinter as tk
from tkinter import filedialog, messagebox
import winreg
import os
import ctypes

class FFmpegPathInstaller:
    def __init__(self, root):
        self.root = root
        self.root.title("Instalator Ścieżki FFmpeg")
        self.root.geometry("450x180")
        self.root.resizable(False, False)
        
        # Stylizacja wbudowanym motywem
        try:
            from tkinter import ttk
            style = ttk.Style()
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except: pass

        self.setup_ui()

    def setup_ui(self):
        tk.Label(self.root, text="Kreator Zmiennych Środowiskowych (PATH)", font=("Arial", 12, "bold")).pack(pady=(15, 5))
        tk.Label(self.root, text="Wskaż folder 'bin', w którym znajduje się pobrany plik ffmpeg.exe", font=("Arial", 9)).pack()

        frame = tk.Frame(self.root)
        frame.pack(fill=tk.X, padx=20, pady=15)

        self.ent_path = tk.Entry(frame, font=("Arial", 10))
        self.ent_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        tk.Button(frame, text="Przeglądaj...", command=self.browse_folder).pack(side=tk.RIGHT)

        tk.Button(self.root, text="DODAJ DO SYSTEMU (PATH)", command=self.add_to_path, bg="#27ae60", fg="white", font=("Arial", 10, "bold"), pady=5).pack(fill=tk.X, padx=20)

    def browse_folder(self):
        dirname = filedialog.askdirectory(title="Wybierz folder bin z FFmpeg")
        if dirname:
            self.ent_path.delete(0, tk.END)
            self.ent_path.insert(0, os.path.normpath(dirname))

    def add_to_path(self):
        new_path = self.ent_path.get().strip()
        
        if not new_path:
            messagebox.showwarning("Błąd", "Najpierw wskaż folder!")
            return
            
        # Zabezpieczenie: Sprawdzamy, czy w folderze faktycznie jest FFmpeg
        ffmpeg_exe = os.path.join(new_path, "ffmpeg.exe")
        if not os.path.exists(ffmpeg_exe):
            messagebox.showerror("Błąd pliku", f"Wskazany folder:\n{new_path}\n\nNie zawiera pliku ffmpeg.exe!\nUpewnij się, że wskazujesz folder 'bin' wewnątrz wypakowanej paczki FFmpeg.")
            return

        try:
            # Otwieramy rejestr zmiennych użytkownika
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Environment', 0, winreg.KEY_ALL_ACCESS)
            
            try:
                current_path, _ = winreg.QueryValueEx(key, 'Path')
            except FileNotFoundError:
                current_path = ""

            # Sprawdzamy, czy ścieżka już tam przypadkiem nie jest
            if new_path.lower() in current_path.lower():
                messagebox.showinfo("Gotowe", "Wybrana ścieżka jest już dodana do systemu Windows!\nNie musisz nic więcej robić.")
                winreg.CloseKey(key)
                return

            # Dopisujemy nową ścieżkę
            if current_path and not current_path.endswith(';'):
                new_path_value = current_path + ';' + new_path
            else:
                new_path_value = current_path + new_path

            # Zapisujemy do rejestru
            winreg.SetValueEx(key, 'Path', 0, winreg.REG_EXPAND_SZ, new_path_value)
            winreg.CloseKey(key)

            # Informujemy system o zmianie w locie (odpowiednik kliknięcia "OK" w oknach Windows)
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            result = ctypes.c_long()
            ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, 'Environment', SMTO_ABORTIFHUNG, 5000, ctypes.byref(result))

            messagebox.showinfo("Sukces!", "Ścieżka do FFmpeg została pomyślnie dodana do systemu!\n\nMożesz teraz zamknąć to okno i uruchomić główny program IPTV Commander.")
            self.root.destroy()
            
        except PermissionError:
            messagebox.showerror("Brak uprawnień", "Brak uprawnień do edycji Rejestru. Spróbuj uruchomić skrypt jako Administrator.")
        except Exception as e:
            messagebox.showerror("Krytyczny Błąd", f"Wystąpił nieoczekiwany błąd podczas edycji PATH:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FFmpegPathInstaller(root)
    root.mainloop()