import subprocess, os, time, threading
from datetime import datetime, timedelta

class RecordingEngine:
    def __init__(self, logger_callback=None, finish_callback=None):
        self.logger_callback = logger_callback
        self.finish_callback = finish_callback
        self.active_processes = {}
        self.force_stopped = set()
        self.active_end_times = {}
        self.active_audio_tracks = {}

    def log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        if self.logger_callback: self.logger_callback(f"[{ts}] {msg}")

    def start_recording(self, t_id, url, base_path, end_dt, fmt, audio_track="Wszystkie", timeout=20, is_archive=0, archive_start_dt=None, overlap=0):
        self.active_end_times[t_id] = end_dt
        self.active_audio_tracks[t_id] = audio_track
        thread = threading.Thread(target=self._record_loop, args=(t_id, url, base_path, fmt, timeout, is_archive, archive_start_dt, overlap), daemon=True)
        thread.start()

    def stop_recording(self, t_id):
        self.force_stopped.add(t_id)
        if t_id in self.active_processes:
            try:
                self.active_processes[t_id].terminate()
            except Exception as e:
                self.log(f"Błąd zatrzymywania {t_id}: {e}")

    def update_end_time(self, t_id, new_end_dt):
        """Aktualizacja czasu zakończenia dla zadania w locie"""
        if t_id in self.active_end_times:
            self.active_end_times[t_id] = new_end_dt
            self.log(f"Zaktualizowano czas zakończenia dla zadania w locie.")

    def change_audio_track(self, t_id, new_track):
        """Natychmiastowa wymiana mapowania podczas nagrywania!"""
        if t_id in self.active_audio_tracks:
            self.active_audio_tracks[t_id] = new_track
            self.log(f"Wymuszam zmianę Audio na '{new_track}' dla zadania {t_id}...")
            if t_id in self.active_processes:
                try: self.active_processes[t_id].terminate()
                except: pass

    def _get_audio_map(self, track_name):
        if track_name == "Ścieżka 1":
            return ['-map', '0:v:0', '-map', '0:a:0', '-disposition:a:0', 'default']
        elif track_name == "Ścieżka 2":
            return ['-map', '0:v:0', '-map', '0:a:1', '-disposition:a:0', 'default']
        return ['-map', '0']

    def _record_loop(self, t_id, url, base_path, fmt, timeout, is_archive, archive_start_dt, overlap):
        
        if is_archive and archive_start_dt:
            current_dt = archive_start_dt
            part = 1
            
            while current_dt < self.active_end_times.get(t_id, current_dt) and t_id not in self.force_stopped:
                target_end = self.active_end_times.get(t_id, current_dt)
                rem_sec = int((target_end - current_dt).total_seconds())
                if rem_sec <= 0: break
                
                current_audio_map = self._get_audio_map(self.active_audio_tracks.get(t_id, "Wszystkie"))
                
                block_dur = min(3600, rem_sec + overlap)
                curr_out = f"{base_path}_p{part}{fmt}"
                block_url = f"{url}?utc={int(current_dt.timestamp())}"
                
                cmd = [
                    'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                    '-user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    '-rw_timeout', '15000000',
                    '-i', block_url, '-t', str(block_dur)
                ] + current_audio_map + ['-c', 'copy', curr_out]
                
                self.log(f"Archiwum: Zapis bloku {part} (Audio: {self.active_audio_tracks.get(t_id, 'Wszystkie')})")
                proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=0x08000000)
                self.active_processes[t_id] = proc
                
                last_size = -1
                stagnant_loops = 0
                
                while proc.poll() is None:
                    if t_id in self.force_stopped or current_dt >= self.active_end_times.get(t_id, current_dt):
                        proc.terminate()
                        break
                    
                    time.sleep(5)
                    
                    if os.path.exists(curr_out):
                        curr_size = os.path.getsize(curr_out)
                        if curr_size == last_size:
                            stagnant_loops += 1
                        else:
                            stagnant_loops = 0
                            last_size = curr_size
                    else:
                        stagnant_loops += 1
                        
                    if stagnant_loops > 12: 
                        self.log(f"Archiwum: Błąd pobierania (brak danych). Restart...")
                        proc.terminate()
                        break
                
                try: proc.terminate(); proc.wait(timeout=2)
                except: pass
                
                current_dt += timedelta(seconds=3600 - overlap)
                part += 1
                
            self.active_processes.pop(t_id, None)
            self.active_end_times.pop(t_id, None)
            self.active_audio_tracks.pop(t_id, None)
            self.force_stopped.discard(t_id)
            if self.finish_callback: self.finish_callback(t_id, "Zakończono")
            
        else:
            part = 1

            while datetime.now() < self.active_end_times.get(t_id, datetime.now()) and t_id not in self.force_stopped:
                target_end = self.active_end_times.get(t_id, datetime.now())
                rem_sec = int((target_end - datetime.now()).total_seconds())
                if rem_sec <= 0: break
                
                current_audio_map = self._get_audio_map(self.active_audio_tracks.get(t_id, "Wszystkie"))
                curr_out = f"{base_path}_p{part}{fmt}"
                
                cmd = [
                    'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                    '-user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    '-rw_timeout', '15000000', 
                    '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
                    '-i', url, '-t', str(rem_sec)
                ] + current_audio_map + ['-c', 'copy', curr_out]
                
                self.log(f"Live: Zapis części {part} (Audio: {self.active_audio_tracks.get(t_id, 'Wszystkie')})")
                proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=0x08000000)
                self.active_processes[t_id] = proc
                
                last_size = -1
                stagnant_loops = 0
                
                while proc.poll() is None:
                    if t_id in self.force_stopped or datetime.now() >= self.active_end_times.get(t_id, datetime.now()):
                        proc.terminate()
                        break
                    
                    time.sleep(5)
                    
                    if os.path.exists(curr_out):
                        curr_size = os.path.getsize(curr_out)
                        if curr_size == last_size:
                            stagnant_loops += 1
                        else:
                            stagnant_loops = 0
                            last_size = curr_size
                    else:
                        stagnant_loops += 1
                        
                    if stagnant_loops > 12: 
                        self.log(f"Live: Zamrożenie strumienia. Restart nagrywania (część {part+1})...")
                        proc.terminate()
                        break
                
                try: proc.terminate(); proc.wait(timeout=2)
                except: pass
                
                if os.path.exists(curr_out) and os.path.getsize(curr_out) < 1024:
                    time.sleep(15) 
                else:
                    part += 1
                    time.sleep(5) 
                
            self.active_processes.pop(t_id, None)
            self.active_end_times.pop(t_id, None)
            self.active_audio_tracks.pop(t_id, None)
            self.force_stopped.discard(t_id)
            if self.finish_callback: self.finish_callback(t_id, "Zakończono")