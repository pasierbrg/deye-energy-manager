# Deye Energy Manager 0.8.0 — instalacja i aktualizacja

Ten dokument prowadzi przez instalację, aktualizację i pierwszy bezpieczny zapis.
Opis funkcji znajduje się w [README.md](README.md), a zmiany wydania w
[RELEASE_NOTES_0.8.0.md](RELEASE_NOTES_0.8.0.md).

## Wymagania

- Home Assistant 2026.6 lub nowszy;
- dostęp do katalogu `/config` i możliwość restartu Home Assistant;
- działające encje falownika udostępnione przez wspierany provider;
- HACS albo możliwość ręcznego skopiowania integracji;
- przeglądarka umożliwiająca twarde odświeżenie cache karty.

Pełne sterowanie wymaga encji trybu pracy, Max Sell Power, prądu rozładowania,
prądu ładowania baterii, prądu ładowania z sieci i SOC baterii. Pełne fizyczne
Deye Time Of Use wymaga sześciu startów, sześciu wartości SOC i sześciu pól Grid
Charge/source. Cena i Solcast są wymagane tylko przez funkcje, które ich używają.

## Kopia bezpieczeństwa przed aktualizacją

Przed aktualizacją:

1. wykonaj pełną kopię zapasową Home Assistant;
2. zapisz aktualne wartości fizycznych sześciu zakresów Deye TOU;
3. zrób zrzuty Harmonogramu, ustawień domyślnych i profili;
4. zanotuj provider, urządzenie falownika i ręczne mapowanie encji;
5. wyłącz **Sterowanie Deye**, aby aktualizacja nie rozpoczęła nowej operacji.

Nie edytuj ręcznie plików `.storage`. Kopia Home Assistant jest właściwą metodą
zabezpieczenia wpisu konfiguracji i danych integracji.

## Instalacja przez HACS

1. Otwórz **HACS → Integracje → Niestandardowe repozytoria**.
2. Dodaj `https://github.com/pasierbrg/deye-energy-manager` jako typ
   **Integracja**.
3. Wyszukaj **Deye Energy Manager** i wybierz instalację.
4. Uruchom ponownie Home Assistant.
5. Przejdź do **Ustawienia → Urządzenia i usługi → Dodaj integrację**.
6. Wyszukaj **Deye Energy Manager** i rozpocznij konfigurację.

Po aktualizacji istniejącej instalacji również wykonaj pełny restart Home
Assistant, nie tylko przeładowanie YAML.

## Instalacja ręczna

1. Skopiuj katalog:

   ```text
   custom_components/deye_energy_manager
   ```

   do:

   ```text
   /config/custom_components/deye_energy_manager
   ```

2. Upewnij się, że pliki zostały zastąpione jako jeden spójny zestaw 0.8.0.
3. Uruchom ponownie Home Assistant.
4. Dodaj albo przeładuj integrację.

Nie mieszaj plików backendu z różnych wersji.

## Aktualizacja z 0.7.x

Po pierwszym uruchomieniu 0.8.0 integracja automatycznie migruje wpis konfiguracji
do wersji `1.24`. Migracja zachowuje stabilne identyfikatory zmapowanych encji,
przebudowuje niezależne kontrakty BUY/SELL, uzupełnia bezpieczne domyślne pola
sprzedawcy i przenosi starsze ustawienia bez uruchamiania zapisu do falownika.
Starszy selected-only plan Jutro jest odtwarzany jako pełna, datowana intencja
24 h z Normalną Pracą dla pozostałych godzin.

Nie edytuj numeru migracji ani rekordów `.storage` ręcznie. Jeżeli migracja nie
może jednoznacznie rozwiązać encji lub semantyki ceny, funkcja pozostaje
zablokowana fail-closed i wskazuje brak w diagnostyce zamiast wybierać inną encję.

## Wybór providera i urządzenia

Pierwszy krok kreatora wybiera sposób komunikacji:

- **ESPHome Deye Inverter — Lewa-Reka** — referencyjne pełne sterowanie;
- **Solarman** — encje Program N Time/SOC/Charging;
- **Sunsynk** — encje ProgN time/capacity/charge;
- **Mapowanie niestandardowe** — dowolne poprawne encje HA;
- **Deye Inverter MQTT / Addon** — profil read-only bez bezpiecznych zapisów.

Następnie wybierz konkretne urządzenie falownika z rejestru Home Assistant.
Automatyczne wykrywanie analizuje tylko encje tego urządzenia. Niejednoznaczne
lub brakujące pola należy wskazać ręcznie albo świadomie pozostawić puste.

Przed zatwierdzeniem sprawdź ekran capabilities. Powinien jasno wskazać, które
funkcje są kompletne, ograniczone albo tylko do odczytu.

## Mapowanie encji

### Sterowanie podstawowe

Sprawdź co najmniej:

- tryb pracy Deye;
- Max Sell Power;
- maksymalny prąd rozładowania;
- prąd ładowania baterii;
- prąd ładowania z sieci;
- bieżący SOC baterii.

### Fizyczne Deye Time Of Use

Dla każdego slotu 1–6 sprawdź:

- start;
- SOC Deye TOU;
- Grid Charge / źródło ładowania.

Pole **Do** nie ma osobnej encji: Do slotu N jest startem slotu N+1, a Do slotu
6 jest startem slotu 1.

Provider Custom może być zapisany częściowo, lecz niepełny readback nie otrzyma
statusu pełnej synchronizacji i nie pozwoli zapisać brakujących pól.

Integracja nie wymaga globalnego przełącznika Time Of Use i nie przełącza
automatycznie `Time Of Use`, `Use Timer` ani odpowiednika globalnego.

## Maksymalna moc falownika

Ustaw rzeczywisty maksymalny limit AC falownika. Backend porównuje go również z
zakresem encji Max Sell Power:

- encja może publikować moc w W albo kW;
- wartość jest przeliczana do natywnej jednostki przed zapisem;
- 0 W jest poprawną świadomą wartością;
- wartości ponad efektywnym limitem są odrzucane albo ograniczane zgodnie z
  daną ścieżką sterowania.

Nie wpisuj mocy większej od możliwości konkretnego falownika i instalacji.

## Ceny energii, taryfa i Solcast

W kroku **Encje cen energii** skonfiguruj niezależnie cztery opcjonalne mapowania:
BUY Today, BUY Tomorrow, SELL Today i SELL Tomorrow. Jawnie puste pole pozostaje
puste po restarcie. Stabilne powiązanie Entity Registry zachowuje mapowanie po
zmianie nazwy tej samej encji, ale przełączenie na inną encję buduje jej adapter
i schema od nowa.

- Pstryk AIO jest rozpoznawany jako cena all-in brutto i nie otrzymuje drugiego
  doliczenia OSD, VAT ani opłaty usługowej;
- PSE/RCE wymaga poprawnych Today/Tomorrow; kompletne kwadranse są agregowane do
  godzin, a bieżący sensor prosumencki SELL nie jest prognozą na kolejne godziny;
- Generic/Custom wymaga jawnej jednostki, podstawy, roli ekonomicznej i pól czasu;
  brak jednoznacznej semantyki blokuje planowanie.

Jeżeli oba BUY są świadomie puste, możesz jawnie wybrać sprzedawcę w **Taryfa i
dystrybucja**. Zweryfikowana standardowa taryfa tworzy BUY 24+24 z ceny energii
brutto i zmiennego OSD dodanego dokładnie raz. Taryfy specjalne lub dynamiczne bez
jednoznacznego kontraktu pozostają zablokowane. Katalog taryf aktualizuje się
rzadko i atomowo; przy błędzie zachowuje ostatnią poprawną wersję.

W kroku **Solcast** wskaż encje używane przez instalację, przede wszystkim
prognozę Today/Tomorrow oraz bieżącą moc; pozostałe dni, prognoza pozostała i dane
szczytu są opcjonalne. W osobnym kroku można wskazać encję pogody. Brak Solcast
nie blokuje sterowania ręcznego, lecz ogranicza funkcje planu wymagające prognozy.

## Karta dashboardu

Karta jest dostarczana razem z integracją. W standardowym trybie UI/storage DEM
automatycznie tworzy albo aktualizuje wyłącznie własny zasób Lovelace. Po
aktualizacji i restarcie nie otwieraj **Dashboardy → Zasoby**, nie kopiuj pliku
do `/config/www` i nie zmieniaj ręcznie `?v=`.

### Tryb UI/storage — automatyczny zasób

Kanoniczny zasób zarządzany przez DEM:

```text
/deye_energy_manager/deye-energy-manager-card.js?v=0.8.0.44
```

Istniejący jednoznaczny wpis `/local/deye-energy-manager-card.js?...` zostanie
zaktualizowany w miejscu do powyższego URL. Integracja nie usuwa automatycznie
niejednoznacznych duplikatów i nie zmienia zasobów innych kart.

### Tryb YAML — konfiguracja ręczna

DEM nie modyfikuje konfiguracji YAML. Dodaj w niej ręcznie kanoniczny bundled
zasób jako moduł JavaScript:

```text
/deye_energy_manager/deye-energy-manager-card.js?v=0.8.0.44
```

### Legacy `/config/www` — compatibility/manual fallback

Root `www/deye-energy-manager-card.js` w repozytorium jest kopią zgodności i
deweloperską, a nie źródłem runtime standardowej instalacji. Tylko gdy istniejąca
ręczna konfiguracja musi pozostać przy `/local/`, skopiuj ten plik do
`/config/www/` i dodaj:

```text
/local/deye-energy-manager-card.js?v=0.8.0.44
```

Aktualna rewizja zasobu to `v=0.8.0.44`. W trybie storage przyszłe aktualizacje
DEM zmienią ją automatycznie. W trybie YAML wartość musi odpowiadać rewizji z
zainstalowanej wersji integracji.

Po aktualizacji:

1. przeładuj zasoby Lovelace;
2. wykonaj `Ctrl+F5` na komputerze;
3. wyczyść cache aplikacji lub przeglądarki na telefonie;
4. sprawdź wersję i rewizję w diagnostyce karty.

Kontrola po aktualizacji:

- w UI/storage istnieje dokładnie jeden zasób DEM pod kanonicznym URL `.44`;
- nie dodano drugiego wpisu ręcznego ani równoległego `/local/`;
- główna karta Solcast i **Historia i dane** pokazują tę samą realizację dnia;
- trafność historyczna pozostaje osobną metryką od bieżącej realizacji.

## Pierwsze uruchomienie

Przed uruchomieniem Harmonogramu pracy i Optimizer Core skonfiguruj ustawienia
domyślne falownika oraz profile Ładowania i Normalnej Pracy. Wszystkie tryby,
moce, prądy i poziomy SOC muszą być zgodne z parametrami falownika i magazynu
energii, warunkami operatora OSD oraz mocą i warunkami przyłączenia
mikroinstalacji. Nie kopiuj wartości widocznych na przykładach ani zrzutach
ekranu — ustawienia muszą odpowiadać konkretnej instalacji.

Po restarcie pozostaw **Sterowanie Deye = Wyłączone** i wykonaj kontrolę:

1. sprawdź odczyty energii, SOC, ceny i Solcast;
2. otwórz diagnostykę providera i potwierdź właściwe urządzenie;
3. sprawdź skonfigurowany, wykryty i efektywny limit mocy;
4. przejrzyj wszystkie 24 godziny Harmonogramu;
5. sprawdź Mapowanie Deye i liczbę fizycznych zakresów;
6. porównaj actual i expected dla Deye Time Of Use 6/6;
7. usuń wszystkie stany unknown/unavailable przed pierwszym zapisem;
8. dopiero potem włącz Sterowanie Deye.

Przy wyłączonym sterowaniu monitoring, Harmonogram, Mapowanie, Solcast, AI,
Optimizer Core i diagnostyka nadal działają. Nie są wykonywane fizyczne zapisy.

## Test Harmonogramu pracy

1. Otwórz pojedynczy slot.
2. Zmień wartość i wybierz **Anuluj** — stan backendu nie powinien się zmienić.
3. Otwórz ponownie, wykonaj niewielką bezpieczną zmianę i wybierz **Zapisz**.
4. Sprawdź, czy dialog czeka na potwierdzenie backendu.
5. Zweryfikuj osobno:
   - `minimum_sell_soc` jako próg zatrzymania sprzedaży;
   - `tou_soc` jako fizyczny SOC Deye TOU;
   - `charge_enabled` jako zgodę Grid Charge.

Zmiana każdego pola formularza nie zapisuje natychmiast encji falownika. Jeden
Zapisz tworzy jeden logiczny patch.

## Test Mapowania Deye

Mapowanie fizyczne jest segmentowane według `tou_soc` i `charge_enabled`.
Sprawdź:

- czy plan tworzy najwyżej sześć kolejnych zakresów;
- czy wartości Od/Do pokrywają pełne 24 godziny;
- czy SOC i Grid Charge odpowiadają godzinom Harmonogramu;
- czy `minimum_sell_soc`, tryb, moc i prądy nie są błędnie traktowane jako
  granice fizycznego TOU.

Więcej niż sześć naturalnych zakresów powinno zablokować zapis przed pierwszą
zmianą falownika.

## Test Deye Time Of Use

Ręczny edytor działa obecnie na pełnych godzinach `HH:00`.

1. Wybierz jeden fizyczny slot.
2. Zmień tylko jedno bezpieczne pole.
3. Zapisz i sprawdź status confirmation.
4. Zweryfikuj, że zapisano wyłącznie zmienioną encję.
5. Sprawdź reverse sync: Harmonogram może zaktualizować tylko `tou_soc`,
   `charge_enabled` i przypisanie godzin.
6. Potwierdź, że tryb, enabled, `minimum_sell_soc`, moc i prądy się nie zmieniły.

Zmiana Do modyfikuje start następnego fizycznego slotu. Dla slotu 6 zmienia
start slotu 1.

## Jak rozpoznać provider read-only

W diagnostyce provider read-only ma brak możliwości fizycznego zapisu TOU i
status `read_only`. Pola mogą pokazywać rzeczywiste odczyty, ale przyciski zapisu
są niedostępne. Deye Inverter MQTT / Addon nie otrzymuje zastępczych komend MQTT.

Jeżeli odczyt fizyczny różni się od Harmonogramu, mismatch jest raportowany, ale
nie jest nadpisywany.

## Pierwszy bezpieczny zapis

Pierwszy zapis wykonuj przy dostępie do fizycznego falownika lub jego aplikacji:

1. upewnij się, że nie trwa inna automatyzacja zmieniająca TOU;
2. włącz Sterowanie Deye;
3. zmień jedną niekrytyczną wartość;
4. obserwuj status writing → confirming → confirmed/in_sync;
5. sprawdź fizyczny odczyt w niezależnym źródle;
6. w razie błędu sprawdź status rollback i wszystkie sześć zakresów.

Timeout confirmation wynosi do 30 sekund. Status krytyczny oznacza, że pełnego
rollbacku nie udało się potwierdzić — wtedy natychmiast sprawdź falownik.

## Zewnętrzne zmiany TOU

Zmiana wykonana przez Solarman, Sunsynk, ESPHome, inną automatyzację lub
Narzędzia deweloperskie nie jest automatycznie kopiowana do Harmonogramu.

- Sterowanie aktywne: Manager odczyta 6/6 i naprawi tylko różnice;
- Sterowanie wyłączone: pokaże mismatch bez zapisu;
- emergency stop: pokaże blokadę bez korekty;
- unknown/unavailable: poczeka na wiarygodny readback;
- read-only: pozostawi fizyczny stan bez zmian.

## Diagnostyka

W **Ustawienia i diagnostyka** sprawdź:

- provider, urządzenie i brakujące encje;
- capabilities każdego pola TOU;
- Planowaną i Wykonaną decyzję Managera;
- stan Sterowania Deye;
- `tou_transaction` i ostatni błąd confirmation/rollback;
- `tou_reverse_sync`;
- `tou_reconciliation`, w tym expected/physical signature, `in_sync`,
  `readback_complete`, `mismatched_fields` i blokady;
- fizyczne actual/expected/status wszystkich sześciu zakresów.

## Typowe problemy

### Karta pokazuje starą wersję

W trybie UI/storage uruchom ponownie lub przeładuj integrację i sprawdź, czy
istnieje dokładnie jeden zasób DEM pod kanonicznym URL. Nie edytuj `?v=` ręcznie.
W trybie YAML sprawdź adres, parametr `v=0.8.0.44`, przeładuj zasoby Lovelace i
wykonaj twarde odświeżenie. Nie używaj równocześnie ścieżki `/local/` i
`/deye_energy_manager/`.

### TOU pozostaje waiting_readback

Sprawdź wszystkie 18 fizycznych pól 6/6. Każdy start, SOC i Grid Charge musi być
dostępny i poprawnie znormalizowany przez provider.

### FuturePlan oczekuje na falownik

`physical_pending` nie oznacza wykonania. Potwierdzenie pojawi się dopiero po
fizycznym zapisie i readbacku. Nie ma catch-up po końcu slotu; późniejsza zmiana
ręczna lub Apply Today ma pierwszeństwo nad wcześniej zaakceptowanym planem.

### Mapowanie wymaga więcej niż sześciu zakresów

Zmniejsz liczbę kolejnych zmian `tou_soc` albo `charge_enabled` w Harmonogramie.
Tryb, moc i próg zatrzymania sprzedaży nie wpływają na segmentację.

### Reverse sync zgłasza błąd round-trip

Sąsiednie fizyczne zakresy mogą mieć identyczny SOC i Grid Charge, a ich ręczna
granica nie jest wtedy przechowywana przez model godzinowy 24 h. Backend wycofuje
zmianę zamiast zapisać niejednoznaczny Harmonogram.

### Sterowanie pozostaje Wyłączone

Sprawdź diagnostykę aktywnej transakcji i błędu wyłączania. Po usunięciu problemu
włącz sterowanie świadomie; Manager porówna readback i wykona diff-only.

### Lokalna kontrola Optimizer Core po aktualizacji

W zakładce Sugestie AI sprawdź status i wiek SOC, tryb uczenia oraz powód braku
propozycji. W trybie `dry-run` przycisk wdrożenia musi być nieaktywny. Przycisk
**Zastosuj wybrane na dziś** traktuje zaznaczone pozycje jako jedyne akcje
specjalne i ustawia wszystkie pozostałe godziny dzisiejszego planu na Normalną
Pracę; odznaczenie nie zachowuje starej Sprzedaży ani Ładowania. Po zatwierdzeniu
testowego planu na jutro potwierdzenie ma zawierać datę, strategię i godziny.
Zaznaczone pozycje są jedynymi specjalnymi akcjami Jutra, a pozostałe godziny
pełnego targetu 24 h mają intencję Normalna Praca. Samo zatwierdzenie nie zmienia
dzisiejszego Harmonogramu i nie zapisuje niczego do Deye; wykonanie następuje
jutro JIT tylko dla aktualnego slotu. Chwilowo niedostępny SOC lub cena daje
`waiting_data`, odzyskanie
danych uruchamia ponowną walidację, a okno pominięte podczas offline daje
`missed`. Zwykła kompletność telemetrii nie oznacza wykonania zatwierdzonej akcji.

W widoku **Dlaczego ten plan?** porównaj osobno Dziś i Jutro. Cel energii profilu
jest dzienny, więc oba aktywne dni pokazują pełny skonfigurowany target; plan,
shortfall i przyczyna muszą odnosić się do tej samej lokalnej daty.

W **Ustawienia i diagnostyka → AI i analiza → Ogólne** dostępne są dwa parametry
strategii `best_hours`:

- **Minimalna moc automatycznej sprzedaży** — domyślnie `1000 W`; dotyczy planu
  automatycznego i nie ogranicza ręcznego sterowania;
- **Różnica ceny uznawana za zbliżoną** — domyślnie `0,05 PLN/kWh`; pozwala Core
  łagodniej rozłożyć moc między ekonomicznie podobne godziny.

Wyraźnie droższa godzina nadal ma pierwszeństwo. Wyrównanie podobnych cen zawsze
respektuje SOC, rezerwę, PV, obciążenie domu i fizyczne limity mocy. Preferowany
plan nie zapisuje automatycznego slotu Sprzedaży poniżej skonfigurowanego minimum.

### Kontrola kontraktów źródeł cen po aktualizacji

Po restarcie wpis konfiguracji zostanie bezpiecznie zmigrowany do niezależnych
kontraktów BUY i SELL bez zmiany identyfikatorów encji. Otwórz **Ustawienia i
diagnostyka → Taryfa i dystrybucja**, sprawdź adapter oraz oba kontrakty i zapisz:

- dla Pstryk pozostaw adapter Pstryk; cena jest all-in brutto i nie wymaga
  ręcznego doliczania dystrybucji;
- dla PSE/RCE ustaw osobne encje Today i Tomorrow dla BUY, podstawę brutto/netto
  oraz jednostkę publikowaną przez integrację; sensor bieżącej ceny prosumenckiej
  SELL pozostanie tylko informacją bieżącą;
- dla generic/custom jawnie wskaż jednostkę, podstawę, semantykę oraz pola listy,
  wartości i czasu. Status `unknown_*`, `ambiguous_price_source`, niepełne 60 min
  albo overlap blokują użycie ceny.

Sekcja **Kanoniczne ceny backendu** pokazuje adapter, jednostkę, podstawę,
pokrycie Today/Tomorrow, status i końcową cenę bieżącej godziny. Po aktualizacji
uruchom ponownie lub przeładuj integrację; w trybie storage DEM sam ustawi
`v=0.8.0.44`. Następnie wyczyść cache karty i wykonaj checklistę testu na własnym
Home Assistant.
