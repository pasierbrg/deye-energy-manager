# Changelog

## 0.7.6

### Poprawki po audycie

- Uzupełniono `services.yaml` o brakujące usługi AI (`save_ai_settings`, `save_ai_analysis`, `clear_ai_history`) i ujednolicono nazwy oraz opisy usług na język polski.
- Dodano kontrolowaną walidację JSON w usługach przyjmujących dane z karty (`save_ai_settings`, `save_ai_analysis`, `apply_schedule_patch`, `save_tariff_settings`, `save_future_plan`). Nieprawidłowy JSON lub nieoczekiwany typ danych zwraca czytelny błąd zamiast nieobsługiwanego wyjątku.
- Dodano testy regresji walidacji JSON i schematów usług.
- Ujednolicono wymagane encje w kreatorze mapowania (`config_flow.py`) oraz diagnostyce. Dla pełnego sterowania wymagane są teraz: tryb pracy Deye, maksymalna moc sprzedaży, prąd rozładowania, prąd ładowania, prąd ładowania z sieci oraz bieżący SOC baterii. Cena sprzedaży pozostaje warunkiem wyłącznie dla `Selling First`.
- Diagnostyka pokazuje osobno `required_entities_complete` oraz oznacza, czy encja została wybrana ręcznie, czy jest domyślną.
- Uporządkowano `_async_tick_impl` tak, aby powiadomienie o zmianie statystyk sprzedaży było wysyłane niezależnie od ścieżki sterowania, bez ryzyka pominięcia przy wcześniejszym `return`.
- Usługa `apply_settings` obsługuje opcjonalny parametr `grid_charge_current`. Po pominięciu używana jest wartość domyślna; dodatnia wartość nie włącza automatycznie Grid Charge, jest wyłącznie limitem prądu.
- Naprawiono formularz **Ustawienia normalnej pracy**: pole `tou_soc` jest zawsze edytowalne, a wybór trybu fizycznego nie powraca do `Zero Export To Load`. Wartości są odczytywane kolejno z: szkicu użytkownika, zapisanego profilu w atrybutach `manager_status`, stanu encji. Przy braku wartości wyświetlany jest pusty placeholder wymagający świadomego wyboru. Zapisanie pustego pola jest odrzucane, a brakujące `tou_soc` nie jest automatycznie uzupełniane jako 100 ani jako inna wartość SOC.
- Usługa `save_normal_profile` akceptuje teraz częściowe aktualizacje: zmiana tylko trybu fizycznego przez encję `select.normal_profile_mode` nie nadpisuje pozostałych parametrów szablonu.
- Etap 5.1: naprawiono synchronizację formularza **Ustawienia normalnej pracy**. Wartości `null`/`undefined`/pusty ciąg dla `tou_soc` nie są już konwertowane na `0`. Wprowadzono stan oczekujący `_normalProfilePending` przechowujący wartości wysłane do backendu; formularz pokazuje je do czasu potwierdzenia przez atrybut `normal_profile` w `sensor.manager_status`. Otwarte okno ustawień synchronizuje kontrolki przy aktualizacjach `hass`, nie nadpisując aktywnego szkicu użytkownika. Wybór `Zero Export To CT` i wpisane wartości SOC pozostają widoczne po zapisie, a stary stan encji pomocniczej nie ma już pierwszeństwa.

### Etap 5.2 — naprawa profili trybów i kopiowania ustawień Charge

- Zachowano definicje czterech encji pomocniczych profili (`charge_profile_*`, `normal_profile_*`) ze stabilnymi `unique_id`; ich brak lub wyłączenie w rejestrze encji nie blokuje zapisu profilu przez dedykowane usługi backendu.
- Zapis **Ustawień ładowania** nie jest już blokowany przez brakujące encje pomocnicze; karta wywołuje wyłącznie `deye_energy_manager.save_charge_profile` i pokazuje stan oczekujący do potwierdzenia przez `manager_status.attributes.charge_profile`.
- Formularz **Ustawień normalnej pracy** odczytuje dane w kolejności: szkic użytkownika, stan oczekujący, `manager_status.attributes.normal_profile`, encja pomocnicza. Stara lub brakująca encja nie nadpisuje potwierdzonego profilu.
- Przy pierwszym przełączeniu slotu na tryb `Charge` kopiowany jest pełny aktualny szablon Charge: `grid_charge_enabled`, `charge_current`, `discharge_current`, `grid_charge_current` i `target_soc`.
- W oknie slotu `Charge` dodano przycisk **Wczytaj ponownie ustawienia ładowania**, który przez `apply_schedule_patch` z flagą `force_copy_charge_profile` ponownie wczytuje szablon tylko do tego slotu.
- Istniejące sloty `Charge` nie są automatycznie nadpisywane po zmianie szablonu ładowania.
- Bezpośrednia edycja pojedynczej encji pomocniczej normalnego profilu zapisuje cały profil, nie zerując pozostałych pól.
- Rewizja karty JavaScript: `v=11`.
- W polu statusu karta wyświetla teraz `Normalna Praca` zamiast `Zero Export To Load` / `Zero Export To CT` dla aktywnych slotów zero export.
- Dla trybu `Normalna Praca` dodano styl wizualny w kolorze `#4dabf7` (pill, legenda, kafelek statusu, pasek decyzji).

### Etap 5.2.1 — bezpieczna obsługa wyłączonych encji profili

- Usunięto automatyczne ponowne włączanie encji pomocniczych profili: usunięto `_ensure_profile_entities_enabled`, `_attr_entity_registry_enabled_default = True` z klasy bazowej oraz `async_migrate_entry`.
- Przywrócono `MINOR_VERSION = 14` w `config_flow.py`, ponieważ migracja nie była konieczna.
- Integracja nie zmienia `disabled_by` żadnej encji w rejestrze; użytkownik zachowuje pełną kontrolę nad wyłączonymi encjami.
- Brak lub wyłączenie pomocniczych encji profili nie blokuje zapisu, odczytu ani kopiowania szablonów Charge — źródłem prawdy pozostają usługi backendu i atrybuty `manager_status`.

### Etap 5.3 — panel przepływu energii

- Zastąpiono klasyczny panel statusu nowym wizualnym diagramem przepływu energii z węzłami PV, falownika, baterii, sieci i domu.
- Dodano opcjonalne mapowanie szczegółowych encji: PV1/PV2 (moc, napięcie, prąd), fazy sieci L1-L3, dzienne import/eksport energii, częstotliwość obciążenia, temperaturę falownika.
- Panel wyświetla dokładnie takie same dane jak na docelowym zdjęciu: sumy PV, szczegóły stringów, napięcia faz, temperaturę baterii, dzienne ładowanie/rozładowanie baterii oraz import/eksport z sieci.
- Środkiem panelu jest inline SVG falownika Deye z wyświetlaczem i temperaturą.
- Linie przepływu są łukowate, kolorowe i animowane kulkami; kierunek zmienia się dynamicznie wraz ze zmianą kierunku energii.
- Dodano legendę sześciu kierunków przepływu oraz dolny pasek z czterema kafelkami: Decyzja managera, Aktywny slot, Tryb pracy (Manager), Tryb Deye.
- Panel aktualizuje wartości dynamicznie bez pełnego rerenderu.
- Poprawiono nazwy encji w karcie JS na zgodne z managerem (`battery_bms_voltage`, `daily_energy_bought`, `daily_energy_sold`).
- Rewizja karty JavaScript: `v=13`.

### Etap 5.3.1 — poprawki layoutu i fazy obciążenia domu

- Przepisano layout panelu **Status energii** na układ siatkowy: PV lewy górny, sieć lewy dolny, falownik centralny, bateria prawy górny, dom prawy dolny.
- Zmieniono położenie legendy przepływów — znajduje się teraz bezpośrednio pod grafiką falownika.
- Dodano opcjonalne mapowanie encji fazowych obciążenia domu: `load_l1_power`, `load_l2_power`, `load_l3_power`.
- Usunięto częstotliwość sieci i temperaturę falownika z kafelka domu — temperatura wyświetla się wyłącznie pod centralnym falownikiem.
- Poprawiono formatowanie wartości mocy: brak podwójnych jednostek i czytelniejsze wartości główne.
- Ujednolicono źródło trybu Deye — odczyt z encji `select.deye_inverter_system_work_mode` zamiast z sensora `current_work_mode`.
- Zaktualizowano dynamiczną aktualizację linii przepływu do nowych ścieżek i markerów SVG.
- Wprowadzono skalowanie całego panelu **Status energii** względem bazowej szerokości 1500 px: panel zachowuje stały układ desktopowy na każdej szerokości (1920, 1366, 768, 430, 390, 320 px) i jest proporcjonalnie pomniejszany bez przechodzenia na układ pionowy, bez ukrywania linii ani legendy.
- Rewizja karty JavaScript: `v=14`.

### Etap 5.3.2 — dopasowanie 1:1 do zdjęcia referencyjnego nr 2

- Zmniejszono bazowy rozmiar panelu do **1320 × 570 px**; panel nie jest już automatycznie powiększany powyżej skali 1.
- Wprowadzono skalowanie `scale = Math.min(1, availableWidth / 1320)` z zachowaniem stałego układu desktopowego na komputerze, tablecie i telefonie.
- Wyśrodkowano panel (`max-width: 1320px`, `margin: 0 auto`) i dynamicznie dostosowano wysokość kontenera do `570 × scale`.
- Zastąpiono linie przepływu nowymi, gładkimi, symetrycznymi łukami bez dużych grotów; dodano małe przesuwające się kropki na aktywnych liniach.
- Dodano wartości mocy przy liniach przepływu (PV, bateria, sieć, dom) w kolorach odpowiednich linii.
- Narysowano nowe ikony SVG dla kafli: PV (słońce + panele), Sieć (słup energetyczny), Bateria (zielona bateria z błyskawicą), Dom (niebieski kontur domu).
- Poprawiono wygląd centralnego falownika Deye (jasna obudowa, zaokrąglone rogi, niebieski obrys, czarny ekran, trzy zielone kontrolki, cień).
- Uporządkowano środek panelu: odległości, długości linii, położenie legendy i wartości mocy.
- Dolny pasek z czterema sekcjami otrzymał pionowe separatory, większe ikony i wyraźniejszy podział.
- Usunięto wszystkie media queries zmieniające układ panelu na pionowy lub ukrywające linie.
- Rewizja karty JavaScript: `v=16`.

### Etap 5.3.3 — poprawki panelu Status energii

- Wprowadzono pełne odświeżanie wszystkich danych szczegółowych panelu **Status energii** co 5 s (mocy, napięć, prądów, temperatur, dziennych sum, sprzedaży) bez pełnego rerenderu.
- Poprawiono wyświetlanie SOC — duża wartość procentowa z przygaszonym `% SOC` obok.
- Zastąpiono skaczące kropki na liniach przepływu płynną animacją `stroke-dashoffset`; kierunek zmienia się bez zerwania animacji, a linie bez przepływu pozostają ciągłe i przygaszone.
- Usunięto wartości mocy wyświetlane nad liniami przepływu.
- Usunięto legendę sześciu kierunków spod grafiki falownika; w jej miejscu pojawił się kafelek **Sprzedano dzisiaj** z wartością i energią.
- Usunięto napis **Falownik Deye** spod grafiki falownika; pozostawiono samą temperaturę.
- Poprawiono kafelek **Decyzja managera** — usunięto linię `Deye:`, dodano uzasadnienie decyzji z sensora `decision_reason`.
- Ujednolicono kolory trybów w kafelkach statusu z paletą harmonogramu: Sprzedaż — zielony, Normalna Praca — niebieski, Ładowanie — pomarańczowy, Wyłączono/Brak danych — szary.
- Potwierdzono, że kafelek **Tryb Deye** czyta nazwę trybu z encji `select.deye_inverter_system_work_mode` i wyświetla ją w kolorze zgodnym z trybem.
- Zagęszczono kompozycję panelu: zmniejszono paddingi i marginesy, nie zmieniając bazowego rozmiaru 1320 × 570 px.
- Rewizja karty JavaScript: `v=17`.

### Etap 5.3.4 — poprawki layoutu, ikon i skalowania dashboardu

- Poprawiono kafelek **Sprzedano dzisiaj** — energia i wartość wyświetlają się w jednym wierszu jako `kWh / PLN`.
- Zwężono kafle **PV**, **Bateria**, **Sieć** i **Dom** do 230 px, zmniejszając pustą przestrzeń bez utraty czytelności.
- Dostosowano długości i pozycje linii przepływu do nowej, zwężonej siatki kafli.
- Usunięto zbędny wiersz **Razem:** z kafla PV.
- Zastąpiono cztery główne ikony nowymi, bardziej czytelnymi SVG: słońce z panelami (PV), słup energetyczny (Sieć), bateria z błyskawicą (Bateria), dom z dachem i drzwiami (Dom).
- Wprowadzono wspólny, nadrzędny kontener skalujący dla całego dashboardu; wszystkie sekcje (Status energii, ceny, Solcast, harmonogram, statystyki) mają teraz jedną wspólną maksymalną szerokość i są wyśrodkowane.
- Zastosowano wspólne skalowanie całego dashboardu na telefonie: `scale = Math.min(1, availableWidth / 1152)`, bez poziomego przewijania całej karty i bez przełączania układu na pionowy.
- Naprawiono kafelek **Tryb Deye** — wyświetla oryginalną fizyczną wartość z `select.deye_inverter_system_work_mode` (np. `Selling First`, `Zero Export To Load`, `Zero Export To CT`), bez tłumaczenia na tryb managera.
- Rewizja karty JavaScript: `v=18`.

### Etap 5.3.5 — poprawki dialogów i wyrównania sekcji

- Przeniesiono overlay/dialogi poza `.dashboard-scaler`, dzięki czemu `position: fixed; inset: 0` odnosi się do viewportu, a nie do przeskalowanego kontenera.
- Dialogi nie są już skalowane razem z dashboardem i otwierają się na środku aktualnie widocznego ekranu.
- Dodano jawne zapisywanie pozycji przewijania strony przed otwarciem dialogu i przywracanie jej po zamknięciu.
- Wyrównano zewnętrzne krawędzie wszystkich głównych sekcji dashboardu: **Status energii**, **Ceny sprzedaży/zakupu**, **Prognoza Solcast**, **Harmonogram pracy**, **Statystyki sprzedaży**.
- Zmieniono proporcje kolumn w wierszu informacyjnym na `0.80fr 0.80fr 1.40fr`, zwężając ceny i poszerzając Solcast.
- Dostosowano wewnętrzne elementy prognozy Solcast, aby wyeliminować poziome przewijanie na komputerze.
- Rewizja karty JavaScript: `v=19`.

### Etap 5.3.6 — konfigurowalny układ YAML i powrót do stabilnego skalowania (v=20)

- Przywrócono stabilny układ znany z rewizji v=17:
  - brak wspólnego skalowania całego dashboardu;
  - dialogi renderowane poza skalowanym kontenerem w osobnym hoście `.dialog-host`;
  - brak migotania okien i niechcianego przeskakiwania scrollu.
- Rozdzielono renderowanie dashboardu i dialogów:
  - `renderDialogOnly()` aktualizuje wyłącznie treść dialogu bez pełnego rerenderu całej karty;
  - `bindDashboardControls()` i `bindDialogControls()` obsługują osobno zdarzenia dashboardu i okien modalnych;
  - dialogi zachowują focus i pozycję przewijania podczas przełączania zakładek.
- Dodano konfigurowalny układ YAML (`config.layout`) z pełną walidacją i domyślnymi wartościami:
  - tryby `layout_mode`: `auto`, `full`, `section`, `single`, `grid`, `fit`;
  - szerokość dashboardu `dashboard_width` (domyślnie 1280 px);
  - widoczność sekcji `sections` oraz wyboru pojedynczej sekcji `section`;
  - ustawienia mobilne `mobile` z własnym breakpointem, trybem, przewijaniem i liczbą kolumn;
  - proporcje górnego rzędu informacyjnego: `prices_ratio` (0.80), `buy_prices_ratio` (0.80), `solcast_ratio` (1.40);
  - parametry panelu Status energii: `energy_tile_width` (230), `energy_tile_gap` (28), `inverter_scale` (1), `flow_animation_speed` (6);
  - opcje `max_scale` i `min_scale` są odczytywane przez `layoutConfig()`, ale obecnie nie wpływają na renderowanie (zarezerwowane na przyszłość).
- Panel **Status energii** został całkowicie sparametryzowany:
  - szerokość kafli, odstępy, skala invertera oraz prędkość animacji przepływów pochodzą z `effectiveLayout()`;
  - ścieżki SVG przeliczane są dynamicznie dla każdej kombinacji `energy_tile_width`, `energy_tile_gap` i `inverter_scale`;
  - `scaleFlowPanel()` odczytuje rzeczywistą bazową szerokość z atrybutu `data-base-width`;
  - `updateFlowLines()` odczytuje geometrię z atrybutów `data-tile-width`, `data-tile-gap`, `data-inverter-width`.
- Zachowano dobre zmiany z v18/v19: nowe ikony SVG, zwężone kafle 230 px, brak wiersza Razem, kafel Sprzedano dzisiaj, surowy Tryb Deye, pełne odświeżanie co 5 s, płynne animacje przepływów, brak legendy/wartości nad liniami, wyrównane sekcje i proporcje kolumn 0.80/0.80/1.40.
- Zaktualizowano dokumentację: `README.md`, `INSTALL_PL.md`, `dashboard/energy_manager.yaml` i `CHANGELOG.md` z pełnym opisem konfiguracji układu i przykładami.
- Dodano testy regresji dla layoutu, dialog host, `renderDialogOnly`, dynamicznej geometrii panelu energii oraz synchronizacji kopii karty JS.
- Testy: `197/197` jednostek przechodzi; `node --check` poprawne dla obu kopii JS; obie kopie są identyczne.
- Rewizja karty JavaScript: `v=20`.

### Bezpieczeństwo

- Naprawiono regresję, która przy Stop Sell, zatrzymaniu awaryjnym i części błędów ustawiała `Max Sell Power` oraz prąd rozładowania na `0`.
- Wszystkie ścieżki zatrzymania i błędów korzystają teraz ze wspólnego stanu powrotu opartego 1:1 na ustawieniach domyślnych użytkownika: trybie, mocy sprzedaży oraz prądach rozładowania, ładowania i ładowania z sieci.
- Usunięto przejściowe zerowanie parametrów i wymuszanie `Zero Export To Load`. Docelowy tryb jest ustawiany dopiero po zapisaniu i potwierdzeniu wartości liczbowych.
- Błąd w połowie operacji przywraca logiczny harmonogram i pełne ustawienia domyślne. `Zero Export To CT`, `Zero Export To Load` i `Selling First` nie są wzajemnie zastępowane.
- Dodano weryfikację odczytu trybu, mocy i wszystkich trzech prądów oraz diagnostykę krytycznego błędu częściowego zapisu.
- Brakujący lub nieprawidłowy SOC albo cena są błędem tylko aktywnego slotu `Selling First`, gdy ma ustawiony odpowiedni warunek. Prawidłowy odczyt poniżej progu jest zwykłym wstrzymaniem sprzedaży, bez `SCHEDULE APPLY ERROR`, bez ponawiania zapisu i bez blokowania slotów `Zero Export`.
- Zapisy ustawień falownika są serializowane.
- Wielopolowe aktualizacje są serializowane; wartości liczbowe są zapisywane i potwierdzane przed ustawieniem wybranego trybu docelowego.
- Błąd mapowania ponad 6 zakresów zatrzymuje operację i stosuje 1:1 pełne ustawienia domyślne użytkownika.
- Dodano zakresy walidacji dla mocy, prądów, SOC i cen.
- Zatrzymanie awaryjne przełącza sterowanie w zatrzaśnięty tryb `Stop Sell`.
- Dla zapisu aktywnego slotu odczyty kontrolne są wykonywane po 0,5, 1 i 2 sekundach, z limitem oczekiwania 12 sekund. W tym czasie transakcja nie jest ponawiana, ustawienia domyślne nie są przedwcześnie przywracane, a diagnostyka pokazuje etap oraz wartości oczekiwane i odczytane.
- Dodano walidację fizycznych encji Deye Time Of Use oraz świadomy przycisk/usługę `resume_manager` („Włącz Manager i harmonogram”). Włącza `Schedule` i Scheduler, lecz nie zmienia flagi `Grid` w żadnym slocie.
- Pole **Ładowanie z sieci** jest jedyną zgodą na Deye Grid Charge: wartość `nie` zawsze zapisuje wyłączony Grid Charge, także w trybie `Charge`; `charge_current` pozostaje limitem całkowitego ładowania baterii, a `grid_charge_current` limitem ładowania z sieci.
- **Ustawienia ładowania** działają jako szablon kopiowany przy wyborze trybu `Charge`. Każdy slot zachowuje późniejsze ręczne zmiany prądów, docelowego SOC oraz zgody na ładowanie z sieci; ponowny zapis szablonu nie nadpisuje istniejących slotów.
- Okno slotu pokazuje jedno kontekstowe pole SOC: minimalny SOC sprzedaży dla `Selling First`, fizyczny SOC Deye TOU dla Zero Export lub docelowy SOC dla `Charge`. Znaczenia logiczne i fizyczne pozostają rozdzielone w backendzie.
- Przywrócono bezpośrednią edycję sześciu fizycznych zakresów w zakładce **Deye Time Of Use** z ostrzeżeniem, że mapowanie harmonogramu może je później nadpisać.
- Usunięto aktywny przełącznik `charge_scheduler_enabled` z logiki sterowania. Parametry falownika wynikają z aktywnego slotu.
- Po błędzie tego samego aktywnego slotu ustawienia domyślne są stosowane tylko raz; kolejna próba wymaga zmiany encji, harmonogramu, slotu albo świadomego wznowienia Managera.

### Harmonogram

- Dodano usługę `apply_schedule_patch` do atomowych operacji zbiorczych.
- Edycja zbiorcza i zastosowanie sugestii korzystają z jednej operacji backendowej.
- Tryb `Charge` nie jest zgodą na Grid Charge; jedyną zgodę określa pole **Ładowanie z sieci** zapisane w konkretnym slocie. Profil Charge jest tylko szablonem wartości początkowych.
- Tabela harmonogramu ponownie pokazuje zapisane wartości **Ładowanie z sieci** i **Prąd ładowania z sieci** dla każdego aktywnego slotu; dopiero mapowanie fizyczne ogranicza Grid Charge do trybu `Charge` z wartością `TAK`.
- Okno pojedynczego slotu udostępnia trzy logiczne tryby (`Selling First`, `Normalna Praca`, `Charge`) i komplet ręcznie edytowalnych parametrów. Jedno pole SOC zmienia znaczenie zależnie od trybu bez łączenia `minimum_sell_soc` z fizycznym `tou_soc`.
- Nieudana aktualizacja przywraca logiczną konfigurację slotów.

### Dane i konfiguracja

- Profil **Ustawienia ładowania** jest zapisywany jako jeden atomowy rekord i odtwarzany w całości po zamknięciu karty oraz restarcie Home Assistant. Formularz ma awaryjny odczyt zapisanego profilu z atrybutów statusu managera, jeśli pomocnicza encja nie opublikowała jeszcze stanu. Błąd walidacji lub zapisu zachowuje ostatni poprawny profil.
- Dodano Options Flow do późniejszej zmiany mapowania encji.
- Dodano konfigurowalne sensory mocy PV, domu i baterii.
- Bieżący dzień pokazuje realizację prognozy; trafność jest liczona po zamknięciu dnia.
- Duże atrybuty historii oznaczono jako niewymagające zapisu w Recorderze.
- Rozdzielono realizację bieżącego dnia od trafności zakończonych dni.
- Trafność pokazuje średnią, ostatni zamknięty dzień i liczbę dni, a korekta historyczna jest ograniczana do bezpiecznego zakresu.
- Dodano próbki pięciominutowe z jawnym oznaczeniem brakujących danych oraz archiwa 90 dni / 24 miesiące / 5 lat / miesięczne bez limitu.
- Dodano pomocniczą prognozę godzinową i dzienną `weather.*`, domyślnie `weather.forecast_home_2`; dane są pobierane przez `weather.get_forecasts`, a brak prognozy dziennej może zostać podsumowany z dostępnych próbek godzinowych.
- Dodano wersjonowany katalog profili PGE, Tauron, Enea, Energa i Stoen, obejmujący dostępne taryfy gospodarstw domowych oraz profil własny.
- Katalog jest sprawdzany przy starcie i co 7 dni, walidowany przed zapisaniem oraz przechowywany jako ostatnia poprawna kopia; dostępne są też ręczne odświeżenie i ręczne stawki awaryjne.
- Profile taryfowe uwzględniają strefy godzinowe, zmiany sezonowe, weekendy i polskie święta, a AI porównuje pełną cenę zakupu z dystrybucją dla dziś i jutra.
- Próbki uczenia są oznaczane operatorem, taryfą, strefą, rodzajem dnia, sezonem i wersją katalogu.
- Dodano konfigurację kierunku znaku mocy sieci i baterii.
- Options Flow przebudowano na pięcioetapowy kreator mapujący wyłącznie encje, z polskimi nazwami, instrukcjami, podpowiedziami automatycznymi i końcową walidacją.

### Karta i UX

- Pole statusu karty tłumaczy `SELL BLOCKED` jako **Sprzedaż zatrzymana**; pełna przyczyna pozostaje widoczna jako decyzja managera.
- Rozdzielono `minimum_sell_soc` od fizycznego `tou_soc`: minimalny SOC jest wyłącznie warunkiem `Selling First`, a do Deye TOU trafia niezależny SOC zapisany w konkretnym slocie, w tym docelowy SOC slotu `Charge`.
- Migracja nie zastępuje brakującego fizycznego `tou_soc` minimalnym SOC sprzedaży ani `0`; wymagające potwierdzenia sloty blokują zapis mapowania przed pierwszą zmianą w Deye.
- Przywrócono świadomą, bezpośrednią edycję fizycznego Deye Time Of Use. Karta ostrzega, że późniejsze zastosowanie mapowania Harmonogramu pracy może nadpisać te wartości.
- Wprowadzono logiczny tryb harmonogramu **Normalna Praca**, który w backendzie mapuje się na fizyczny `Zero Export To Load` lub `Zero Export To CT`; selektor slotów pokazuje teraz tylko trzy tryby: `Selling First`, `Normalna Praca` i `Charge`.
- Dodano szablon **Ustawienia normalnej pracy** (fizyczny tryb Deye, moc sprzedaży, prądy, SOC TOU) kopiowany do slotu przy jego pierwszym wyborze lub przy ręcznym ponownym wczytaniu; późniejsze zmiany szablonu nie nadpisują istniejących slotów.
- Tabela harmonogramu pokazuje zgodę **Ładowanie z sieci** jako **tak** albo **nie** dla trybu `Charge`, a dla pozostałych trybów jako **nie dotyczy**; nie wyświetla błędnego stanu **brak**.
- Obie dystrybuowane kopie karty mają identyczną zawartość i rewizję zasobu `v=11`.
- Poprawiono zabezpieczanie dynamicznych wartości HTML.
- Usunięto błędnie wyświetlane encje numeryczne HTML, m.in. w nazwie strategii „Zrównoważony”.
- Dodano zakładkę `Taryfa i dystrybucja` z wyborem operatora, taryfy i trybu katalogu, jawnym przyciskiem zapisu, diagnostyką aktualizacji oraz profilem 48h dla dziś i jutra.
- Sensory proxy reagują na zdarzenia źródłowych encji, a karta grupuje aktualizacje w jednej klatce animacji i nie przelicza ciężkich wykresów przy każdej zmianie mocy.
- Zmienione wartości są krótko sygnalizowane wizualnie bez tworzenia sztucznych odczytów.
- Uporządkowano działanie ustawień inteligentnego optymalizatora.
- Okna ustawień i sugestii mają lepsze przewijanie, przyklejone akcje i pełnoekranowy widok mobilny.
- Przebudowano okno `Sugestie AI` zgodnie z układem nawigacyjnym: Przegląd, Proponowane zmiany, Plan na dziś, Plan na jutro, Plan energii 48h i Jakość danych.
- Dodano rozdzielone tabele cen Dziś/Jutro, przełącznik propozycji/pełnych 24 godzin oraz jeden dynamiczny przycisk Zaznacz/Odznacz wszystkie.
- Dodano rzeczywistą symulację energii i SOC na 48 godzin, osobne wykresy dziś/jutro, pogodę pomocniczą, jakość danych i warianty Bezpieczny/Zrównoważony/Maksymalny zysk.
- Przebudowano wykresy planu dziś, jutro i 48 h: rozdzielono produkcję rzeczywistą, prognozę Solcast, prognozę skorygowaną i jej przedział oraz dodano zużycie, SOC, działania, tanią dystrybucję, pogodę godzinową, granicę dni i znacznik bieżącego czasu.
- Dodano wspólny interaktywny kursor i szczegółowy tooltip dla myszy oraz dotyku; brakujące pomiary są jawnie oznaczane jako brak danych.
- Rozbudowano kartę pogody o bieżące warunki, temperaturę, ciśnienie, wilgotność, wiatr oraz przełączane prognozy dzienną i godzinową z dokładnym źródłem i stanem aktualizacji.
- Zwiększono czytelność wykresów planu: energia i SOC mają osobne osie, legenda umożliwia ukrywanie serii, a wariant 48 h jest pokazany jako dwa osobne wykresy dobowe bez poziomego przewijania.
- Teksty osi, godziny, ikony pogody i pasy statusu przeniesiono poza skalowany SVG; usunięto dominujące pionowe linie godzinowe i pozostawiono tylko delikatne prowadnice co 6 godzin.
- Dodano osobny zsynchronizowany pasek pogody z ikoną dla każdej godziny oraz osobne pasy godzinowe sprzedaży, ładowania i taniej dystrybucji.
- Dodano datowany plan na jutro, który po ręcznym zatwierdzeniu jest zapisywany do restartu i stosowany dopiero właściwego dnia po kontroli SOC, cen i encji. Plan nie jest automatycznie zastępowany inną propozycją.
- Zaktualizowano wersjonowanie do 0.7.6.

### Jakość

- Dodano testy regresji logiki bezpieczeństwa, mapowania i kolejności zapisów.
- Usunięto śledzone pliki `__pycache__` i `.pyc`.
- Naprawiono kodowanie polskich dokumentów.
