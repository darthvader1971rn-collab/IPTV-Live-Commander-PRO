📝 Instrukcja Instalacji - IPTV Live Commander PRO
Witaj! Ten krótki poradnik przeprowadzi Cię przez proces instalacji nagrywarki krok po kroku. Nie musisz być informatykiem – przygotowaliśmy automatyczne skrypty, które zrobią najtrudniejsze rzeczy za Ciebie.

📦 ETAP 1: Przygotowanie systemu (Zrób to tylko raz!)
Zanim uruchomisz nagrywarkę, Twój komputer potrzebuje dwóch darmowych narzędzi:

1. Zainstaluj język Python
Wejdź na stronę python.org i pobierz najnowszą wersję dla Windows.

Uruchom instalator.

🛑 BARDZO WAŻNE: Na samym dole pierwszego okienka instalatora MUSISZ ZAZNACZYĆ małe okienko: Add Python.exe to PATH. Jeśli tego nie zrobisz, program nie zadziała!

Kliknij "Install Now" i poczekaj do końca.

2. Pobierz silnik FFmpeg
Pobierz darmową paczkę FFmpeg dla Windows (w formacie .zip).

Kliknij na pobrany plik prawym przyciskiem myszy i wybierz "Wyodrębnij wszystkie...".

Wypakuj ten folder w bezpieczne miejsce, np. bezpośrednio na dysk C:\FFmpeg. Nie musisz niczego instalować, po prostu niech tam sobie leży.

3. Zainstaluj VLC (Opcjonalnie)
Jeśli chcesz mieć podgląd kanałów po dwukrotnym kliknięciu, zainstaluj darmowy VLC Media Player ze strony videolan.org (instalacja standardowa - po prostu klikaj "Dalej").

🚀 ETAP 2: Błyskawiczna instalacja programu
W folderze z tym plikiem tekstowym masz zestaw skryptów. Wykonaj te dwa proste kroki:

Kliknij dwukrotnie plik instaluj_wtyczki.bat

Otworzy się czarne okienko, które samo ściągnie z internetu brakujące klocki do programu. Poczekaj, aż okienko zniknie.

Kliknij dwukrotnie plik dodaj_ffmpeg_path.pyw

Otworzy się mały instalator. Kliknij "Przeglądaj..." i wskaż folder bin, który znajduje się wewnątrz wypakowanego wcześniej folderu FFmpeg (np. C:\FFmpeg\bin).

Kliknij niebieski przycisk "DODAJ DO SYSTEMU". Gotowe! Windows już wie, jak nagrywać.

⚙️ ETAP 3: Pierwsze uruchomienie
Uruchom główny program, klikając dwukrotnie plik commander.py (lub commander.pyw).

W górnej części okna (Konfiguracja) wklej swoje dane:

M3U Kccc (Live): Link do Twojej listy kanałów na żywo.

M3U OtoPay (Arch): Link do listy archiwum.

EPG: Link do przewodnika telewizyjnego (np. plik .xml lub .gz).

Zapis: Wpisz nazwę folderu, gdzie mają wpadać filmy (np. Moje_Nagrania). Program sam założy ten folder!

Kliknij duży przycisk "ZAPISZ I SYNC".

Poczekaj chwilę – na dole w czarnym okienku logów zobaczysz, jak program ładuje kanały i układa listę EPG.

GOTOWE! Od teraz jesteś mistrzem nagrywania! 🎉

💡 Triki dla zaawansowanych (Warto wiedzieć!)
Brak dźwięku na kanale? Kliknij prawym przyciskiem myszy na problematyczny kanał na liście po lewej i wybierz "Ustaw domyślne audio dla kanału...". Zmień np. na Ścieżkę 1. Program zapamięta to na zawsze!

Zmiana zdania (Noc/Teraz): Zadania z OtoPay domyślnie pobierają się w nocy (żeby nie mulić internetu). Chcesz obejrzeć film od razu po emisji? Zaznacz go w kolejce prawym przyciskiem i wybierz "Przełącz tryb Archiwum (Noc / Teraz)".

Ratowanie sytuacji (W locie): Film już leci, a Ty zapomniałeś go dodać? Kliknij go z listy Arch, daj prawy przycisk w kolejce i wybierz "Konwertuj na Live i nagrywaj natychmiast".

Grupowe działanie: Jeśli przytrzymasz klawisz CTRL na klawiaturze, możesz zaznaczyć wiele zadań na raz. Wtedy kasowanie, startowanie czy zmiana statusu załatwi wszystkie wybrane filmy za jednym kliknięciem!