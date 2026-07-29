# IMPLEMENTATION 0.7.7

## Punkt bazowy

- Źródło tylko do odczytu: `C:\Users\rafal\Documents\Codex\0.7.6`
- Folder roboczy: `C:\Users\rafal\Documents\Codex\0.7.7`
- Utworzenie folderu roboczego: kompletna kopia źródła wraz z plikami ukrytymi i katalogiem `.git`.
- Commit bazowy źródła: `20221dd18fa468cd863ac63a4c4829c5827e482c`
- Commit początkowy folderu roboczego: `20221dd18fa468cd863ac63a4c4829c5827e482c`
- Gałąź początkowa: `main`
- `origin/main`: `20221dd18fa468cd863ac63a4c4829c5827e482c`
- `git status --short` źródła przed kopiowaniem: czysty.
- `git status --short` folderu roboczego po kopiowaniu: czysty.
- Porównanie: po wykluczeniu `.git` oba katalogi miały po 116 plików; porównanie SHA-256 wszystkich względnych ścieżek wykazało 0 różnic.
- Zastane zmiany w `0.7.7`: brak; folder został utworzony jako identyczna kopia.
- Folder `0.7.6` po utworzeniu i weryfikacji kopii: czysty i niezmieniony.

## Audyt stanu 0.7.6/0.7.7

Stan aplikacji przed wdrożeniem:

- wersja integracji: `0.7.6`;
- rewizja dwóch kopii karty: `v=23`;
- wersja schematu harmonogramu: `1`;
- wersje magazynów AI, Solcast, uczenia i próbek energii: `1`;
- istniejący lokalny planner 48 h jest deterministyczny i tylko odczytowy, ale nie spełnia pełnego kontraktu Optimizer Core 0.7.7;
- istniejący moduł taryf tworzy wspólny godzinowy profil kosztów na dziś i jutro oraz respektuje `price_includes_distribution`;
- mapowanie i kompresja TOU, transakcyjny zapis Deye, potwierdzanie i retry są kompletne i zostają zamrożone;
- główny dashboard, `renderDialogOnly()` i `.dialog-host` działają i nie należą do zakresu przebudowy;
- istniejący dialog Sugestie AI, historia AI, ustawienia AI i plan przyszły są częściowo wdrożone;
- istniejąca historia próbek mocy, historia uczenia i historia Solcast wymagają migracji, jawnych źródeł/jakości i dokładniejszych snapshotów;
- profil domu jest obecnie godzinowy 24 h, a nie 7×24;
- brakuje kompletnego rozdzielenia historycznego i prognozowanego SOC oraz rozliczania rozpoczętej godziny;
- brakuje osobnych profili użytkownika Poranna sprzedaż, Wieczorna sprzedaż i Ładowanie;
- brakuje opcjonalnego, bezpiecznego asystenta przez zewnętrzne API.

### Walidacja bazowa

- `python -B -m unittest discover -s tests -v`: 217 testów, wszystkie zaliczone.
- `node --check custom_components/deye_energy_manager/www/deye-energy-manager-card.js`: OK.
- `node --check www/deye-energy-manager-card.js`: OK.
- `git diff --check`: OK.
- obie kopie JS: identyczny SHA-256.
- PGE G12w: istnieją testy sezonowych okien, weekendów i świąt; taryfy nie będą przebudowywane.

## Macierz audytu encji i funkcji

Legenda statusu: **już kompletne**, **częściowo wdrożone**, **brakujące**, **nieaktualne**, **nie dotyczy**.

| Nazwa funkcjonalna | Oczekiwany klucz backendu | Aktualny klucz backendu | Config flow | Options flow | Frontend | Historia | Diagnostyka | Migracja | Testy | Status | Działanie 0.7.7 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Tryb pracy Deye | `work_mode_select` | ten sam | tak, wymagany | tak | tak | n/d | tak | zachowanie | szerokie | już kompletne | pozostawić |
| Maks. moc sprzedaży | `max_sell_power_number` | ten sam | tak, wymagany | tak | tak | n/d | tak | zachowanie | szerokie | już kompletne | pozostawić |
| Maks. prąd rozładowania | `discharge_current_number` | ten sam | tak, wymagany | tak | tak | n/d | tak | zachowanie | szerokie | już kompletne | pozostawić |
| Maks. prąd ładowania | `charge_current_number` | ten sam | tak, wymagany | tak | tak | n/d | tak | zachowanie | szerokie | już kompletne | pozostawić |
| Maks. prąd ładowania z sieci | `grid_charge_current_number` | ten sam | tak, wymagany | tak | tak | n/d | tak | zachowanie | szerokie | już kompletne | pozostawić |
| SOC baterii | `battery_soc_sensor` | ten sam | tak, wymagany | tak | tak | próbki | podstawowa | zachowanie | fail-closed | częściowo wdrożone | dodać źródło, jakość i ciągłość historii SOC |
| Moc PV całkowita | `pv_power_sensor` | ten sam | tak | tak | tak | próbki | podstawowa | zachowanie | częściowe | częściowo wdrożone | jakość, fallback diagnostyczny i snapshoty |
| Moc domu całkowita | `load_power_sensor` | ten sam | tak | tak | tak | próbki | podstawowa | zachowanie | częściowe | częściowo wdrożone | zachować jako priorytet, dodać walidację/fallback |
| Moc sieci | `grid_power_sensor` | ten sam | tak | tak | tak | próbki | podstawowa | zachowanie | znak testowany | częściowo wdrożone | dodać metadane jakości, bez zmian znaku |
| Moc baterii | `battery_power_sensor` | ten sam | tak | tak | tak | próbki | podstawowa | zachowanie | znak testowany | częściowo wdrożone | priorytet nad V×A, dodać kontrolę/fallback |
| Load L1 | `load_l1_power_sensor` | ten sam | tak, opcjonalny | tak | Status energii | brak szczegółowej historii | ograniczona | zachowanie | render | częściowo wdrożone | historia fazowa, fallback, jakość |
| Load L2 | `load_l2_power_sensor` | ten sam | tak, opcjonalny | tak | Status energii | brak szczegółowej historii | ograniczona | zachowanie | render | częściowo wdrożone | historia fazowa, fallback, jakość |
| Load L3 | `load_l3_power_sensor` | ten sam | tak, opcjonalny | tak | Status energii | brak szczegółowej historii | ograniczona | zachowanie | render | częściowo wdrożone | historia fazowa, fallback, jakość |
| Dzienna/całkowita energia domu | `daily_load_consumption_sensor` + nowe neutralne źródło energii | dzienny klucz istnieje | tak | tak | tak | odczyt, bez solidnego resetu/źródła | ograniczona | zachowanie + nowe pole puste | częściowe | częściowo wdrożone | zachować alias, dodać semantykę licznika i reset |
| PV1 moc | `pv1_power_sensor` | ten sam | tak | tak | tak | brak profilu stringu | ograniczona | zachowanie | frontend | częściowo wdrożone | historia/jakość stringu |
| PV2 moc | `pv2_power_sensor` | ten sam | tak | tak | tak | brak profilu stringu | ograniczona | zachowanie | frontend | częściowo wdrożone | historia/jakość stringu |
| PV3 moc | `pv3_power_sensor` | brak | brak | brak | brak | brak | brak | nowe pole puste | brak | brakujące | dodać jako opcjonalne |
| PV1 napięcie | `pv1_voltage_sensor` | ten sam | tak | tak | tak | brak | ograniczona | zachowanie | frontend | częściowo wdrożone | jakość i diagnostyka |
| PV2 napięcie | `pv2_voltage_sensor` | ten sam | tak | tak | tak | brak | ograniczona | zachowanie | frontend | częściowo wdrożone | jakość i diagnostyka |
| PV1 prąd | `pv1_current_sensor` | ten sam | tak | tak | tak | brak | ograniczona | zachowanie | frontend | częściowo wdrożone | jakość i diagnostyka |
| PV2 prąd | `pv2_current_sensor` | ten sam | tak | tak | tak | brak | ograniczona | zachowanie | frontend | częściowo wdrożone | jakość i diagnostyka |
| Energia PV | `daily_pv_production_sensor` + semantyka licznika | ten sam | tak | tak | tak | próbki dobowe | ograniczona | zachowanie | frontend | częściowo wdrożone | reset, różnica, preferencja total_increasing |
| Napięcie baterii | `battery_bms_voltage_sensor` | ten sam | tak | tak | tak | brak | ograniczona | zachowanie | frontend | częściowo wdrożone | metadane jakości i V×A tylko kontrolnie |
| Prąd baterii | `battery_current_sensor` | ten sam | tak | tak | tak | brak | ograniczona | zachowanie | frontend | częściowo wdrożone | metadane jakości i V×A tylko kontrolnie |
| Temperatura baterii | `battery_temperature_sensor` | ten sam | tak | tak | tak | brak | ograniczona | zachowanie | frontend | częściowo wdrożone | diagnostyka jakości |
| SOH baterii | `battery_soh_sensor` | brak | brak | brak | brak | brak | brak | nowe pole puste | brak | brakujące | dodać jako opcjonalne |
| Dzienna energia kupiona | `daily_energy_bought_sensor` | ten sam | tak | tak | tak | odczyt bez kompletnego rozliczenia resetu | ograniczona | zachowanie | frontend | częściowo wdrożone | licznik dobowy, reset, historia i rozliczenie |
| Dzienna energia sprzedana | `daily_energy_sold_sensor` | ten sam | tak | tak | tak | odczyt bez kompletnego rozliczenia resetu | ograniczona | zachowanie | frontend | częściowo wdrożone | licznik dobowy, reset, historia i rozliczenie |
| Dzienna energia ładowania | `daily_battery_charge_sensor` | ten sam | tak | tak | tak | odczyt bez kompletnego rozliczenia resetu | ograniczona | zachowanie | frontend | częściowo wdrożone | licznik dobowy, reset, historia i rozliczenie |
| Dzienna energia rozładowania | `daily_battery_discharge_sensor` | ten sam | tak | tak | tak | odczyt bez kompletnego rozliczenia resetu | ograniczona | zachowanie | frontend | częściowo wdrożone | licznik dobowy, reset, historia i rozliczenie |
| Grid L1/L2/L3 i napięcia | istniejące historycznie, niewymagane w 0.7.7 | istnieją | istnieją legacy | istnieją legacy | Status energii | nie dla Optimizer Core | ograniczona | zachowanie | frontend | nieaktualne dla nowego zakresu | zachować kompatybilność, nie rozbudowywać ani nie używać w plannerze |
| Częstotliwość LOAD | istniejący historyczny klucz, niewymagana | istnieje | istnieje legacy | istnieje legacy | Status energii | nie | ograniczona | zachowanie | frontend | nieaktualne dla nowego zakresu | zachować kompatybilność, nie używać w plannerze |
| Falownik AC temperatura | istniejący szczegół | istnieje | tak | tak | tak | nie | ograniczona | zachowanie | frontend | już kompletne dla UI | pozostawić |
| Ceny sprzedaży/kupna dziś/jutro | istniejące klucze | istnieją | tak | tak | tak | próbki | tak | zachowanie | planner | częściowo wdrożone | ujednolicić źródło i jakość bez nowych obowiązków |
| Solcast dziś/jutro i kolejne dni | istniejące klucze | istnieją | tak | tak | tak | jedna wersja prognozy | ograniczona | zachowanie | planner | częściowo wdrożone | snapshot initial/latest/hourly, korektor i curtailment |
| Pogoda | `weather_entity` | ten sam | tak | tak | tak | nie | ograniczona | zachowanie | frontend | częściowo wdrożone | tylko dane pomocnicze, bez przebudowy |
| Profil taryfy OSD | `tariff_context()` | istnieje | poza mapperem | poza mapperem | tak | kontekst planu | tak | zachowanie | katalog | już kompletne | zamrozić i używać jako jedyne źródło dystrybucji |
| Mapowanie TOU | `_compress_schedule_segments()` / `async_apply_time_of_use_map()` | istnieje | n/d | n/d | tak | status | tak | zachowanie | szerokie | już kompletne | zamrozić; dodać test zgodności 0.7.6 |
| Historia próbek | wersjonowany schemat historii | Store v1 | n/d | n/d | częściowo | tak | ograniczona | brak jawnej migracji | częściowe | częściowo wdrożone | schema v2, migracja bez utraty danych |
| Profil domu 7×24 | model backendu | profil 24 h | n/d | n/d | częściowo | częściowo | ogólna | brak | brak | częściowo wdrożone | zastąpić wersjonowanym 7×24 |
| Korektor PV/Solcast | model lokalny | prosty współczynnik | n/d | n/d | częściowo | częściowo | ogólna | brak | częściowe | częściowo wdrożone | lokalne uczenie, staged confidence, curtailment reject |
| Historia/prognoza SOC | osobne serie rzeczywista/prognozowana | jedna projekcja | n/d | n/d | wykres | niepełna | ogólna | brak | częściowe | częściowo wdrożone | ciągłość 24/48 h i źródło każdej godziny |
| Optimizer Core | osobny deterministyczny kontrakt | `ai_planner.py` uproszczony | n/d | n/d | uproszczony plan | częściowo | ogólna | brak | 9 testów | częściowo wdrożone | wydzielić pełny kontrakt, baseline i warianty |
| Profile użytkownika | poranna/wieczorna sprzedaż/ładowanie | brak | poza mapperem | poza mapperem | brak | brak | brak | nowe wyłączone | brak | brakujące | dodać wersjonowane ustawienia i wpływ na Core |
| Zewnętrzny asystent AI | provider abstraction | brak | poza mapperem | poza mapperem | brak | brak | brak | sekrety osobno | brak | brakujące | dodać opcjonalnie, wyłącznie doradczo |

### Wynik audytu funkcjonalnego

Już było i zostaje zachowane:

- bezpieczny zapis Deye z kolejnością, potwierdzeniem, retry i przywracaniem ustawień;
- kompresja i mapowanie maksymalnie sześciu zakresów TOU;
- moduł taryf, katalog OSD, profil ręczny i `price_includes_distribution`;
- podstawowe mapowania przepływów, SOC, cen, Solcast i pogody;
- większość opcjonalnych pól szczegółowych PV, baterii, faz LOAD i czterech liczników dobowych;
- główny dashboard, osobny host dialogów i mobilne skalowanie;
- lokalny plan 48 h, trzy uproszczone warianty, historia sugestii i ręczne zatwierdzanie.

Było częściowo i wymaga uzupełnienia:

- mapowanie opcjonalnych encji nie ma bezpiecznych pustych wartości migracyjnych ani pełnej jakości źródeł;
- tryb „Zachowaj bieżące mapowanie” przechodzi dalej zamiast zakończyć bez zmian;
- historia energii, Solcast, uczenia i SOC jest w schemacie v1;
- profil domu jest 24-godzinny, nie 7×24;
- korekta PV nie rozróżnia ograniczenia produkcji;
- planner nie ma pełnego kontraktu, baseline, rozliczenia finansowego, wartości końcowej i neutralności;
- diagnostyka nie pokazuje kompletnego źródła/fallbacku/jakości/resetów liczników;
- frontend AI ma bazowe zakładki, ale nie pełne profile i szczegóły wykonania.

Brakowało i zostanie dodane:

- PV3 Power i Battery SOH jako pola opcjonalne;
- wersjonowana migracja historii i profili;
- jednoznaczne snapshoty Solcast;
- pełny profil obciążenia 7×24;
- osobne historyczne i prognozowane SOC;
- trzy profile użytkownika, baseline, status wykonania godzin i lokalna alternatywa;
- bezpieczna, opcjonalna abstrakcja zewnętrznego AI.

## Plan etapów

1. Audyt repozytorium, punkt bazowy Git i niniejszy dokument.
2. Migracja schematu historii, snapshoty, źródła danych i jakość danych.
3. Profil zużycia domu 7×24 i lokalny korektor Solcast/PV.
4. Model magazynu oraz rzeczywisty i prognozowany SOC 24/48 h.
5. Optimizer Core, plan bazowy, trzy warianty, finanse i profile użytkownika.
6. Frontend Sugestii AI, ustawienia profili i diagnostyka.
7. Opcjonalny zewnętrzny asystent AI przez API.
8. Regresja Deye/TOU/taryf, pełne testy i audyt bezpieczeństwa.
9. Dokumentacja, wersjonowanie 0.7.7, commit, tag, push i GitHub Release.

## Dziennik etapów

### Etap 1 — audyt i punkt bazowy

- Zmienione pliki: `IMPLEMENTATION_0.7.7.md`.
- Testy wykonane: 217 testów Python — OK; oba `node --check` — OK; `git diff --check` — OK; zgodność SHA-256 obu kopii JS — OK.
- Testy niewykonane: test w działającym Home Assistant i na fizycznym falowniku — środowisko nie jest dostępne na tym etapie.
- Git diff: wyłącznie dodanie dokumentu audytowego.
- Pozostałe zadania: etapy 2–9.
- Miejsce pracy: wyłącznie `C:\Users\rafal\Documents\Codex\0.7.7`.
- Źródło `C:\Users\rafal\Documents\Codex\0.7.6`: tylko do odczytu, bez zmian.

### Etap 2 — migracja historii, źródła i jakość danych

- Zmienione pliki: `const.py`, `config_flow.py`, `manager.py`, `history.py`, `strings.json`, `translations/pl.json`, `translations/en.json`, `tests/test_history.py`, `tests/test_manager_logic.py`, `tests/test_service_validation.py`.
- Schemat: dodano aplikacyjny `schema_version=2` przy zachowaniu wersji koperty HA Store, dzięki czemu pliki 0.7.6 są najpierw odczytywane, a następnie bezstratnie migrowane.
- Migracja: zachowuje próbki, archiwa, historię AI, ustawienia, fizyczne mapowanie slotów i profile sterowania; nowe profile AI powstają wyłączone.
- Źródło LOAD: poprawny `Load Power` → komplet L1+L2+L3 → awaryjny bilans PV/sieć/bateria. Fazy nigdy nie są dodawane do poprawnego totalu.
- Bateria: bezpośrednia moc pozostaje źródłem głównym, V×A jest tylko oznaczonym fallbackiem.
- Liczniki energii: normalizacja Wh/kWh/MWh, zapis stanu między restartami, rozpoznawanie resetu i brak ujemnych delt.
- Solcast: jawne `initial_forecast_kwh`, `latest_forecast_kwh` i godzinowe snapshoty; trafność zakończonego dnia ma podstawę w prognozie początkowej.
- Mapowanie: uzupełniono wyłącznie brakujące opcjonalne PV3 Power i Battery SOH; istniejące mapowania zachowano; stare pola GRID/frequency pozostają kompatybilne w backendzie, ale nie są dokładane do kroku 0.7.7.
- „Zachowaj bieżące mapowanie”: w options flow kończy się bez autodetekcji i bez kolejnych kroków.
- Testy wykonane: pełny zestaw 231 testów — OK (217 bazowych + 14 nowych); walidacja JSON tłumaczeń — OK; `git diff --check` — OK.
- Testy niewykonane: migracja na rzeczywistym katalogu `.storage` oraz odczyty z fizycznego Deye — brak środowiska HA/falownika.
- Git diff/status: wyłącznie pliki wymienione powyżej i dokument implementacyjny; brak zmian poza `0.7.7`.
- Pozostałe zadania: etapy 3–9.
- Miejsce pracy: wyłącznie `C:\Users\rafal\Documents\Codex\0.7.7`.
- Źródło `C:\Users\rafal\Documents\Codex\0.7.6`: tylko do odczytu, bez zmian.

### Etap 3 — profil domu 7×24 i korektor PV

- Zmienione pliki: `manager.py`, `learning.py`, `tests/test_learning.py`.
- Profil domu: 168 niezależnych komórek dzień tygodnia × godzina, EWMA, ograniczanie pojedynczych wartości skrajnych, jawne fallbacki `weekday_hour` → `day_type_hour` → `hour_only`.
- Do profilu trafia wyłącznie rozstrzygnięty pomiar LOAD; przepływy baterii i sieci nie są do niego dodawane.
- PV: lokalny współczynnik miesiąc × godzina, EWMA, ograniczenie 0,4–1,6 i stopniowy wpływ do 21 próbek.
- Godziny nocne i zbyt mała prognoza nie są korygowane.
- Curtailment: rejestrowane są flagi pełnego magazynu, Zero Export, limitu eksportu, clippingu, braku sieci, starego sensora, fallbacku i ręcznego override. Takie godziny są liczone diagnostycznie, ale odrzucane z uczenia korekty Solcast.
- Historia godzinowa zapisuje lokalną datę/godzinę, prognozę initial/latest/hourly/corrected, SOC start/end, kompletność, akcję i `plan_id`.
- Status uczenia: rzeczywiste progi 0–2/3–6/7–20/21–59/60+ pełnych dni z limitami pewności 25/35/70/85/100 i blokadą zastosowania przed 7 pełnymi dniami.
- Diagnostyka backendu zawiera stan profilu PV i domu, liczniki przyjętych/odrzuconych próbek, błędy, szczyty, korekty oraz gotowość X/3, X/7, X/21, X/60.
- Testy wykonane: pełny zestaw 238 testów — OK; obejmuje 7×24, weekendy, fallback profilu, odrzucanie niepełnych godzin, curtailment, stopniową korektę i etapy uczenia.
- Testy niewykonane: długookresowe uczenie na rzeczywistych 60 dniach danych i fizyczne ograniczenie mocy falownika — brak rzeczywistego zbioru instalacji.
- Git diff/status: zmiany wyłącznie w folderze `0.7.7`; `git diff --check` bez błędów.
- Pozostałe zadania: etapy 4–9.
- Miejsce pracy: wyłącznie `C:\Users\rafal\Documents\Codex\0.7.7`.
- Źródło `C:\Users\rafal\Documents\Codex\0.7.6`: tylko do odczytu, bez zmian.

### Etap 4 — model magazynu i SOC 24/48 h

- Zmienione pliki: `battery_model.py`, `manager.py`, `tests/test_battery_model.py`.
- Przyczyna błędnej historii SOC: wcześniejszy planner tworzył jedną serię od bieżącego SOC i nie miał trwałego kontraktu łączącego zakończone godziny, punkt „Teraz” i przyszłość.
- Naprawa: `build_soc_timeline()` pobiera minione punkty wyłącznie z zamkniętych rekordów godzinowych, pozostawia lukę przy braku danych, dodaje jeden bieżący punkt i dopiero potem prognozę.
- Zmiana bieżącego SOC nie modyfikuje żadnego historycznego punktu.
- Prognoza 48 h jest sekwencyjna; `soc_start[h+1] == soc_end[h]`, również na granicy dziś/jutro.
- Każda godzina zwraca przepływy PV→dom/bateria/sieć, sieć→dom/bateria, bateria→dom/sieć, straty, energię start/end, SOC start/end, czas, limit i źródło.
- Nocne zużycie obniża SOC powyżej minimum; po dojściu do minimum przechodzi na import z sieci.
- Wartość 33,3% jest poprawnym efektywnym minimum dla 20% + dodatkowej rezerwy 4 kWh przy 30 kWh. Model zwraca jawnie twarde minimum, rezerwę i efektywne minimum.
- Sprawność 0.7.6 jest migrowana do osobnych sprawności ładowania/rozładowania przez pierwiastek, zachowując dotychczasową sprawność pełnego cyklu.
- Limit mocy jest minimum z limitu planu, eksportu, falownika, prądu×napięcia i encji Deye.
- Bieżąca godzina używa 1–60 minut pozostałych do końca godziny; energia jest ograniczona czasem, SOC i mocą/prądem.
- Brak aktualnego SOC daje wyłącznie punkty `missing` i blokadę fail-closed, bez fałszywej linii.
- Testy wykonane: pełny zestaw 250 testów — OK; obejmuje pełną historię i lukę, niezmienność historii, fail-closed, granicę północy, nocne zużycie, minimum, import, ładowanie, sprzedaż, bilans energii i częściową godzinę.
- Testy niewykonane: wizualna weryfikacja wykresu w działającym HA zostanie wykonana po etapie frontendowym; test fizycznego falownika pozostaje niedostępny.
- Git diff/status: zmiany wyłącznie w folderze `0.7.7`; `git diff --check` bez błędów.
- Pozostałe zadania: etapy 5–9.
- Miejsce pracy: wyłącznie `C:\Users\rafal\Documents\Codex\0.7.7`.
- Źródło `C:\Users\rafal\Documents\Codex\0.7.6`: tylko do odczytu, bez zmian.

### Etap 5 — lokalny Optimizer Core

- Zmienione pliki: `optimizer_core.py`, `ai_planner.py`, `history.py`, `manager.py`, `tests/test_optimizer_core.py`.
- `optimizer_core.py` jest osobnym, deterministycznym modułem bez zależności od usług Home Assistant i bez dostępu do warstwy zapisu Deye. `ai_planner.py` pozostaje zgodnym punktem wejścia dla istniejącego frontendu i testów.
- Kontrakt planu zawiera identyfikatory snapshotu i planu, wersję algorytmu i schematu, horyzont, powód przeliczenia, statusy, 48 sekwencyjnych rekordów godzinowych, przepływy energii, ceny, koszty, wynik, pewność, przyczyny i ograniczenia.
- Plan bazowy symuluje aktualny harmonogram i ustawienia użytkownika z tego samego snapshotu. Nie tworzy skrótów typu Sell OFF, moc sprzedaży 0, prądy 0 ani wyłączenie TOU.
- Warianty `safe`, `balanced` i `profit` są osobnymi symulacjami z jawnymi parametrami rezerwy, limitu mocy, progu zysku, kwantyla prognozy i docelowego SOC końcowego. Raport wskazuje, gdy dwa warianty dają identyczny wynik.
- Finanse obejmują przychód eksportu, koszt energii importowanej, koszt dystrybucji wyłącznie z istniejącego profilu taryfowego, straty, opcjonalny koszt cyklu, terminalną wartość energii i rozbicie korzyści względem baseline. Ustawienie `price_includes_distribution` eliminuje ponowne doliczenie dystrybucji.
- Próg neutralności wynosi `max(0,20 PLN, 1% wartości bezwzględnej baseline)`. Wynik mieszczący się w progu jest oznaczony „Praktycznie taki sam” i nie dostaje rekomendacji zapisu.
- Profile Poranna sprzedaż, Wieczorna sprzedaż i Ładowanie są migrowane jako wyłączone, mają wersjonowany wspólny schemat i stanowią jedynie wejście optymalizatora. Nie są bezpośrednimi poleceniami dla falownika.
- Plan jest cache’owany po stabilnym SHA-256 wejść. Samo odświeżenie UI nie przelicza Core; zmiana godziny, cen, prognozy, ustawień, profili, harmonogramu lub istotna zmiana SOC tworzy nową wersję i zachowuje maksymalnie 30 poprzednich planów.
- `simulate_alternative()` liczy jedną wybraną przyszłą godzinę i pozostały horyzont bez wykonywania zapisów.
- Brak aktualnego SOC blokuje wszystkie akcje (`blocked`, fail-closed). Propozycje mają status `planned`; Core nigdy nie nadaje `confirmed`.
- Testy wykonane: 9 dotychczasowych testów planera oraz 10 nowych testów kontraktu Core — OK; łącznie z wybranymi testami historii i managera 120/120 — OK.
- Testy niewykonane: fizyczny dispatch i potwierdzenie przez falownik — Core nie wykonuje zapisów, a środowisko Deye nie jest dostępne.
- Pozostałe zadania: etapy 6–9.
- Miejsce pracy: wyłącznie `C:\Users\rafal\Documents\Codex\0.7.7`.
- Źródło `C:\Users\rafal\Documents\Codex\0.7.6`: tylko do odczytu, bez zmian.

### Etap 6 — frontend profili i Sugestii AI

- Zmienione pliki: `manager.py`, `sensor.py`, `services.yaml`, obie kopie
  `deye-energy-manager-card.js`, tłumaczenia i testy managera/frontendu.
- Dodano wspólny formularz profili sprzedaży, formularz ładowania, walidację
  frontend/backend i atomową usługę zapisu profili. Zapis profilu nie wywołuje
  usług Deye; wyłącznie unieważnia snapshot planu.
- Przegląd pokazuje najlepszą decyzję, wynik netto, korzyść względem baseline,
  końcowy SOC, pewność, status uczenia/planu oraz wpływ profili.
- Tabela propozycji pokazuje wynik netto i szczegóły godzinowe. Zachowano
  działające `renderDialogOnly()`, `.dialog-host`, główny dashboard, harmonogram
  i Solcast.
- Testy wykonane: 70 testów frontendu oraz 124 wybrane testy backendu — OK;
  oba `node --check` — OK.
- Testy niewykonane: pomiar pikselowy w rzeczywistym HA — brak uruchomionej
  instancji w środowisku testowym.
- Miejsce pracy: wyłącznie folder `0.7.7`; źródło `0.7.6` bez zmian.

### Etap 7 — opcjonalny asystent AI przez API

- Zmienione pliki: `ai_assistant.py`, `manager.py`, `__init__.py`, `sensor.py`,
  `services.yaml`, obie kopie karty, tłumaczenia i `tests/test_ai_assistant.py`.
- Dostawcy: Gemini, OpenRouter, OpenAI, oficjalny publiczny endpoint OpenCode i
  własny endpoint zgodny z OpenAI (wyłącznie HTTPS).
- Żądanie używa JSON Schema; odpowiedź jest ponownie walidowana lokalnie.
  Timeout, pojedynczy retry dla 429/502/503 i fallback nie blokują lokalnego Core.
- Payload jest sanitizowany; brak encji, urządzeń, lokalizacji, surowej historii,
  sekretów i możliwości bezpośredniego zapisu. Integracja nie odczytuje
  lokalnych poświadczeń OpenCode i nie uruchamia powłoki.
- Automatyczna analiza jest ograniczona do jednego uruchomienia na godzinę,
  wykonywana asynchronicznie i cache’owana tylko jako zredagowany wynik.
- Testy wykonane: 9 testów asystenta i 175 wybranych testów integracyjnych — OK;
  oba `node --check` — OK.
- Testy niewykonane: płatne wywołanie produkcyjnych API bez klucza użytkownika.
- Miejsce pracy: wyłącznie folder `0.7.7`; źródło `0.7.6` bez zmian.

### Etap 8 — regresja i audyt bezpieczeństwa

- Rozszerzono testy Optimizer Core o profile jedno- i wielogodzinne, minimalną
  cenę, trzy metody dystrybucji celu, `battery_to_grid`/`total_export`, cel SOC
  i kWh, limit energii z sieci, okno przez północ, priorytety, konflikt oraz
  minimalną pewność.
- TOU i zapis Deye pozostają bez zmian: limit 6/6, kompresja po istniejących
  kryteriach, fail-closed, confirm/retry, brak zerowania parametrów i brak
  automatycznego zapisu identycznej wartości.
- Moduł taryfowy i katalog OSD nie zostały przebudowane. Optimizer otrzymuje
  gotowy profil godzinowy i respektuje `price_includes_distribution`.
- Testy wykonane: pełny zestaw 279 testów Python — OK; kompilacja Python — OK;
  oba `node --check` — OK.
- Testy niewykonane: test na fizycznym falowniku, realne 60 dni uczenia i
  wizualna sesja HA na wielu urządzeniach — brak takiego środowiska.
- Git diff/status: wyłącznie zakres 0.7.7, bez sekretów i danych użytkownika.
- Pozostałe zadania: dokumentacja, wersjonowanie, finalna walidacja i publikacja.
- Miejsce pracy: wyłącznie folder `0.7.7`; źródło `0.7.6` bez zmian.

### Etap 9 — dokumentacja, wersjonowanie i gotowość wydania

- Zmienione pliki: `README.md`, `INSTALL_PL.md`, `CHANGELOG.md`,
  `RELEASE_NOTES_0.7.7.md`, `manifest.json`, diagnostyka managera, obie kopie
  karty, banner, przykład dashboardu i testy wersjonowania.
- Wersja integracji i karty: `0.7.7`; rewizja zasobu frontendowego: `v=24`.
  Historyczne wpisy 0.7.6 i katalog taryf `2026.07.18.1` zachowano, ponieważ
  nie oznaczają bieżącej wersji aplikacji ani zmienionego katalogu.
- Dokumentacja opisuje profile, uczenie, minimalne SOC, wynik netto, istniejący
  katalog OSD, fallbacki danych, migrację, prywatność i opcjonalne API.
- Walidacja końcowa: 282 testy Python — OK; kompilacja `custom_components` i
  `tests` — OK; oba `node --check` — OK; wszystkie JSON i YAML — OK;
  `git diff --check` — OK; obie kopie JS mają identyczny SHA-256.
- Audyt sekretów nie wykrył kluczy, plików `.env`, `.pem`, `.key`, logów ani
  prywatnych danych użytkownika.
- Testy niewykonane: rzeczywisty Home Assistant/falownik, wielodniowy test
  uczenia oraz produkcyjne API bez klucza użytkownika.
- Folder źródłowy `0.7.6` ponownie zweryfikowano: branch `main`, commit
  `20221dd18fa468cd863ac63a4c4829c5827e482c`, czysty status, wersja 0.7.6 i
  rewizja karty v=23 — bez zmian.
- Repozytorium jest gotowe do commita, tagu `v0.7.7`, pushu i GitHub Release.
