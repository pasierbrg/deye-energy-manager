# Changelog

## [0.8.0] - 2026-08-30

### Solcast consistency — Etap 5H.3 SAFE

- Bieżąca realizacja prognozy używa jednego backendowego kontraktu:
  `production_today_kwh / forecast_today_kwh`, gdzie mianownikiem jest
  najnowsza pełnodniowa prognoza; wynik powyżej 100% nie jest ograniczany.
- Główna karta, Historia i dane oraz lokalny kontekst Sugestii AI odczytują te
  same jawne pola. Trafność historyczna, prognoza pozostała i prognoza jutra
  pozostają osobnymi metrykami, a brak lub stare źródło działa fail-safe.
- Optimizer Core nadal otrzymuje prognozy energii w kWh, profil godzinowy,
  historyczną korektę i historyczną trafność do wyznaczenia niepewności; nie
  używa bieżącego procentu realizacji do decyzji.
- Dodano testy kontraktowe T1–T12, w tym wynik >100%, brak/starość danych,
  rollover, oddzielenie payloadu zewnętrznego AI oraz lokalny dzień DST.
- Manifest pozostaje `0.8.0`, config minor `24`; zmiana karty podnosi rewizję
  zasobu do `v=0.8.0.44`.

### Release infrastructure / automatic Lovelace resource — Etap 5H.0 SAFE

- Bundled karta jest serwowana z domenowej ścieżki integracji, a w trybie
  UI/storage DEM idempotentnie tworzy lub aktualizuje wyłącznie własny zasób.
- Jednoznaczny legacy wpis `/local/deye-energy-manager-card.js` jest migrowany w
  miejscu. Tryb YAML pozostaje read-only, a niejednoznaczne duplikaty działają
  fail-safe bez automatycznego usuwania.
- Aktywne metadata i URL katalogu taryf wskazują kanoniczne repozytorium
  `https://github.com/pasierbrg/deye-energy-manager`.
- Kod JS nie został zmieniony: rewizja pozostaje `v=0.8.0.43`, manifest `0.8.0`,
  config minor `24`.

### Final issue fixes — Etap 5G.4K.5 SAFE

- Autodiscovery wymaga rzeczywistego dopasowania semantycznego i odrzuca
  niemożliwe jednostki/device class; opcjonalne PV3/SOH pozostają puste bez
  poprawnego kandydata, a samo słowo `deye` nie wybiera już encji.
- Runtime TOU korzysta wyłącznie z jawnych mapowań pełnych encji, bez fallbacku
  prefiksu `deye_inverter_`; brak mapowania działa fail-closed.
- Przypadkowe/legacy `0 A` w slocie Harmonogramu oznacza wartość nieustawioną i
  dziedziczy niezależny limit użytkownika, bez cofania kontraktu J.6.
- Fizyczne TOU 6/6 nie wymaga globalnego master switcha, a poprawione skalowanie
  karty zachowuje czytelny układ na obsługiwanych szerokościach.
- Tracking Solcast bez daty sam się inicjalizuje, rollover nie zamyka dnia bez
  prognozy, a postęp używa najnowszej prognozy. Parser liczb karty rozróżnia
  brak danych od zera i zachowuje scientific notation.
- Rewizja karty: `v=0.8.0.43`; manifest pozostaje `0.8.0`, config minor `24`.

### Lokalny release candidate — Etap 5H.1 SAFE

- Finalne release notes opisują automatyczny zasób Lovelace, poprawki `0 A`,
  samonaprawę historii Solcast, status issues #1/#2/#3/#5/#6/#7/#9 oraz
  pozostawienie issue #8 jako nieblokującej obserwacji runtime.
- Doprecyzowano, że Optimizer Core jest deterministyczny, zewnętrzny AI ma rolę
  doradczą, a DEM nie zastępuje zabezpieczeń sprzętowych ani konfiguracji
  falownika.
- Kod backendu i JS pozostają bez zmian; manifest `0.8.0`, config minor `24` i
  rewizja zasobu `v=0.8.0.43` nie wymagają bumpu.

### Polskie powody decyzji w UI — Etap 5G.4K.4 SAFE

- Centralny mapper prezentacyjny tłumaczy aktywne reason codes, złożone limity
  oraz dynamiczny prefiks `material_live_input_changed:*`; nieznane kody mają
  neutralny polski fallback bez ujawniania raw identyfikatora.
- Przegląd, Dlaczego ten plan, Plan i wykonanie, Powód, Ostatnia analiza i empty
  state używają tej samej warstwy tłumaczeń. Kod `empty_reason_by_day` nie jest
  już dopisywany użytkownikowi w nawiasie.
- Core, decyzje, FuturePlan, ceny, taryfy i sterowanie pozostają bez zmian.
  Rewizja karty: `v=0.8.0.42`; manifest pozostaje `0.8.0`.

### Jednoznaczny wynik modelowany — Etap 5G.4K.1 v2 SAFE

- Wszystkie prezentacje `row.net_result` nazywają tę wartość pełnym wynikiem
  ekonomicznym modelowanego slotu, dnia lub planu, z uwzględnieniem przepływów
  energii i cen. Nie jest ona przedstawiana jako zysk samej decyzji.
- Karta nie rekonstruuje delty decyzji. `row.benefit` pozostaje porównaniem
  odpowiadających sobie slotów planu i baseline, natomiast `planner.benefit`
  jest wyraźnie opisany jako porównanie całych planów.
- Reprezentatywna propozycja nadal jest wybierana chronologicznie, bez rankingu
  po `net_result`; Core, plany, ceny i taryfy pozostają bez zmian. Rewizja karty:
  `v=0.8.0.41`; manifest pozostaje `0.8.0`.

### Pełna macierz OSD/sprzedawca i standardowy BUY — Etap 5G.4K.3E v2 SAFE

- Wspólny, walidowany katalog obejmuje 33 grupy G pięciu głównych OSD oraz 21
  jednoznacznych taryf standardowych sprzedawców na 2026 r.; każda grupa ma
  jawny status wsparcia, a oferty specjalne i dynamiczne działają fail-closed.
- Przy pustych BUY Today/Tomorrow użytkownik może jawnie wybrać sprzedawcę.
  Resolver generuje kanoniczne 24+24 z ceny energii brutto i dolicza zmienny OSD
  dokładnie raz. Jawne encje BUY, w tym Pstryk all-in, zawsze mają pierwszeństwo.
- Resolver jest validity-first (również zmiana w połowie roku i przełom roku),
  a wspólny updater zachowuje last-known-good i sprawdza aktualizację co 90 dni
  lub na żądanie. Migracja 23 → 24 nie przypisuje sprzedawcy automatycznie.
- Rewizja karty: `v=0.8.0.40`; manifest pozostaje `0.8.0`.

### Prosty UX taryfy i role ekonomiczne — Etap 5G.4K.3D SAFE

- Standardowy ekran taryfy edytuje tylko operatora OSD i taryfę. Cztery
  centralne mapowania BUY/SELL są zwięzłym podsumowaniem, profil ręczny pojawia
  się tylko dla Custom/Inne, a polaryzacja i diagnostyka są zwinięte.
- `price_source` i domyślne encje providera zostały odłączone od runtime;
  zachowano je wyłącznie w deterministycznej migracji dawnych wpisów.
- Kontrakty mają walidowaną rolę ekonomiczną: Pstryk BUY
  `retail_buy_all_in`, Pstryk SELL `prosumer_sell`, RCE BUY `energy_only`, RCE
  SELL `market_reference`; Custom bez jawnej roli działa fail-closed.
- Migracja konfiguracji: minor 22 → 23. Rewizja karty: `v=0.8.0.39`.

### Real HA cleanup kanonicznych cen — Etap 5G.4K.3B.2 SAFE

- Explicit empty tworzy minimalny kontrakt `unmapped` bez aktywnego adaptera,
  schematu i pól ekonomicznych. Parser ignoruje przekazany stary stan encji,
  gdy odpowiedni centralny mapping jest pusty.
- Jednorazowa migracja minor 21 → 22 odbudowuje known-adapter metadata z
  bieżących czterech mapowań, zachowuje Custom/Inne i usuwa stale Pstryk fields.
- Trwały `optimizer_plan.canonical_prices` jest sanityzowany podczas startu.
  Invalidacja usuwa tylko wiersze zmienionego direction/day i nie dotyka
  Energy Store, historii ani niezależnego kierunku.
- UI pokazuje źródło jako derived/read-only, znane kontrakty jako diagnostykę,
  a ręczną edycję pozostawia wyłącznie Custom/Inne. Rewizja: `v=0.8.0.38`.

### Mapowanie jako jedyne źródło prawdy — Etap 5G.4K.3B.1 v2 SAFE

- Optional selector używa `suggested_value`, a nie voluptuous `default`, dzięki
  czemu brak klucza po wyczyszczeniu pola nie przywraca poprzedniej encji.
- Kontrakt ma fingerprint aktualnych mapowań i osobne auto-profile Today/Jutro.
  Zmiana encji unieważnia binding, adapter, schema i semantykę starego źródła;
  rename tej samej pozycji Entity Registry nadal zachowuje stable binding.
- Legacy selector źródła cen został odłączony od runtime authority. Znane
  adaptery Pstryk/RCE są w UI tylko diagnostyczne, a edycja zaawansowana pozostaje
  dla Custom/Inne. Migracja konfiguracji: minor 21. Rewizja karty: `v=0.8.0.38`.

### Puste mapowanie cen pozostaje puste — Etap 5G.4K.3B SAFE

- Rozdzielono brak starego klucza od świadomego wyczyszczenia selektora.
  Jawne `null`/puste mapowanie jest utrwalane, wygrywa nad kontraktem i nie
  uruchamia domyślnej encji providera, autodetekcji ani numeric state fallback.
- Config Flow zapisuje wszystkie cztery pola cen, również gdy opcjonalny
  selector pomija wyczyszczone pole. Reload, reconfigure i migracja minor 20
  zachowują `unmapped/user_unmapped` oraz usuwają nieaktualny binding/schema.
- BUY i SELL pozostają niezależne: RCE SELL działa przy pustym BUY, a Pstryk BUY
  działa przy pustym SELL. Diagnostyka karty pokazuje czytelne
  „nie skonfigurowano / usunięto w mapowaniu”. Rewizja karty: `v=0.8.0.38`.

### Uniwersalne mapowanie encji cen — Etap 5G.4K.3A SAFE

- Cztery encje cen wybrane przez użytkownika są bezwzględnym źródłem prawdy;
  brak mapowania kończy się statusem fail-closed i nigdy nie uruchamia podmiany
  na domyślny sensor providera ani skanowania pozostałych encji.
- Mapowanie zapisuje stabilną tożsamość Entity Registry i rozwiązuje zmianę
  `entity_id` wyłącznie do tej samej encji. Adapter wynika z jawnego kontraktu
  lub metadanych integracji, a nie z nazwy encji.
- Dodano trwałą detekcję ograniczonego schematu danych, realny format Pstryk AIO
  `today_prices`/`tomorrow_prices` z `start`/`end`/`price`, generic i pełne pola
  custom. Numeric state jest dozwolony wyłącznie dla `current_price_only`.
- Diagnostyka pokazuje per mapowanie encję wybraną i rozwiązaną, adapter,
  schema, pola, semantykę, pokrycie i powód błędu. Karta nadal renderuje tylko
  kanoniczne wiersze backendu. Rewizja karty: `v=0.8.0.38`.

### Kanoniczny model cen energii — Etap 5G.4K.3 SAFE

- Dodano niezależne, wersjonowane kontrakty źródeł BUY i SELL oraz adaptery
  Pstryk, PSE/RCE, generic i custom. Detekcja znanych providerów korzysta najpierw
  z metadanych integracji, a nazwa encji jest tylko słabą wskazówką.
- Backend normalizuje jednostkę, brutto/netto, semantykę składników i interwały,
  agreguje wyłącznie kompletne godziny oraz przekazuje te same kanoniczne wiersze
  do Optimizer Core i karty. Nieznana semantyka działa fail closed.
- Pstryk jest traktowany jako zmienna cena all-in brutto, więc OSD/VAT/usługa nie
  są doliczane drugi raz. RCE `rce_pln` obsługuje 96 kwadransów, `period`, końcowy
  `dtime`, `business_date`, ceny ujemne i osobne encje Today/Tomorrow.
- Bieżący sensor prosumencki RCE SELL nie jest prognozą i daje jawny status
  `missing_sell_forecast`. Rewizja karty: `v=0.8.0.38`.

### Kontrakt wyniku slotu w Sugestiach AI — Etap 5G.4K.1

- Usunięto mylący ranking „Najlepsza decyzja” oparty na pełnym `net_result`.
  Karta pokazuje chronologicznie reprezentatywną propozycję bez przypisywania jej
  marginalnego zysku, którego Core nie wylicza osobno per decyzja.
- `net_result` jest prezentowany jako **Wynik całego slotu**: obejmuje pełny
  modelowany bilans przepływów, a ostatni slot może zawierać wartość terminalną
  baterii. `row.benefit` jest opisany jako różnica wyniku slotu względem baseline,
  natomiast `planner.benefit` pozostaje korzyścią całego planu względem bazowego.
- Semantyka jest identyczna dla Dziś i Jutro. Rewizja karty: `v=0.8.0.38`.

### Lokalny parser timestampów cen — Etap 5G.4J.10B

- Timestampy ISO z `Z` lub jawnym offsetem są konwertowane do lokalnej strefy
  Home Assistant przed wyznaczeniem daty, godziny i bucketu Dziś/Jutro.
- Naiwne datetime zachowują semantykę lokalnego czasu, a proste etykiety godzin
  nie uruchamiają konwersji timezone. W powtórzonej jesiennej godzinie
  deterministycznie wygrywa pierwsza wartość providera.
- Parser Managera i karty zachowuje ceny zerowe oraz ujemne. Rewizja tego etapu:
  `v=0.8.0.32`.

### Best-hours: max-profit i łagodzenie peaków — Etap 5G.4J.10A v2

- Chronologiczna symulacja nie pozwala już wcześniejszemu, tańszemu slotowi tego
  samego profilu zużyć energii zarezerwowanej dla wyraźnie droższego późniejszego
  slotu. Ranking ekonomiczny nadal korzysta z ceny sprzedaży, a ograniczenia
  fizyczne i dzienny target pozostają nadrzędne.
- Ceny różniące się najwyżej o konfigurowalne `0,05 PLN/kWh` tworzą
  deterministyczną grupę równoważności. W jej obrębie bounded water-fill obniża
  peak mocy bez łamania dynamicznych limitów i bez niepotrzebnego aktywowania
  całego okna.
- Preferowane automatyczne sloty Sprzedaży mają domyślne minimum `1000 W`.
  Redystrybucja i wyrównanie odbywają się przed oznaczeniem pozostałości jako
  shortfall; wymagany profil może jawnie skorzystać z minimum fizycznego.
- Dodano ustawienia, przetłumaczone powody diagnostyczne oraz regresje dla
  rankingu, grupowania, dynamicznych caps i residuali. Rewizja karty:
  `v=0.8.0.31`.

### FuturePlan lifecycle i ownership — Etap 5G.4J.8C

- Rozdzielono `approved`, zapis logiczny, oczekiwanie na falownik i fizyczne
  `confirmed`. Potwierdzenie powstaje wyłącznie po zapisie i udanym readbacku
  skorelowanym z właściwym planem, datą, slotem i rewizją intencji.
- Per-slot revision/fingerprint realizuje politykę **MANUAL WINS**. Późniejsza
  zmiana ręczna lub Apply Today nie jest nadpisywana przez stary FuturePlan.
- Datowane Sell/Charge są czyszczone do Normalnej Pracy po końcu własnego slotu,
  wyłącznie gdy nadal należą do planu. Nie ma powtórki następnego dnia ani catch-up.
- Rewizja karty: `v=0.8.0.30`.

### Autorytatywny FuturePlan 24 h — Etap 5G.4J.8B

- Akceptacja „Jutro” zapisuje datowany target 24 h: wybrane pozycje są jedynymi
  akcjami specjalnymi, a każda pozostała godzina ma kanoniczną intencję Normalna
  Praca. Nie wykonuje przy tym patcha bieżącego Harmonogramu ani zapisu do Deye.
- Backend buduje pełny target, bezpiecznie migruje starsze selected-only plany i
  materializuje następnego dnia JIT tylko aktualny slot. Sell zachowuje wyłącznie
  tryb i skwantowaną moc; Normalna Praca nie zamraża globalnych limitów.
- UI opisuje pełnodniową semantykę i odroczone wykonanie. Rewizja karty:
  `v=0.8.0.29`.

### Dzienny cel profilu — Etap 5G.4J.8A

- `target_energy_kwh` jest celem dziennym. Każdy aktywny lokalny dzień ma
  niezależny target, fulfillment, shortfall i diagnostykę, podczas gdy SOC
  nadal płynie nieprzerwanie przez cały horyzont 48 h.
- Alokacja, rezerwa dla późniejszego profilu i post-clamp redistribution są
  kluczowane po `(profile_id, local_date)`. Godziny okna przechodzącego przez
  północ konsumują target własnej daty kalendarzowej.
- Widoki Dziś/Jutro oraz walidacja danych planu jutra korzystają z tego samego
  dziennego ledgeru. Rewizja karty: `v=0.8.0.28`.

### Bezpieczny kontrakt sprzedaży — Etap 5G.4J.6

- Core używa maksymalnego prądu rozładowania wyłącznie jako ograniczenia
  wejściowego. Automatyczna sprzedaż steruje trybem i mocą sprzedaży, nie
  globalnym prądem baterii; backend ignoruje także stare pola prądowe AI.
- Szacowany prąd `sell_power / battery_voltage` pozostaje diagnostyką i nie
  trafia do harmonogramu ani `number.set_value`. Rewizja karty: `v=0.8.0.27`.

### Parametryczne dopełnianie celu — Etap 5G.4J

- **Zastosuj wybrane na dziś** tworzy autorytatywny plan 24 h: zaznaczone
  propozycje są jedynymi akcjami specjalnymi, a pozostałe godziny przechodzą na
  Normalną Pracę. Zwykła usługa listowa nadal jest partial patch. Rewizja karty:
  `v=0.8.0.27`.
- Moc proponowana przez Core jest przed publikacją kwantowana do rzeczywistego
  kroku encji `Max Sell Power`; energia, fulfillment, podgląd i kontrakt zapisu
  korzystają z tej samej wartości.
- Dodano bounded redistribution po clampie oraz jeden ledger fulfillmentu dla
  `battery_to_grid` i `total_export`, uwzględniający rozpoczętą godzinę.
- Core zachowuje pierwotne źródło limitu mocy (profil, plan globalny, eksport,
  falownik, encja Max Sell Power albo prąd × napięcie baterii).
- Pole `preferred_power_w` zachowuje kontrakt danych, a w UI jest opisane jako
  **Maksymalna moc profilu**.

### SOC source health — Etap 5G.4I

- Niezmienny SOC pozostaje poprawny, gdy zweryfikowane encje tego samego
  urządzenia/provider source nadal dostarczają świeże raporty.
- Freshness SOC rozdziela raport wartości od health źródła, zachowując
  fail-closed po rzeczywistej utracie komunikacji i recovery bez reloadu.
- Zmiany samych timestampów health pozostają poza Core, Store i pełną
  publikacją; status zmienia się semantycznie tylko przy `valid ↔ stale`.

### SOC freshness — Etap 5G.4F

- Freshness SOC korzysta z czasu faktycznego raportu, więc niezmienna wartość
  nie przechodzi błędnie w `stale` po 900 sekundach.
- Recovery `stale → valid` ponownie uruchamia guard także dla tej samej wartości
  SOC, bez powtarzania safe defaults dla niezmienionego błędu.
- Karta rozróżnia prawdziwe `0%` od `unknown`, `unavailable` i braku danych.

### Migracja Config Entry i zgodność 0.7.x

- Finalny schemat wpisu ma wersję `1.24`. Migracja zachowuje stabilne
  identyfikatory mapowanych encji i rozwiązuje je przez Entity Registry zamiast
  uzależniać konfigurację od bieżącej nazwy encji.
- Starsze kontrakty cen są przebudowywane do niezależnych BUY/SELL; selector
  `price_source` pozostaje migration-only, a jawnie puste mapowanie nie odzyskuje
  automatycznie providera po restarcie.
- Uzupełniane są bezpieczne ustawienia sprzedawcy, a starszy selected-only
  FuturePlan jest normalizowany do datowanego targetu 24 h. Migracja nie wykonuje
  fizycznego zapisu do falownika.

### Wydajność i lifecycle runtime

- Manager śledzi dokładną allowlistę wejść i nie przelicza Core od własnych
  sensorów wyjściowych ani zmian samego timestampu bez zmiany semantycznej.
- Core, AI, learning i zapisy Store używają single-flight/coalescing; ciężkie
  obliczenia są przeniesione poza główną pętlę HA, a publikacja jest deduplikowana.
- Historia jest ograniczana i kompaktowana, żądania AI mają limit/cooldown, start
  jest bramkowany gotowością Home Assistant, a unload usuwa listenery i zadania.
- Ścieżki runtime mają budżety czasu i nie używają pollingowych pętli zasobu.

### Sterowanie i bezpieczeństwo

- Dodano nadrzędny przełącznik **Sterowanie Deye** ze stanami Aktywne,
  Wyłączanie i Wyłączone. Wyłączenie blokuje wszystkie nowe fizyczne zapisy,
  nie uruchamia safe defaults i nie zatrzymuje monitoringu, Harmonogramu,
  Solcast, AI, Optimizer Core ani diagnostyki.
- Rozdzielono **Planowaną decyzję Managera** od **Wykonanej decyzji Managera**,
  dzięki czemu tryb obserwacyjny pokazuje plan bez sugerowania zapisu.
- Wszystkie fizyczne ścieżki zapisu przechodzą przez centralny guard oraz
  respektują wyłączenie sterowania i zatrzymanie awaryjne.
- Zapis Deye Time Of Use działa diff-only: powstaje snapshot, zapisywane są tylko
  rozbieżne encje, backend czeka na confirmation/readback do 30 sekund, a błąd
  uruchamia rollback wyłącznie encji zapisanych przez bieżącą transakcję.
- Stany unknown/unavailable i niepełny readback działają fail-closed. Provider
  read-only nie otrzymuje surowych ani zgadywanych operacji zastępczych.

### Moc falownika i limity

- Dodano konfigurowalny maksymalny limit mocy AC falownika z bezpiecznym limitem
  absolutnym oraz walidacją fizycznego zakresu encji Max Sell Power.
- Obsługiwane są encje publikujące moc w W i kW; wartość jest przeliczana do
  natywnej jednostki providera przed zapisem.
- Zachowano semantykę 0 W: zero jest poprawną świadomą wartością, a nie brakiem
  konfiguracji.
- Rozdzielono limity importu i eksportu sieci oraz wspólne budżety mocy w
  Optimizer Core, aby równoległe przepływy nie wykorzystywały wielokrotnie tego
  samego limitu.

### Providerzy Deye

- Dodano profile ESPHome Deye Inverter — Lewa-Reka, Solarman, Sunsynk,
  Deye Inverter MQTT / Addon oraz Mapowanie niestandardowe.
- Kreator ogranicza wykrywanie do wybranego urządzenia falownika i pokazuje
  capabilities dla odczytów, sterowania, sprzedaży, ładowania i fizycznego TOU.
- Solarman normalizuje między innymi opcje `Disabled` i `Disable`. Sunsynk
  rozpoznaje `Allow Grid`, `Allow Grid & Gen`, `No Grid or Gen` i
  `Allow Gen`.
- Custom może działać z mapowaniem częściowym, ale nie deklaruje pełnej
  synchronizacji TOU bez kompletnego readbacku 6/6.
- Deye Inverter MQTT / Addon pozostaje read-only, gdy provider nie udostępnia
  bezpiecznych natywnych encji HA do sterowania.
- Usunięto zależność od globalnego przełącznika Time Of Use. Manager nie
  przełącza automatycznie `Time Of Use`, `Use Timer` ani odpowiednika globalnego.

### Harmonogram i Mapowanie Deye

- Harmonogram udostępnia trzy polskie tryby użytkownika: **Normalna Praca**,
  **Ładowanie** i **Sprzedaż**. Techniczne opcje providera pozostają szczegółem
  fizycznego mapowania.
- Rozdzielono `minimum_sell_soc` i `tou_soc`: pierwsze pole jest wyłącznie
  logicznym progiem zatrzymania sprzedaży, drugie jest fizycznym SOC Deye TOU.
- Aktualna segmentacja 24 h → 6/6 używa pary `tou_soc` i `charge_enabled`.
  Logiczny tryb, moc, prądy i `minimum_sell_soc` nie tworzą fizycznej granicy.
- Gdy naturalna mapa ma mniej niż sześć zakresów, najdłuższe zakresy są
  deterministycznie dzielone. Więcej niż sześć zakresów blokuje zapis przed
  pierwszą zmianą falownika.
- Edycja pojedynczego slotu działa transakcyjnie na lokalnym szkicu. **Anuluj**
  nie wykonuje usługi, a **Zapisz** wysyła jeden patch zawierający wszystkie
  zmienione pola.
- Zmiany profilu są kopiowane do szkicu tylko przy wyborze lub jawnym ponownym
  wczytaniu; późniejsze wartości konkretnego slotu pozostają niezależne.

### Fizyczne Deye Time Of Use

- Dodano backendowe capabilities dla każdego z sześciu slotów i pól Od, Do,
  SOC Deye TOU oraz Grid Charge / źródło ładowania.
- Pole Do jest fizycznie startem następnego slotu; Do slotu 6 wskazuje start
  slotu 1. Ręczne granice są obecnie ograniczone do pełnych godzin HH:00.
- Usługa częściowego `set_tou_slot` zapisuje tylko jawnie przekazane i wspierane
  pola. Równoległy zapis TOU jest blokowany.
- Edytor TOU pokazuje actual, expected i status, uwzględnia częściowy Custom
  oraz blokuje zapis dla providerów read-only.
- Potwierdzona ręczna zmiana wykonana w Managerze uruchamia reverse sync do
  Harmonogramu. Aktualizowane są wyłącznie `tou_soc`, `charge_enabled` i
  przypisanie godzin; tryb, enabled, `minimum_sell_soc`, moc, prądy i
  `physical_work_mode` pozostają bez zmian.
- Round-trip verification odrzuca fizyczną mapę, której nie można jednoznacznie
  odtworzyć przez algorytm 24 h → 6/6.

### Zewnętrzne zmiany TOU

- Usunięto fałszywy skrót cache `_last_tou_signature`. Cache pozostał
  optymalizacją, ale pominięcie zapisu wymaga również pełnego znormalizowanego
  readbacku fizycznego 6/6.
- Dodano oczekiwaną i fizyczną sygnaturę obejmującą start, end, SOC i Grid
  Charge każdego zakresu.
- Zewnętrzna zmiana startu, SOC albo Grid Charge jest wykrywana podczas
  zwykłego cyklu Managera. Przy aktywnym sterowaniu diff-only przywraca wyłącznie
  rozbieżne encje.
- Przy wyłączonym Sterowaniu Deye, zatrzymaniu awaryjnym albo providerze
  read-only różnica jest tylko raportowana i nie zmienia Harmonogramu.
- Po własnym potwierdzonym zapisie i po reverse sync aktualizowany jest podpis
  fizyczny, co zapobiega write-loop.
- Diagnostyka `tou_reconciliation` pokazuje expected/physical signature,
  kompletność readbacku, mismatch, blokadę, listę pól i ostatni błąd.

### Optimizer Core i Sugestie AI

- Etap 5G.4D zastąpił sztywny próg 7/21/60 dni adaptacyjną dojrzałością
  profilu wyliczaną z istniejących zwalidowanych godzin, pełnych dni, pokrycia
  profili 7×24 i 12×24, próbek PV, trafności forecastu oraz świeżości historii.
- Rozdzielono Jakość danych, Dojrzałość profilu, Pewność planu i Gotowość
  wykonania. Niska dojrzałość wpływa proporcjonalnie na pewność i nie nakłada
  globalnego capu tylko z powodu wieku profilu.
- Kandydaci niespełniający minimalnej pewności pozostają widoczni w trybie
  podglądu bez checkboxa i bez możliwości zapisu, z osobnymi powodami blokady
  propozycji i wdrożenia.
- Learning zachowuje inkrementalny `learning_revision` i `history_watermark`, a
  rolling 48 h reaguje na skwantowane materialne odchylenia live PV/load bez
  osłabienia debounce, semantic dedupe ani single-flight.
- Karta czyta autorytatywne `data_quality.soc`; rewizja zasobu wynosi
  `v=0.8.0.23`, przy niezmienionej wersji integracji `0.8.0`.
- Optimizer Core używa wspólnych budżetów ładowania, rozładowania, importu,
  eksportu i mocy AC, przenosi niezrealizowane cele na kolejne kwalifikujące się
  sloty oraz jawnie raportuje niepełne dane finansowe.
- Rozdzielono straty konwersji od kosztu degradacji i dodano wartość końcowej
  energii oraz karę za brak docelowej rezerwy SOC.
- Wariant `optimizer_shadow` porównuje plan bez wykonywania zapisów.
- Opcjonalne AI pozostaje doradcą: odpowiedź jest związana z konkretnym planem,
  kandydat jest ponownie symulowany przez lokalny Core i wymaga ręcznej decyzji.
  AI nie ma bezpośredniego dostępu do usług Home Assistant ani Deye.

### Diagnostyka, UX i testy

- Rozszerzono diagnostykę providerów, mapowania, transakcji TOU, reverse sync,
  reconciliation, limitów mocy oraz planowanych i wykonanych decyzji.
- Dodano aktualne polskie etykiety trybów i transakcyjne dialogi Harmonogramu
  oraz TOU z ochroną przed utratą niezapisanych zmian.
- Znacznie rozszerzono testy bezpieczeństwa, providerów, mapowania, TOU,
  reverse sync, zewnętrznych zmian, Optimizer Core, AI i obu kopii karty.
- Integracja i karta pozostają w wersji `0.8.0`.

## [0.7.9] - 2026-08-01

### Local resource revision v=0.7.9.11

- Ujednolicono rewizję wyświetlaną w diagnostyce karty z nagłówkiem zasobu,
  dokumentacją instalacji i testami wersjonowania.
- Rewizja `v=0.7.9.11` nie zmienia wersji integracji ani karty `0.7.9` oraz nie
  zmienia backendu, Optimizer Core ani sterowania falownikiem.

### Local resource revision v=0.7.9.10

- Harmonogram pracy odświeża tryb i zależne parametry po potwierdzonej zmianie
  encji, bez wymuszania pełnego renderowania przy aktualizacjach samej telemetrii.
- Wartość trybu wybrana dla pojedynczego slotu jest pokazywana optymistycznie,
  a następnie zastępowana stanem potwierdzonym przez Home Assistant.
- Przycisk „Zastosuj zmiany” w bocznym panelu edycji zbiorczej ponownie wywołuje
  zapis wyłącznie zaznaczonych godzin i pól. Trwający zapis blokuje ponowne
  kliknięcie, a błąd zachowuje formularz i zaznaczenie.
- Nie zmieniono backendu, Optimizer Core, mapowania Deye TOU ani logiki
  sterowania falownikiem.

### Local resource revision v=0.7.9.4

- Telemetria PV, domu, sieci, baterii, SOC i cen jest próbkowana co minutę
  oraz oceniana niezależnie, bez zamiany brakujących danych na zera.
- Zakończona godzina zachowuje energię kanałów, SOC start/koniec/min/max/średni,
  tryb i moc, migawkę Solcast i pogody, kompletność każdego kanału oraz kontrolę
  bilansu energii. Godziny częściowe pozostają w historii i mają mniejszą wagę.
- Optimizer Core otrzymuje historię godzinową, bieżący stan i część otwartej
  godziny. Historyczny SOC jest oddzielony od prognozy, a bieżąca godzina jest
  zakotwiczona na zmierzonym SOC i aktualnych mocach.
- Panel jakości pokazuje użyteczne godziny, zakres historii i osobne pokrycie
  kanałów. Rewizja zasobu `v=0.7.9.4` nie zmienia wersji integracji ani karty
  `0.7.9`.

### Added

- Pełne egzekwowanie profili: `allow_partial`, `min_net_result`,
  `profitable_only`, `purpose`, `deadline`, `charge_missing_only`,
  `use_corrected_pv`, `allow_earlier_grid_charge` i dynamiczne miejsce na PV.
- Rozliczanie `profile_execution` z celem, planem, wykonaniem, SOC, ceną,
  importem, eksportem, wynikiem, jakością danych i stanem realizacji.
- Zakładka **Plan i wykonanie** z widokami Dziś, Jutro, 48 h i Historia,
  porównaniem plan/real oraz stanami propozycji, akceptacji, wdrożenia i wykonania.
- Wersjonowane, 90-dniowe archiwum godzinowe zamraża plan obowiązujący dla
  danej godziny i dopina do niego rzeczywiste pomiary bez przeliczania historii.
- Usługa `get_plan_execution` zwraca wyłącznie do odczytu jeden wybrany dzień,
  dzięki czemu pełna historia nie obciąża atrybutów encji Home Assistant.
- Ponowna walidacja każdego zaakceptowanego slotu planu na jutro bez
  automatycznej zmiany innych slotów.
- Testy cen zerowych i ujemnych, OSD, chronologii ładowania, celów końcowego
  SOC, profili częściowych, backendowego źródła planu i wersjonowania.

### Changed

- Optimizer Core analizuje późniejszą sprzedaż, uniknięty import domu i jawną
  rezerwę; nie stosuje ukrytych limitów 1/3/4 godzin.
- Warianty 55% / 45% / 30% używają końcowego SOC jako miękkiego celu mającego
  rzeczywisty wpływ na symulację.
- Ceny `0,00` i ujemne pozostają poprawnymi danymi, a koszt zakupu uwzględnia
  dystrybucję OSD.
- Karta nie tworzy niezależnego planu JavaScript przy braku backendu.
- Rankingi sprzedaży i zakupu są sortowane według rzeczywistej ceny, a szczegóły
  decyzji pokazują cel ładowania, źródło PV, późniejszy cel i miejsce na PV.
- Rewizja zasobu `v=0.7.9.3` unieważnia wcześniejszy cache planu i prezentuje
  rzeczywiste pokrycie profili, częściowe pokrycie OSD oraz wpływ odrzuconych
  próbek na pewność.
- Karta jakości rozdziela status propozycji od faktycznej realizacji profilu,
  nie zamienia brakujących danych na zera i pokazuje średnią pewność osobno dla
  dziś, jutra oraz całego planu 48 h.
- Integracja, karta i fallback mają wspólną wersję `0.7.9`;
  aktywny parametr cache to `v=0.7.9.4`.

### Safety

- Nie zmieniono fizycznego mapowania Deye TOU, kompresji 6/6, confirm/retry,
  fail-closed ani wymogu działania i potwierdzenia użytkownika.
- Zewnętrzny asystent AI pozostaje wyłącznie polskojęzycznym doradcą i nie może
  wykonywać zapisów do Deye.

## [0.7.7 — lokalna rewizja karty v=0.7.7.2] - 2026-07-29

### Added

- Jednoznaczne rankingi Porannej i Wieczornej sprzedaży z okien, celów,
  minimalnych cen i minimalnego SOC ustawionych przez użytkownika.
- Ranking zakupu według efektywnego kosztu energii z godzinowym profilem OSD,
  składowymi ceny i informacją o pokryciu danych.
- Lokalne rejestrowanie zmierzonego wykonania profili bez zmiany ich parametrów
  i bez wywoływania usług Deye.
- Wspólne polskie mapowanie statusów, źródeł decyzji i błędów asystenta API.

### Changed

- Przegląd jest krótkim podsumowaniem i nie dubluje pełnych wykresów dziennych
  ani rozbudowanych kart pogody.
- Profile pokazują osobno cel, zaplanowaną energię, wykonanie, pozostałą energię
  oraz przyczynę ograniczenia.
- Proponowane zmiany rozdzielają realizację profili, sugestie optymalizatora
  i akcje bez zmiany planu bazowego.
- Moc sprzedaży przekazywana do slotu odpowiada planowanej energii i faktycznej
  długości slotu; propozycje zerowe oraz nieopłacalne nie są udostępniane do
  zaznaczenia.
- Bieżąca minimalna cena profilu ma pierwszeństwo przed starszą wartością
  zapisaną w planie, a tabele Dziś/Jutro pokazują pełne ceny chronologicznie.
- Przywrócono dotychczasowy, edytowalny układ prywatności Asystenta AI przez API;
  zmiana w tej części ogranicza się do polskiego polecenia i polskiej odpowiedzi.
- Wykresy używają osi energii od 0 kWh, zakresu SOC 0–100%, osobnych linii
  twardego i efektywnego minimum SOC oraz nie rysują produkcji rzeczywistej dla
  przyszłych godzin.
- Dolny pasek działań jest nieprzezroczystym sticky footerem widocznym wyłącznie
  w zakładce Proponowane zmiany.
- Wersja integracji i karty pozostaje `0.7.7`; lokalna rewizja zasobu wynosi
  `v=0.7.7.2`.

### Safety

- Brak pełnych danych OSD blokuje automatyczne propozycje ładowania z sieci
  przedstawiane jako opłacalne; surowa cena pozostaje informacyjna.
- Nie zmieniono Deye TOU, kompresji 6/6, confirm/retry, fail-closed ani
  parametrów profili użytkownika.

## [0.7.7] - 2026-07-29

### Added

- Deterministyczny backendowy Optimizer Core z planem bazowym, trzema wariantami,
  48-godzinnym bilansem przepływów, wynikiem netto, progiem neutralności i
  lokalną symulacją alternatywy.
- Profil zużycia domu 7×24, lokalna korekta PV miesiąc×godzina, etapy uczenia
  oraz rozpoznawanie próbek z curtailmentem.
- Sekwencyjny model SOC 48 h z osobnymi sprawnościami, limitami mocy/prądu,
  rezerwą energetyczną i obsługą niepełnej bieżącej godziny.
- Profile Poranna sprzedaż, Wieczorna sprzedaż i Ładowanie z walidacją,
  priorytetami, celami, oknami przez północ i trzema metodami rozłożenia energii.
- Opcjonalny asystent AI przez Gemini, OpenRouter, OpenAI, OpenCode lub własny
  zgodny endpoint HTTPS, z JSON Schema, redakcją danych i lokalną walidacją.
- Opcjonalne mapowanie PV3 Power i Battery SOH oraz diagnostyka źródeł/fallbacków.

### Changed

- Historia aplikacyjna i profile użytkownika używają wersjonowanego schematu v2.
- `Load Power` jest źródłem głównym obciążenia; komplet L1/L2/L3 i bilans są
  jednoznacznie oznaczonymi fallbackami bez podwójnego liczenia.
- Solcast przechowuje oddzielnie prognozę początkową, najnowszą i skorygowaną.
- Sugestie AI pokazują baseline, warianty, pewność, rozbicie finansowe, status
  wykonania oraz ustawienia profili i API.

### Fixed

- Liczniki `total_increasing` poprawnie obsługują jednostki i reset o północy,
  bez ujemnych delt.
- Prognoza SOC zachowuje ciągłość dziś/jutro i nie zmienia punktów historycznych
  po zmianie bieżącego SOC.
- Dystrybucja nie jest doliczana ponownie, gdy cena zakupu już ją zawiera.

### Security

- Zewnętrzny model nie ma dostępu do usług Deye i nie może zapisać planu.
- Klucz API nie trafia do historii, encji ani diagnostyki; payload nie zawiera
  identyfikatorów encji/urządzeń, lokalizacji ani surowej historii.
- Brak SOC pozostaje warunkiem fail-closed; zachowano walidację, confirm/retry,
  limit 6/6 TOU i ręczne zatwierdzanie.

### Migration

- Migracja 0.7.6 → 0.7.7 jest idempotentna, zachowuje historię, licznik dni,
  mapowania, taryfę i harmonogram. Nowe profile są domyślnie wyłączone.
- Koperta Home Assistant Store pozostaje kompatybilna ze starszymi danymi.

### Documentation

- Rozszerzono README i polską instrukcję o uczenie, profile, taryfy, migrację,
  prywatność oraz opcjonalną konfigurację API.
- Dodano `IMPLEMENTATION_0.7.7.md` i `RELEASE_NOTES_0.7.7.md`.

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

### Etap 5.3.7 — naprawa układu mobilnego (v=21)

- Usunięto konflikt pomiędzy desktopowym inline `grid-template-columns` a układem mobilnym: ratios `prices_ratio`, `buy_prices_ratio` i `solcast_ratio` są generowane tylko dla desktopu, a aktywny układ mobilny używa jednej kolumny.
- `effectiveLayout()` jawnie zwraca `is_mobile`, uwzględnia `mobile_breakpoint`, szerokość hosta karty, `preserve_desktop_layout` oraz mobilne nadpisania trybu, dopasowania, przewijania i liczby kolumn.
- Przy `allow_horizontal_scroll: false` główny kontener dashboardu otrzymuje `overflow-x: hidden`; mobilny `.dem-v073` używa `width: 100%`, `max-width: 100%`, `min-width: 0` i `box-sizing: border-box`.
- Elementy siatki oraz panele otrzymały bezpieczne ograniczenia `min-width: 0`, `max-width: 100%` i `box-sizing: border-box`.
- Harmonogram pozostaje w szerokości karty, a poziomy scroll szerokiej tabeli działa wyłącznie w jej lokalnym kontenerze.
- Panel Solcast nie rozszerza dashboardu; lista dni zachowuje lokalny poziomy scroll, a wykres skaluje się do szerokości panelu.
- Panel **Status energii**, `flow-scaler`, `.dialog-host`, `renderDialogOnly()` i wygląd desktopowy pozostały bez zmian.
- Dodano `getGridOptions()` z oficjalnie obsługiwanym `columns: "full"` dla widoku Sections; wysokość pozostaje automatyczna.
- Rozszerzono testy regresji układu; pełny zestaw `python -m unittest discover -s tests -v` obejmuje 205 testów.
- Rewizja karty JavaScript: `v=21`.

### Etap 5.3.8 — geometria przepływu i mobilne Sugestie AI (v=22)

- Zastąpiono zduplikowane wzory ścieżek wspólną metodą `flowGeometry()`, używaną zarówno podczas pierwszego renderu, jak i w `updateFlowLines()`.
- Rozdzielono szerokość środkowej kolumny panelu od rzeczywistej szerokości widocznego SVG falownika.
- Punkty początkowe linii przeniesiono na wewnętrzne krawędzie kafli, a przy falowniku utworzono osobne górne i dolne porty dla PV, Sieci, Baterii i Domu.
- Punkty kontrolne Béziera są obliczane proporcjonalnie do odległości pomiędzy początkiem i końcem ścieżki; lewa i prawa strona zachowują lustrzaną geometrię.
- `viewBox` panelu przepływu jest zgodny z dynamicznym `boardWidth`, a ścieżki tła i aktywne są aktualizowane razem.
- Lokalny `ResizeObserver` panelu przepływu ponawia istniejące skalowanie po zmianie szerokości kontenera, również w podglądzie edytora karty.
- Mobilny dialog **Sugestie AI** otrzymał lokalne ograniczenia szerokości, przewijany poziomo pasek pełnych nazw zakładek oraz responsywne kontenery kart i bieżącego wykresu 48 h.
- Szerokie tabele, starsze wykresy i pasek pogody zachowują lokalne przewijanie bez rozszerzania całego dialogu.
- `renderAiDialog()`, logika AI, `.dialog-host`, `renderDialogOnly()`, dialog **Ustawienia i diagnostyka**, główny mobilny dashboard i backend pozostały bez zmian.
- Dodano testy regresji geometrii SVG, symetrii, wariantów parametrów panelu, mobilnego ograniczania szerokości dialogu AI oraz lokalnych kontenerów przewijania.
- Testy: `214/214` jednostek przechodzi; `node --check` jest poprawne dla obu kopii JS; obie kopie mają identyczny SHA-256.
- Rewizja karty JavaScript: `v=22`.

### Etap 5.3.9 — wizualna przebudowa Status energii (v=23)

- Przebudowano wyłącznie frontendową sekcję **Status energii** zgodnie z nowym wzorcem: większe kafle, głębsze tła, wyraźniejsze obramowania, większa typografia i neonowe akcenty.
- Zastąpiono ikony PV, Sieci, Baterii i Domu bogatszymi rysunkami SVG; powiększono również ikony czterech dolnych kafli.
- Powiększono i uszczegółowiono SVG falownika, dodano podpis **Falownik Deye**, większą temperaturę oraz przebudowany kafel **Sprzedano dzisiaj**.
- Zachowano wspólną metodę `flowGeometry()` z `v=22`, cztery osobne porty falownika, dynamiczny `viewBox` i symetrię ścieżek. Bazowa wysokość panelu jest teraz przekazywana do istniejącego lokalnego skalowania.
- Linie przepływu mają kolorowe neonowe tło, animowane punkty i małe strzałki kierunkowe; zbędne, powielone wartości mocy nad ścieżkami zostały usunięte. Kierunki importu/eksportu i ładowania/rozładowania nadal wynikają z istniejących znaków danych.
- Dzienną produkcję PV przeniesiono pod odczyty PV1/PV2 jako **Wyprodukowano dzisiaj**, a dzienne zużycie domu pod odczyty L1/L2/L3 jako **Zużycie dzisiaj**; oba podsumowania oddzielono poziomą linią.
- Dolna belka zawiera większe kafle: **Decyzja managera**, **Aktywny slot**, **Tryb pracy (Manager)** i **Tryb Deye**.
- **Tryb Deye** jest odczytywany frontendowo z istniejącej encji `select.deye_inverter_system_work_mode` albo jej konfiguracji w mapowaniu karty. Wartości `unknown`, `unavailable` i brak encji są prezentowane jako `—`; nie dodano żadnej encji ani logiki backendowej.
- Domyślna szerokość bocznych kafli została zwiększona z `230` do `300`, nadal z walidowanym zakresem 120–360 i lokalnym skalowaniem całego panelu.
- Backend, manager, encje, usługi, harmonogram, Solcast, Sugestie AI, dialogi, `.dialog-host`, `renderDialogOnly()` i główny układ mobilny pozostały bez zmian.
- Rewizja karty JavaScript: `v=23`.

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
