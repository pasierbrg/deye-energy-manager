# Deye Energy Manager 0.8.0

Wersja 0.8.0 porządkuje całą drogę od planu użytkownika do fizycznego falownika:
24-godzinny Harmonogram pracy jest mapowany na sześć zakresów Deye Time Of Use,
zapisy są potwierdzane odczytem zwrotnym, a rozbieżności mogą zostać bezpiecznie
wycofane. Jednocześnie rozszerzono providerów, Optimizer Core, Sugestie AI i
diagnostykę.

## Finalny stan wydania

- Po finalnej weryfikacji automatycznej i potwierdzeniu użytkownika ujednolicono
  prezentację Solcast:
  `Realizacja dzisiaj` jest
  wyliczana z najnowszej pełnodniowej prognozy i produkcji od lokalnej północy,
  bez ograniczania wyniku do 100%. `Trafność historyczna` pozostaje osobną
  metryką. Główna karta i Historia korzystają z tego samego kontraktu backendu.

- W standardowym trybie UI/storage zasób Lovelace jest tworzony albo
  aktualizowany automatycznie z bundled karty integracji. Zwykła aktualizacja
  nie wymaga kopiowania JS do `/config/www`, ręcznego dodawania zasobu ani
  zmiany `?v=`. Tryb YAML pozostaje jawnie ręczny i używa canonical URL DEM.
- Przypadkowe lub starsze `0 A` w slocie Harmonogramu oznacza brak własnego
  ustawienia i dziedziczy właściwy limit profilu/użytkownika; jawna dodatnia
  wartość ręczna nadal ma pierwszeństwo.
- Tracking historii Solcast bez daty inicjalizuje się sam. Rollover nie zamyka
  fałszywie dnia bez prognozy, a bieżący postęp używa najnowszej dostępnej
  prognozy.
- Poprawki issues #1, #2, #3, #5, #6, #7 i #9 są objęte testami regresji:
  fizyczne TOU 6/6 bez globalnego master switcha, skalowanie karty, opcjonalne
  PV3/SOH, dowolny jawny prefiks encji, brak luźnego autodiscovery po słowie
  `deye`, semantyka `0 A` oraz parser liczb rozróżniający brak danych od zera.
- Issue #8 pozostaje nieblokującą obserwacją runtime do kolejnego potwierdzenia
  rollover Solcast po lokalnej północy.
- Lokalny Optimizer Core wykonuje deterministyczne obliczenia. Opcjonalny
  zewnętrzny AI/Assistant jest wyłącznie doradczy, nie wywołuje bezpośrednio
  usług Home Assistant ani Deye i nie zastępuje zabezpieczeń sprzętowych,
  konfiguracji falownika ani świadomej kontroli użytkownika.

## Najważniejsze nowości

- trzy czytelne tryby użytkownika: Normalna Praca, Ładowanie i Sprzedaż;
- nadrzędny przełącznik Sterowanie Deye;
- konfigurowalny limit mocy AC falownika i poprawna obsługa W/kW oraz 0 W;
- transakcyjne Deye Time Of Use 6/6 z diff-only, confirmation i rollbackiem;
- fizyczny edytor TOU z polami Od, Do, SOC i Grid Charge;
- reverse sync po ręcznej zmianie wykonanej przez Managera;
- wykrywanie zmian fizycznego TOU wykonanych poza Managerem;
- lokalny szkic edycji slotu Harmonogramu z Anuluj/Zapisz;
- profile Lewa-Reka, Solarman, Sunsynk, Custom i Deye MQTT / Addon read-only;
- rozszerzony Optimizer Core i bezpieczny, opcjonalny doradca AI.
- pełnodniowe **Zastosuj wybrane na dziś**: wybrane akcje specjalne oraz
  Normalna Praca dla wszystkich pozostałych godzin, bez zmiany planu Jutro.
- datowany plan **Jutro** jako autorytatywny target 24 h: wybrane akcje są
  jedynymi akcjami specjalnymi, a pozostałe godziny mają Normalną Pracę;
  akceptacja nie zapisuje dziś do falownika, wykonanie odbywa się jutro JIT.
- jednoznaczny kontrakt ekonomiczny UI: `net_result` jest opisany jako pełny
  wynik ekonomiczny modelowanego slotu/planu, oddzielony od korzyści całego
  planu względem bazowego i nieprzedstawiany jako marginalny efekt pojedynczej
  decyzji.
- warstwa `PriceSourceContract` dla uniwersalnych źródeł cen: cztery mapowane
  encje użytkownika są źródłem prawdy,
  rename jest rozwiązywany przez stabilną tożsamość, Pstryk AIO używa
  `today_prices`/`tomorrow_prices`, a nieobsługiwany schema działa fail-closed.
- świadomie wyczyszczone BUY/SELL pozostaje puste po zapisie i restarcie oraz
  nie uruchamia defaultu providera; przy obu pustych BUY można jednak jawnie
  wybrać sprzedawcę i użyć zweryfikowanej standardowej taryfy z katalogu.
- zmiana mapowanej encji przebudowuje adapter i schema od zera, więc Pstryk nie
  może pozostawić semantyki all-in po przełączeniu na RCE; cztery mapowania są
  jedynym runtime source-of-truth, a legacy `price_source` jest migration-only.
- finalna migracja konfiguracji do `1.24` usuwa stare kanoniczne rekordy i
  auto-metadata po clear lub zmianie providera, zachowuje stabilne identyfikatory
  mapowanych encji oraz uzupełnia bezpieczne wartości ustawień sprzedawcy; known
  adapters są tylko do odczytu, a cache planu jest selektywnie uzgadniany z
  bieżącymi mapowaniami.
- uproszczony ekran taryfy edytuje standardowo tylko operatora OSD i taryfę;
  role ekonomiczne rozróżniają Pstryk BUY/SELL (`retail_buy_all_in` /
  `prosumer_sell`) oraz RCE BUY/SELL (`energy_only` / `market_reference`), a
  Custom bez jawnej roli działa fail-closed.
- pełna macierz 33 grup G klasyfikuje zwykłe, specjalne i dynamiczne taryfy;
  21 zweryfikowanych kontraktów sprzedawców generuje BUY 24+24 validity-first,
  z ceną energii brutto i zmiennym OSD dodanym dokładnie raz. Pstryk pozostaje
  all-in i zawsze wygrywa jako jawne mapowanie.
- wspólny updater OSD/sprzedawców działa atomowo, zachowuje last-known-good,
  pokazuje wersję lokalną/zdalną i sprawdza automatycznie najwyżej co 90 dni.

## Automatyczny zasób Lovelace

W standardowym trybie UI/storage DEM rejestruje bundled kartę i idempotentnie
tworzy lub aktualizuje wyłącznie własny zasób Lovelace. Użytkownik nie musi
kopiować pliku do `/config/www` ani ręcznie zmieniać `?v=`. Jednoznaczny legacy
resource `/local/deye-energy-manager-card.js?...` może zostać zmigrowany w miejscu,
a wiele Config Entries nadal prowadzi do jednego zasobu. Integracja nie zapisuje
bezpośrednio plików `.storage`.

Kanoniczny resource 0.8.0:

```text
/deye_energy_manager/deye-energy-manager-card.js?v=0.8.0.44
```

W trybie Lovelace YAML integracja nie modyfikuje konfiguracji. Powyższy bundled
URL należy dodać ręcznie jako moduł JavaScript.

## Solcast — spójność prognozy i realizacji

Bieżąca realizacja jest liczona jako `production_today_kwh /
forecast_today_kwh * 100`, z użyciem aktualnej lub najnowszej pełnodniowej
prognozy. Wynik nie jest ograniczany do 100%, a brak, zero lub nieaktualna
prognoza nie tworzy fałszywego `0%`. `historical_accuracy_pct` pozostaje osobną
metryką; główna karta Solcast i Historia używają wspólnego kanonicznego backendu
dla bieżącego dnia, podczas gdy zakończone dni zachowują własną ocenę historyczną.

Kontrakt bieżącego dnia rozdziela jawnie `forecast_today_kwh`,
`production_today_kwh`, `remaining_forecast_kwh`, `realization_today_pct`,
`historical_accuracy_pct`, `forecast_difference_today_kwh` oraz
`forecast_tomorrow_kwh`.

Historia zachowuje osobno prognozę początkową dnia, najnowszą prognozę
pełnodniową, godzinowy snapshot i prognozę skorygowaną. Bieżąca realizacja używa
najnowszej prognozy jako mianownika; prognoza skorygowana i trafność historyczna
służą analizie jakości i nie są podmieniane pod aktualny procent realizacji.

Optimizer Core nie używa `realization_today_pct` jako wejścia decyzyjnego —
korzysta z prognoz energii w kWh i osobnej historycznej accuracy/korekty.
Zewnętrzny AI pozostaje wyłącznie doradczy. Mechanizm self-heal i rollover jest
objęty testami automatycznymi; issue #8 pozostaje nieblokującą obserwacją do
rzeczywistego rolloveru po lokalnej północy.

## Finalne poprawki stabilności

- Integracja nie wymaga globalnej encji TOU/Use Timer do działania fizycznych 6/6.
- Usunięto hardcoded fallback prefiksu Deye; autodiscovery nie wybiera encji tylko
  dlatego, że jej identyfikator zawiera `deye`.
- Opcjonalne PV3/string/SOH pozostają puste bez jednoznacznego kandydata.
- Per-slot `0 A` oznacza unset/inherit/default, natomiast świadome globalne `0 A`
  pozostaje poprawne tam, gdzie dopuszcza je kontrakt danej encji.
- Strict parser liczb rozróżnia brak danych od prawdziwego zera i obsługuje
  scientific notation.
- Poprawiono skalowanie i układ karty na obsługiwanych szerokościach ekranu.

## Sterowanie Deye

Sterowanie ma stany Aktywne, Wyłączanie i Wyłączone. Wyłączenie zatrzymuje nowe
fizyczne operacje, czeka na bezpieczne zakończenie albo rollback aktywnej
transakcji i nie uruchamia automatycznych ustawień domyślnych.

Przy wyłączonym sterowaniu nadal działają monitoring, lokalny Harmonogram,
Mapowanie Deye, Solcast, Optimizer Core, AI i diagnostyka. Karta rozdziela
Planowaną decyzję Managera od Wykonanej decyzji Managera, dlatego tryb
obserwacyjny nie udaje wykonania planu.

Po ponownym włączeniu Manager najpierw odczytuje fizyczne TOU. Nie wysyła ślepo
całej mapy i naprawia wyłącznie rozbieżne pola.

## Harmonogram pracy

Harmonogram składa się z 24 jednogodzinnych slotów. Edytor pojedynczego slotu
pracuje na lokalnym szkicu: zmiany pól nie wywołują od razu usług HA. Anuluj
odrzuca całość, a Zapisz wysyła jeden logiczny patch.

Profile Normalnej Pracy i Ładowania są szablonami kopiowanymi przy wyborze trybu
lub po jawnym ponownym wczytaniu. Późniejsze ręczne parametry konkretnego slotu
pozostają niezależne.

## Mapowanie Deye i Time Of Use

Fizyczna segmentacja 24 h → 6/6 używa `tou_soc` i `charge_enabled`. Logiczny
tryb, moc, prądy i próg zatrzymania sprzedaży nie tworzą granic TOU. Sąsiednie
godziny o tej samej parze są łączone, a przy mniej niż sześciu zakresach
najdłuższe są deterministycznie dzielone. Plan wymagający więcej niż sześciu
zakresów jest blokowany przed zapisem.

Edytor fizycznego TOU pokazuje capabilities providera, actual, expected i status.
Pole Do jest startem następnego slotu, a Do slotu 6 jest startem slotu 1. Usługa
częściowa zapisuje tylko przekazane i wspierane pola.

Ręczna zmiana wykonana w Deye Energy Managerze po confirmation aktualizuje
Harmonogram przez reverse sync. Zmieniane są wyłącznie `tou_soc`,
`charge_enabled` i przypisanie godzin. Inne parametry slotu pozostają bez zmian.

Zewnętrzna zmiana startu, SOC albo Grid Charge nie jest automatycznie adoptowana
do Harmonogramu. Manager porównuje pełny fizyczny readback 6/6 z oczekiwaną mapą:

- przy aktywnym sterowaniu wykonuje diff-only reconciliation;
- przy wyłączonym sterowaniu lub emergency stop tylko raportuje różnicę;
- przy providerze read-only nie wykonuje zapisu;
- przy unknown/unavailable nie uznaje TOU za zgodne i nie pisze na ślepo.

## Sprzedaż i SOC

W 0.8.0 znaczenia SOC są jednoznacznie rozdzielone:

- `minimum_sell_soc` to logiczny próg zatrzymania sprzedaży przez Managera;
- `tou_soc` to fizyczny SOC zapisywany do Deye Time Of Use.

Osiągnięcie progu sprzedaży nie zmienia fizycznego TOU. Slot Sprzedaży zachowuje
osobno moc, prąd rozładowania, cenę minimalną i oba poziomy SOC.

## Providerzy

- **ESPHome Deye Inverter — Lewa-Reka**: pełne sterowanie i natywne TOU 6/6;
- **Solarman**: Program N Time/SOC/Charging, z normalizacją Disable/Disabled;
- **Sunsynk**: ProgN time/capacity/charge i semantyka Grid/Generator;
- **Custom**: mapowanie częściowe albo pełne, zależnie od wskazanych encji;
- **Deye Inverter MQTT / Addon**: profil odczytowy bez zastępczych zapisów MQTT.

Capabilities backendu są źródłem prawdy. Karta nie zgaduje domen ani surowych
opcji providerów.

## Bezpieczeństwo zapisu

- centralny guard wszystkich fizycznych operacji;
- walidacja encji, domen, opcji select i zakresów liczbowych przed zapisem;
- snapshot wartości fizycznych;
- diff-only i deterministyczna kolejność zapisu;
- confirmation/readback z timeoutem do 30 sekund;
- rollback tylko zmienionych encji;
- status krytyczny, gdy pełnego rollbacku nie można potwierdzić;
- blokada równoległych transakcji TOU;
- fail-closed przy niepełnych danych.

## Optimizer Core i AI

Optimizer Core otrzymał wspólne budżety mocy, importu, eksportu, ładowania i
rozładowania. Jawnie rozdziela straty konwersji, degradację baterii, wartość
końcowej energii i kompletność danych finansowych. Plan dziś i jutro jest
oceniany niezależnie.

Maksymalny prąd rozładowania pozostaje wejściowym limitem fizycznym Core.
Automatyczna sprzedaż zapisuje wyłącznie tryb i dokładną moc sprzedaży; nie
zmienia globalnego prądu baterii. Estymacja prądu z mocy jest tylko diagnostyką.

Strategia `best_hours` chroni teraz wyraźnie droższe późniejsze sloty przed
chronologicznym zużyciem SOC przez tańszy slot tego samego profilu. Ranking
pozostaje oparty o cenę sprzedaży. Ceny oddalone najwyżej o domyślne
`0,05 PLN/kWh` mogą utworzyć deterministyczną grupę równoważności, w której
bounded water-fill zmniejsza peak mocy z zachowaniem targetu i wszystkich
dynamicznych ograniczeń. Preferowany automatyczny slot Sprzedaży ma domyślne
minimum `1000 W`; mniejsza pozostałość po redystrybucji jest shortfallem, a nie
zapisem Harmonogramu. Oba progi są konfigurowalne w ustawieniach AI i analizy.

Timestampy cen z UTC lub jawnym offsetem są mapowane na lokalną datę i godzinę
Home Assistant przed podziałem na Dziś/Jutro. Dotyczy to zarówno wejścia Core,
jak i tabel cen karty. Naiwne datetime nadal oznaczają lokalny czas, a przy
jesiennym powtórzeniu godziny obowiązuje deterministyczna polityka first-wins.

Opcjonalne AI pozostaje doradcą. Odpowiedź jest związana z konkretnym planem,
proponowany kandydat jest ponownie symulowany przez lokalny Core i wymaga
zatwierdzenia. AI nie wykonuje bezpośrednich usług Home Assistant ani Deye.

## Wydajność i lifecycle runtime

0.8.0 ogranicza pełne przeliczenia do dokładnej listy rzeczywistych wejść. Własne
sensory wyniku nie tworzą pętli zdarzeń, a zmiana samego timestampu bez zmiany
semantycznej nie publikuje ponownie całego planu. Core, AI, learning i Store są
chronione przez single-flight/coalescing, kosztowne obliczenia działają poza
główną pętlą HA, historia jest kompaktowana, a żądania AI mają limit i cooldown.
Integracja czeka ze startem pracy do gotowości Home Assistant oraz usuwa listenery
i zadania podczas unloadu.

## Diagnostyka

Diagnostyka pokazuje między innymi:

- możliwości i braki wybranego providera;
- oczekiwane i rzeczywiste pola sześciu zakresów TOU;
- stan transakcji, confirmation i rollbacku;
- stan reverse sync;
- expected/physical signature oraz pola rozbieżne podczas reconciliation;
- Planowaną i Wykonaną decyzję Managera;
- skonfigurowany, wykryty i efektywny limit mocy falownika.

## Interfejs i dashboard

Karta 0.8.0 otrzymała skalowalny panel przepływu **Status energii**, rozdzielone
Planowaną i Wykonaną decyzję, pełne widoki Harmonogramu, TOU, cen, Solcast i
Sugestii AI oraz responsywne dialogi poza skalowanym kontenerem. Parser wartości
UI odróżnia prawdziwe zero od braku danych i obsługuje notację naukową. Etykiety
trybów, powodów decyzji i statusów są prezentowane po polsku, a szczegóły
techniczne pozostają dostępne w diagnostyce.

## Aktualizacja z wcześniejszej wersji

1. Wykonaj kopię bezpieczeństwa Home Assistant i dotychczasowego Harmonogramu.
2. Zaktualizuj integrację i uruchom ponownie Home Assistant.
3. Pozwól integracji zakończyć automatyczną migrację wpisu do `1.24`; nie edytuj
   ręcznie `.storage`. Migracja zachowuje stabilne identyfikatory mapowanych encji,
   przebudowuje kontrakty BUY/SELL i nie wykonuje zapisu do falownika.
4. Otwórz opcje integracji, wybierz provider i zweryfikuj urządzenie oraz encje.
5. Sprawdź maksymalną moc falownika i fizyczny zakres encji Max Sell Power.
6. Zweryfikuj cztery mapowania cen, taryfę/OSD oraz opcjonalne encje Solcast.
7. Pozostaw Sterowanie Deye wyłączone podczas pierwszej kontroli diagnostyki.
8. Zweryfikuj osobno Harmonogram, Mapowanie Deye i fizyczne TOU 6/6.
9. Dopiero potem włącz sterowanie i wykonaj pierwszy kontrolowany zapis.
10. W trybie UI/storage DEM automatycznie utworzy albo zaktualizuje zasób karty:

   ```text
   /deye_energy_manager/deye-energy-manager-card.js?v=0.8.0.44
   ```

   Nie kopiuj karty do `/config/www` i nie zmieniaj ręcznie `?v=`. W trybie YAML
   dodaj powyższy URL ręcznie jako moduł JavaScript.

11. Po restarcie wykonaj twarde odświeżenie przeglądarki.

Szczegółowa procedura znajduje się w [INSTALL_PL.md](INSTALL_PL.md).

## Ważne informacje i ograniczenia

- Ręczny edytor fizycznego TOU przyjmuje obecnie granice pełnogodzinne `HH:00`.
- Do slotu N jest startem slotu N+1; zmiana Do modyfikuje sąsiednią granicę.
- Dowolne sześć ręcznych granic, w których sąsiednie zakresy mają identyczny SOC
  i Grid Charge, może nie być odtwarzalne przez algorytm 24 h → 6/6. Wtedy
  round-trip zostaje odrzucony i następuje rollback.
- Custom bez pełnego readbacku 6/6 nie deklaruje pełnej synchronizacji.
- Deye MQTT / Addon pozostaje read-only bez bezpiecznych natywnych encji.
- Integracja nie przełącza globalnego Time Of Use / Use Timer.

Wersja integracji i karty: `0.8.0`. Aktualna rewizja zasobu: `v=0.8.0.44`.

## FuturePlan, plan Dziś/Jutro i jakość danych

- ścisła walidacja oraz diagnostyka świeżości SOC bez sztucznego fallbacku 0%;
- `raw_confidence` i fail-closed `effective_confidence`;
- przejściowy `waiting_data`, ponawianie w aktywnej godzinie i trwały `missed`;
- globalny ranking 48 h z wartością alternatywną energii i rezerwą terminalną;
- dzienny `target_energy_kwh` i fulfillment per `(profil, lokalna data)`, bez
  resetowania ciągłej symulacji SOC o północy;
- egzekwowany kontrakt uczenia `dry_run` / `apply_allowed` / `confidence_cap`;
- zgodny podgląd i payload profilu Charge oraz kontrola aktualności summary AI;
- dynamiczne, koaleskowane przeliczanie pozostałej części dnia.
- FuturePlan przechowuje 24 lekkie, datowane intencje zamiast częściowego patcha;
  brak wpisu specjalnego zawsze oznacza Normalną Pracę. Store/restore i migracja
  starszego selected-only planu zachowują ten kontrakt, a JIT materializuje
  wyłącznie bieżący slot.
- Lifecycle FuturePlan oddziela zapis logiczny, oczekiwanie na falownik i
  fizycznie potwierdzony readback. Ownership/revision chroni późniejsze zmiany
  ręczne i Apply Today, a cleanup usuwa wygasłe datowane Sell/Charge bez catch-up
  i bez powtórki następnego dnia.

## Ceny energii: mapowania, Pstryk i PSE/RCE

- BUY i SELL mają odrębne kontrakty i niezależne zasady braku danych.
- Adapter Pstryk zachowuje pełną cenę brutto bez powtórnego OSD/VAT/usługi.
- Adapter PSE/RCE agreguje wyłącznie kompletne, niepokrywające się interwały
  15-minutowe; respektuje `rce_pln`, `period`, końcowy `dtime` i
  `business_date`, w tym ceny zerowe i ujemne.
- Generic/custom wymaga jawnej semantyki; nieznane dane kończą się statusem
  diagnostycznym i blokadą planowania zamiast cichego zgadywania.
- Optimizer Core, sugestie AI, tabele i cena „Teraz” korzystają ze wspólnego
  `canonical_prices` backendu. Migracja wpisu nie zmienia mapowania encji.
- Stałe opłaty miesięczne pozostają poza kosztem godzinowym; Core optymalizuje
  marginalny koszt zmienny za kWh.

## Taryfy sprzedawców i OSD

- Gdy oba mapowania BUY są puste, użytkownik może jawnie wybrać sprzedawcę jako
  fallback. Zweryfikowane standardowe kontrakty tworzą ceny 24+24 validity-first.
- Katalog rozróżnia 33 grupy taryf G; 21 zwykłych kontraktów sprzedawców ma
  audytowalny skład ceny energii brutto i zmiennego OSD doliczanego dokładnie raz.
- Taryfy specjalne, dynamiczne albo niejednoznaczne pozostają fail-closed. Wspólny
  updater jest atomowy, zachowuje last-known-good i sprawdza nową wersję najwyżej
  raz na 90 dni.

## Sugestie AI i polskie powody decyzji

- Techniczne reason codes są tłumaczone przez jeden centralny mapper warstwy UI.
- Dynamiczne przyczyny `material_live_input_changed:*` mają polskie opisy znanych
  wejść i neutralny fallback bez ujawniania nazwy nieznanego pola.
- Normalne widoki nie dopisują raw `empty_reason_by_day.code`; powody w ekranach
  Przegląd, Dlaczego ten plan oraz Plan i wykonanie używają tego samego mappera.
- Matematyka Core, decyzje, FuturePlan, ceny, taryfy i sterowanie pozostają bez zmian.
