import sqlite3
import re
from datetime import datetime

class DVRDatabase:
    def __init__(self, db_path="data/commander.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS timers (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, channel_name TEXT, 
                channel_url TEXT, start_time DATETIME, end_time DATETIME, 
                status TEXT DEFAULT 'Oczekujący', file_format TEXT DEFAULT '.ts')''')
            
            try: cursor.execute("ALTER TABLE timers ADD COLUMN is_archive INTEGER DEFAULT 0")
            except: pass
            try: cursor.execute("ALTER TABLE timers ADD COLUMN audio_track TEXT DEFAULT 'Wszystkie'")
            except: pass
            try: cursor.execute("ALTER TABLE timers ADD COLUMN night_mode INTEGER DEFAULT 1")
            except: pass
            try: cursor.execute("ALTER TABLE timers ADD COLUMN source_list TEXT DEFAULT 'Kccc'")
            except: pass
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS epg_programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, channel_name TEXT, 
                title TEXT, description TEXT, start_time DATETIME, end_time DATETIME)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, tvg_id TEXT, url TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS channels_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, tvg_id TEXT, url TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS autotimers (
                id INTEGER PRIMARY KEY AUTOINCREMENT, keyword TEXT, channel_id TEXT, 
                start_hour TEXT, end_hour TEXT, start_date TEXT, end_date TEXT,
                exclude_word TEXT, enabled INTEGER DEFAULT 1)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS recording_history (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT UNIQUE, recorded_at DATETIME)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS channel_aliases (m3u_tvg_id TEXT PRIMARY KEY, epg_channel_id TEXT)''')
            conn.commit()

    def sync_channels(self, channel_list):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM channels")
            conn.executemany("INSERT INTO channels (name, tvg_id, url) VALUES (?,?,?)", channel_list)
            conn.commit()

    def sync_channels_archive(self, channel_list):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM channels_archive")
            conn.executemany("INSERT INTO channels_archive (name, tvg_id, url) VALUES (?,?,?)", channel_list)
            conn.commit()

    def sync_epg_data(self, programs):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM epg_programs")
            conn.executemany("INSERT INTO epg_programs (channel_id, channel_name, title, description, start_time, end_time) VALUES (?,?,?,?,?,?)", programs)
            conn.commit()

    def _format_series_title(self, base_title, desc):
        se_m = re.search(r'(S\d+E\d+)(?:\s*-\s*|\s+)?([^\n\.]*)', desc)
        if se_m:
            ep_info = se_m.group(1)
            ep_title = se_m.group(2).strip()
            if ep_title and len(ep_title) < 40:
                return f"{base_title} {ep_info} {ep_title}".strip()
            return f"{base_title} {ep_info}".strip()
        return base_title

    def add_advanced_autotimer(self, kw, ch_id, s_h, e_h, s_d, e_d, ex_w):
        with self._get_connection() as conn:
            conn.execute('''INSERT INTO autotimers (keyword, channel_id, start_hour, end_hour, start_date, end_date, exclude_word) 
                         VALUES (?,?,?,?,?,?,?)''', (kw, ch_id, s_h, e_h, s_d, e_d, ex_w))
            conn.commit()

    def add_timer(self, title, channel_name, channel_url, start_time, end_time, file_format, status='Oczekujący', is_archive=0, audio_track='Wszystkie', night_mode=1, source_list='Kccc'):
        with self._get_connection() as conn:
            conn.execute("INSERT INTO timers (title, channel_name, channel_url, start_time, end_time, file_format, status, is_archive, audio_track, night_mode, source_list) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (title, channel_name, channel_url, start_time, end_time, file_format, status, is_archive, audio_track, night_mode, source_list))
            conn.commit()

    def run_autotimer_hunter(self, default_format=".ts", default_audio="Wszystkie", audio_overrides=None, global_night_mode=1):
        if audio_overrides is None: audio_overrides = {}
        added = 0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        now_dt = datetime.now()
        with self._get_connection() as conn:
            rules = conn.execute("SELECT keyword, channel_id, start_hour, end_hour, start_date, end_date, exclude_word FROM autotimers WHERE enabled = 1").fetchall()
            for kw, ch_filter, s_h, e_h, s_d, e_d, ex_w in rules:
                clean_kw = re.sub(r'[^a-zA-Z0-9\s]', '', kw).strip().lower()
                query = "SELECT title, channel_name, start_time, end_time, channel_id, description FROM epg_programs WHERE end_time >= ?"
                matches = conn.execute(query, [now_str]).fetchall()
                for t, cn, s, e, cid, desc in matches:
                    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', t).lower()
                    if clean_kw not in clean_title: continue
                    if ch_filter and ch_filter != "ALL":
                        f_c = re.sub(r'(PL[:|]|\sHD|\sFHD|\s4K|[^a-zA-Z0-9])', '', ch_filter, flags=re.I).lower()
                        db_c = re.sub(r'(PL[:|]|\sHD|\sFHD|\s4K|[^a-zA-Z0-9])', '', cn, flags=re.I).lower()
                        if f_c not in db_c and db_c not in f_c: continue
                    
                    s_dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                    if s_d and s_dt.date() < datetime.strptime(s_d, "%Y-%m-%d").date(): continue
                    if e_d and s_dt.date() > datetime.strptime(e_d, "%Y-%m-%d").date(): continue
                    if s_h and e_h and not (int(s_h) <= s_dt.hour <= int(e_h)): continue
                    if ex_w and (ex_w.lower() in t.lower() or ex_w.lower() in desc.lower()): continue
                    
                    ft = self._format_series_title(t, desc)
                    ft = re.sub(r'[\\/*?:"<>|]', '', ft).strip()
                    
                    if not self.is_duplicate(ft):
                        url_r = conn.execute('''SELECT url, name FROM channels WHERE tvg_id = ? OR name = ? 
                                              OR tvg_id = (SELECT m3u_tvg_id FROM channel_aliases WHERE epg_channel_id = ?)''', (cid, cn, cid)).fetchone()
                        if url_r:
                            real_m3u_name = url_r[1]
                            ch_audio = audio_overrides.get("Kccc", {}).get(real_m3u_name, default_audio)
                            status = 'Wstrzymany' if s_dt <= now_dt else 'Oczekujący'
                            self.add_timer(ft, cn, url_r[0], s, e, default_format, status, 0, ch_audio, global_night_mode, 'Kccc')
                            added += 1
            conn.commit()
        return added

    def is_duplicate(self, title):
        with self._get_connection() as conn:
            res = conn.execute("SELECT id FROM recording_history WHERE title = ? UNION SELECT id FROM timers WHERE title = ?", (title, title)).fetchone()
            return res is not None

    def search_epg(self, keyword, min_end_time):
        with self._get_connection() as conn:
            return conn.execute('''SELECT * FROM epg_programs 
                                   WHERE (channel_id = ? OR title LIKE ?) AND end_time >= ? 
                                   ORDER BY start_time ASC LIMIT 300''', 
                                (keyword, f'%{keyword}%', min_end_time)).fetchall()

    def get_channels(self):
        with self._get_connection() as conn:
            return conn.execute("SELECT name, tvg_id, url FROM channels ORDER BY name ASC").fetchall()

    def get_archive_channels(self):
        with self._get_connection() as conn:
            return conn.execute("SELECT name, tvg_id, url FROM channels_archive ORDER BY name ASC").fetchall()

    def get_archive_url_and_name(self, channel_id):
        with self._get_connection() as conn:
            res = conn.execute('''SELECT url, name FROM channels_archive WHERE tvg_id = ? OR name = ? 
                                  OR tvg_id = (SELECT m3u_tvg_id FROM channel_aliases WHERE epg_channel_id = ?)''', (channel_id, channel_id, channel_id)).fetchone()
            return res if res else (None, None)

    def get_active_timers(self):
        with self._get_connection() as conn:
            return conn.execute("SELECT id, title, channel_name, start_time, end_time, status, file_format, is_archive, audio_track, night_mode, source_list FROM timers ORDER BY start_time ASC").fetchall()

    def get_timer_details(self, t_id):
        with self._get_connection() as conn:
            return conn.execute("SELECT channel_name, channel_url, start_time, end_time, file_format, title, is_archive, audio_track, night_mode, source_list FROM timers WHERE id = ?", (t_id,)).fetchone()

    def delete_timer(self, timer_id):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM timers WHERE id = ?", (timer_id,))
            conn.commit()

    def clear_completed_timers(self):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM timers WHERE status = 'Zakończono'")
            conn.commit()

    def update_timer_details(self, timer_id, new_title, new_start, new_end, new_audio, new_night_mode):
        with self._get_connection() as conn:
            conn.execute("UPDATE timers SET title = ?, start_time = ?, end_time = ?, audio_track = ?, night_mode = ? WHERE id = ?", (new_title, new_start, new_end, new_audio, new_night_mode, timer_id))
            conn.commit()

    def get_autotimers(self):
        with self._get_connection() as conn:
            return conn.execute("SELECT id, keyword, channel_id, start_hour, end_hour, start_date, end_date, exclude_word FROM autotimers").fetchall()

    def delete_autotimer(self, at_id):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM autotimers WHERE id = ?", (at_id,)); conn.commit()

    def update_timer_status(self, t_id, status):
        with self._get_connection() as conn:
            conn.execute("UPDATE timers SET status = ? WHERE id = ?", (status, t_id)); conn.commit()

    def set_channel_alias(self, m3u_id, epg_id):
        with self._get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO channel_aliases (m3u_tvg_id, epg_channel_id) VALUES (?, ?)", (m3u_id, epg_id)); conn.commit()

    def get_alias_for(self, m3u_id):
        with self._get_connection() as conn:
            res = conn.execute("SELECT epg_channel_id FROM channel_aliases WHERE m3u_tvg_id = ?", (m3u_id,)).fetchone()
            return res[0] if res else None