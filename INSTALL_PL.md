# Deye Energy Manager 0.7.7 — instalacja

Wymagany Home Assistant: `2026.6` lub nowszy.

## Aktualizacja z 0.7.6 przez HACS

1. W HACS otwórz Deye Energy Manager i wybierz aktualizację do `0.7.7`.
2. Uruchom ponownie Home Assistant.
3. Sprawdź w **Ustawienia i diagnostyka → System**, czy integracja i karta
   pokazują `0.7.7`.
4. Ustaw rewizję zasobu karty na `v=24`, przeładuj zasoby Lovelace i wykonaj
   twarde odświeżenie przeglądarki.
5. W **Historia i dane** sprawdź status migracji, zachowaną liczbę dni oraz
   `history_schema_version = 2`. Migracja jest automatyczna i nie kasuje danych.
6. Przejrzyj mapowanie encji. Nowe PV3 Power i Battery SOH są opcjonalne.
7. Pozostaw nowe profile AI wyłączone, dopóki nie skonfigurujesz ich świadomie.

## Pierwsza konfiguracja planowania 0.7.7

W **Sugestie AI → Ustawienia** skonfiguruj kolejno:

1. Parametry magazynu: pojemność, twarde minimum SOC, rezerwę w kWh, sprawność
   ładowania i rozładowania oraz limity mocy/prądu.
2. Profil domu: preferowane `Load Power`; opcjonalnie kompletne L1/L2/L3 jako
   fallback. Brak pełnego kompletu faz nie jest sumowany częściowo.
3. Profil PV i Solcast. Korekta lokalna rośnie stopniowo wraz z liczbą poprawnych
   próbek i pomija okresy ograniczenia produkcji.
4. **Poranna sprzedaż**: dni, okno, minimalna cena, cel kWh, sposób rozłożenia,
   minimalny SOC po sprzedaży, limit mocy i minimalna pewność.
5. **Wieczorna sprzedaż**: analogicznie; planer liczy ją po wcześniejszym
   zużyciu i wykonaniu porannego profilu.
6. **Ładowanie**: cel SOC lub energia kWh, deadline, źródło, maksymalna
   efektywna cena, limit energii z sieci i zachowanie miejsca na PV.

`Cel kWh` jest limitem energii profilu. `Częściowa realizacja` pozwala zaplanować
mniej, gdy ogranicza to SOC, moc, dostępna liczba godzin lub cena. Profil
sprzedaży nie schodzi poniżej wskazanego SOC. Profil ładowania z opcją zachowania
miejsca na PV pozostawia co najmniej podaną wolną pojemność.

## Taryfa i dystrybucja

Nie konfiguruj godzin taniej taryfy w AI. Wybierz istniejący operator OSD,
taryfę i tryb katalogu w dotychczasowym module. W trybie automatycznym używany
jest jego profil dziś/jutro; w trybie ręcznym – profil użytkownika. Ustaw
poprawnie opcję **Cena zakupu zawiera dystrybucję**, aby koszt nie został
doliczony drugi raz.

## Opcjonalne API AI

Lokalny Optimizer Core działa bez API. Aby włączyć dodatkową ocenę:

1. Otwórz **Sugestie AI → Ustawienia → API**.
2. Wybierz Gemini, OpenRouter, OpenAI, OpenCode albo własny endpoint zgodny z
   OpenAI.
3. Uzyskaj klucz wyłącznie według oficjalnej instrukcji dostawcy i wklej go w
   pole hasła.
4. Wybierz model. Dla własnego dostawcy podaj endpoint `https://`.
5. Ustaw zakres prywatności, zapisz i wybierz **Test połączenia**.
6. Po poprawnym teście uruchom analizę ręcznie.

OpenCode / OpenCode Go jest dostępny tylko przez oficjalny publiczny endpoint
usługi i klucz podany przez użytkownika. Integracja nie korzysta z lokalnego
logowania OpenCode, plików poświadczeń ani poleceń powłoki. Nigdy nie wklejaj
klucza do YAML, dokumentacji ani zgłoszenia diagnostycznego.

Przez pierwsze 7 dni zalecany jest tryb sugestii bez stosowania planu. Statusy
„Zbieranie danych” i „Plan wstępny” są normalne; pełniejsza pewność pojawia się
po 21 i 60 kompletnych dniach. Błąd API nie blokuje planera lokalnego. Status
„Plan zablokowany” zwykle oznacza brak krytycznego SOC lub cen – sprawdź jakość
danych i mapowanie, zamiast omijać zabezpieczenie.

## Instalacja przez HACS

1. Dodaj repozytorium jako niestandardowe repozytorium HACS typu **Integracja**.
2. Zainstaluj Deye Energy Manager.
3. Uruchom ponownie Home Assistant.
4. Przejdź do **Ustawienia → Urządzenia i usługi → Dodaj integrację**.
5. Przejdź przez kreator:
   - wybierz mapowanie automatyczne, ręczne albo zachowanie bieżących ustawień;
   - sprawdź encje sterujące i pomiarowe Deye;
   - wybierz encje cen sprzedaży i zakupu;
   - sprawdź encje Solcast;
   - wybierz prognozę `weather.*` (domyślnie `weather.forecast_home_2`);
   - wykonaj test i potwierdź mapowanie.

Automatyczne mapowanie niczego nie zapisuje bez końcowego potwierdzenia. Kreator służy wyłącznie do wyboru encji Home Assistant. Operatora, taryfę, stawki oraz kierunek znaku mocy sieci i baterii ustawia się później w karcie.

## Karta dashboardu

Dodaj zasób JavaScript:

```text
/deye_energy_manager/deye-energy-manager-card.js?v=24
```

Przy instalacji ręcznej użyj:

```text
/local/deye-energy-manager-card.js?v=24
```

Następnie dodaj kartę ręczną:

```yaml
type: custom:deye-energy-manager-card
```

### Konfiguracja rozmiaru i układu karty

W edytorze karty Lovelace dodaj sekcję `layout:` bezpośrednio pod `type: custom:deye-energy-manager-card`. Wszystkie pola są opcjonalne; nieprawidłowe wartości są zastępowane domyślnymi.

#### Minimalny przykład

```yaml
type: custom:deye-energy-manager-card
```

#### Przykład pełny

```yaml
type: custom:deye-energy-manager-card
layout:
  layout_mode: auto
  dashboard_width: 1280
  center_dashboard: true
  fit_to_width: false
  allow_horizontal_scroll: false
  grid_columns: null
  grid_gap: 16
  section: null
  sections:
    status_energy: true
    prices: true
    solcast: true
    schedule: true
    sales_stats: true
  mobile:
    mode: auto
    preserve_desktop_layout: false
    fit_to_width: true
    allow_horizontal_scroll: false
    grid_columns: 1
    mobile_breakpoint: 768
  prices_ratio: 0.80
  buy_prices_ratio: 0.80
  solcast_ratio: 1.40
  energy_tile_width: 300
  energy_tile_gap: 28
  inverter_scale: 1
  flow_animation_speed: 6
```

#### Telefon (jedna kolumna, brak przewijania poziomego)

```yaml
type: custom:deye-energy-manager-card
layout:
  layout_mode: auto
  allow_horizontal_scroll: false
  mobile:
    mode: grid
    preserve_desktop_layout: false
    grid_columns: 1
    fit_to_width: true
    allow_horizontal_scroll: false
    mobile_breakpoint: 768
```

Na telefonie sekcje cen i Solcast zostaną ułożone pionowo. Główny dashboard nie będzie przewijany poziomo. Poziome przewijanie pozostaje dostępne lokalnie wewnątrz tabeli Harmonogramu oraz listy dni Solcast.

#### Pojedynczy panel

```yaml
type: custom:deye-energy-manager-card
layout:
  layout_mode: single
  section: schedule
```

#### Układ grid

```yaml
type: custom:deye-energy-manager-card
layout:
  layout_mode: grid
  grid_columns: 2
  sections:
    status_energy: true
    prices: true
    solcast: true
    schedule: true
    sales_stats: true
```

#### Ważne uwagi

- `layout_mode: fit` nie skaluje proporcjonalnie całego dashboardu. Włącza tylko dopasowanie zewnętrznego kontenera do szerokości karty przy zachowaniu wewnętrznego układu sekcji.
- `max_scale` i `min_scale` są obecnie zarezerwowane. Są wczytywane przez `layoutConfig()`, ale **nie wpływają na renderowanie**.

#### Zmiana wersji zasobu i odświeżenie cache

Po każdej aktualizacji karty ustaw w zasobie JavaScript parametr `v=24`:

```text
/deye_energy_manager/deye-energy-manager-card.js?v=24
```

jeśli korzystasz z karty dostarczanej przez integrację, albo:

```text
/local/deye-energy-manager-card.js?v=24
```

jeśli skopiowałeś plik ręcznie do `/config/www/`.

Następnie w Home Assistant:
1. przeładuj zasoby Lovelace (trzy kropki w prawym górnym rogu dashboardu → **Odśwież**),
2. wykonaj twarde odświeżenie przeglądarki (`Ctrl + F5` lub `Cmd + Shift + R`).

Test na telefonie:
1. Zamknij aplikację Home Assistant albo kartę przeglądarki i otwórz dashboard ponownie.
2. Sprawdź, czy Ceny sprzedaży, Ceny zakupu i Solcast są ułożone w jednej kolumnie.
3. Upewnij się, że cała strona nie przewija się poziomo.
4. Przewiń osobno tabelę Harmonogramu i listę dni Solcast — ich lokalny poziomy scroll powinien pozostać aktywny.
5. Otwórz i zamknij Ustawienia oraz edycję slotu, aby potwierdzić brak migotania i zmiany pozycji strony.

Błędne wartości w konfiguracji YAML są automatycznie zastępowane bezpiecznymi domyślnymi.

## Aktualizacja z 0.7.5

1. Wykonaj kopię konfiguracji w panelu **System i diagnostyka**.
2. Zaktualizuj integrację i uruchom ponownie Home Assistant.
3. Zmień parametr cache zasobu na `v=24`.
4. Odśwież przeglądarkę przez `Ctrl + F5`.
5. Sprawdź mapowanie encji w opcjach integracji.
6. Otwórz **Ustawienia i diagnostyka → Taryfa i dystrybucja**, wybierz operatora i taryfę, a następnie użyj przycisku **Zapisz ustawienia taryfy**.
7. Zweryfikuj diagnostykę i wykonaj pierwszy test przy niskich limitach mocy.
8. Po Stop Sell lub zatrzymaniu awaryjnym użyj **System i diagnostyka → Włącz Manager i harmonogram**. Przycisk włącza `Schedule` i Scheduler, lecz nie zmienia szablonu ani istniejących slotów `Charge`; tylko **Ładowanie z sieci: TAK** w konkretnym slocie `Charge` zezwala na ładowanie z sieci.

Po aktualizacji otwórz **Ustawienia → Urządzenia i usługi → Deye Energy Manager → Konfiguruj**. Kreator zachowa dotychczasowe mapowanie i pozwoli uzupełnić encje cen, Solcast oraz pogody. Ustawienia OSD i taryfy zostały przeniesione do karty i nie są już częścią mapowania encji.

## Wymagane i zalecane encje

Wymagane dla bezpiecznego sterowania są: tryb pracy Deye, maksymalna moc sprzedaży, maksymalny prąd rozładowania, prąd ładowania baterii, prąd ładowania z sieci oraz bieżący odczyt SOC baterii. Cena sprzedaży jest wymagana tylko przez aktywny slot `Selling First`, jeżeli ma odpowiedni limit. Sloty `Zero Export` mogą działać bez aktualnego SOC i ceny. Pozostałe encje pomiarowe są zalecane zgodnie z używanymi funkcjami.

Prognoza pogody jest opcjonalnym wsparciem Solcast. Jeżeli `weather.forecast_home_2` nie istnieje, wybierz inną encję z domeny `weather`, która udostępnia prognozę godzinową. Integracja pobiera prognozy godzinowe i dzienne przez `weather.get_forecasts`; brak osobnej prognozy dziennej jest podsumowywany z dostępnych danych godzinowych.

## Kontrola po instalacji

1. W diagnostyce sprawdź, czy wymagane encje mają stan `OK`.
2. Porównaj znaki `Sieć` i `Bateria` z kartą falownika.
3. W zakładce **Taryfa i dystrybucja** wybierz tryb automatyczny lub ręczny, operatora i taryfę, ustaw znaki przepływu, a następnie kliknij **Zapisz ustawienia taryfy**.
4. Sprawdź profil 48 godzin: strefy na dziś i jutro, rodzaj dnia, sezon oraz łączną stawkę dystrybucji.
5. Jeżeli encja ceny zakupu zawiera dystrybucję, zaznacz **Cena zakupu zawiera już dystrybucję**.
6. Sprawdź stan i wersję katalogu. Automatyczna kontrola odbywa się przy starcie i co 7 dni; przycisk **Sprawdź aktualizację katalogu** uruchamia ją ręcznie. Przy błędzie pozostaje ostatnia poprawna kopia, a ostatecznym zabezpieczeniem jest katalog dostarczony z integracją.
7. Sprawdź, czy dashboard reaguje na zmianę mocy bez czekania jednej minuty.
8. Po zakończeniu pełnego dnia sprawdź trafność historyczną; w ciągu dnia używaj pola `Realizacja dzisiaj`.
9. Otwórz **Sugestie AI** i sprawdź zakładkę **Jakość danych**. Brak cen jutra lub prognozy pogody powinien być jawnie opisany jako brak danych.
10. W **Proponowanych zmianach** sprawdź osobno **Dziś** i **Jutro**. Plan jutra jest tylko zapisywany; nie zmienia od razu powtarzalnego Deye Time Of Use.
11. Sprawdź wykresy **Plan na dziś**, **Plan na jutro** i **Plan energii 48h**. Każda godzina powinna mieć ikonę pogody; lewa oś opisuje energię w kWh, prawa SOC w procentach, a dolne pasy sprzedaż, ładowanie i tanią dystrybucję. Po najechaniu lub dotknięciu godziny powinny być widoczne: produkcja rzeczywista, prognoza Solcast, prognoza skorygowana, przedział prognozy, zużycie, SOC, działanie i pogoda. Brak pomiaru powinien być opisany jako brak danych.
12. W sekcji **Pogoda** przełącz widok **Dzienna/Godzinowa** i potwierdź, że jako źródło widoczna jest wybrana encja `weather.*`.

Tryb ręczny pozwala wpisać własne stawki i przedziały tanich godzin. W trybie automatycznym pory roku, weekendy oraz polskie dni ustawowo wolne wynikają z wybranego profilu OSD. Katalog nie zastępuje umowy — przed uruchomieniem ładowania z sieci porównaj wybrane dane z dokumentami operatora.

Po ręcznym skopiowaniu nowej karty do `/config/www/` użyj zasobu `/local/deye-energy-manager-card.js?v=24`, przeładuj zasoby Lovelace i wykonaj `Ctrl + F5`. Jeśli korzystasz z karty dostarczanej przez integrację, użyj adresu `/deye_energy_manager/deye-energy-manager-card.js?v=24`.

Plan na jutro wymaga ręcznego zaznaczenia godzin i potwierdzenia przyciskiem **Zaplanuj wybrane na jutro**. Plan jest zapisany z datą i pozostaje oczekujący po restarcie Home Assistant. W dniu wykonania integracja sprawdza encje sterujące oraz tylko SOC i ceny wymagane przez zatwierdzony slot `Selling First`, po czym stosuje dokładnie zaakceptowane pozycje. Nie tworzy planu zastępczego. W razie błędu plan jest oznaczony jako nieudany, a falownik otrzymuje pełne **Ustawienia domyślne** 1:1.

W 0.7.6 warunek SOC jest sprawdzany wyłącznie dla aktywnego slotu `Selling First`, gdy ma ustawiony minimalny SOC sprzedaży. Brakujący lub nieprawidłowy SOC (analogicznie cena) jest błędem tylko dla slotu, który wymaga tego warunku; prawidłowy odczyt poniżej progu jedynie wstrzymuje sprzedaż bez błędu harmonogramu. Nie blokuje slotu `Zero Export` ani nie jest zastępowany sztuczną wartością.

**Minimalny SOC sprzedaży** jest warunkiem wyłącznie dla `Selling First`; nie trafia do fizycznego Deye TOU. Okno slotu pokazuje tylko jedno pole SOC odpowiednie dla trybu: minimalny SOC sprzedaży, SOC Deye TOU albo docelowy SOC Charge. Po zapisie falownik może opublikować nowy stan z opóźnieniem: integracja nasłuchuje zmian encji Deye i wykonuje odczyt kontrolny po 0,5, 1 i 2 sekundach, maksymalnie przez 12 sekund, bez ponownego wysyłania tej samej transakcji; w tym czasie diagnostyka pokazuje oczekiwanie, a nie błąd.

Jeżeli poprzednia konfiguracja nie zawiera wiarygodnie zapisanego **SOC baterii Deye (TOU)**, wprowadź go świadomie dla każdego slotu niebędącego `Charge`. Do czasu potwierdzenia integracja blokuje fizyczny zapis mapowania TOU, zamiast kopiować minimalny SOC sprzedaży albo podstawić `0`.

## Ustawienia ładowania

W **Ustawienia i diagnostyka → Ustawienia Trybów → Ustawienia ładowania** zapisz szablon dla nowych slotów `Charge`: prąd ładowania, prąd rozładowania, prąd ładowania z sieci, zgoda na ładowanie z sieci oraz **Docelowy SOC**. Szablon jest kopiowany przy pierwszej zmianie trybu danego slotu na `Charge`. Od tej chwili wartości slotu można edytować ręcznie i mają one pierwszeństwo; późniejsza zmiana szablonu ich nie nadpisze. W oknie slotu `Charge` dostępny jest przycisk **Wczytaj ponownie ustawienia ładowania**, który ponownie skopiuje aktualny szablon tylko do tego slotu. Jedyną zgodą na Grid Charge jest przełącznik **Ładowanie z sieci: TAK** w danym slocie Charge. Przy wartości `NIE` Grid Charge pozostaje wyłączone nawet przy dodatnim limicie prądu; bateria może ładować się z PV.

Przycisk **Zapisz ustawienia ładowania** zapisuje cały profil jako jeden rekord przez dedykowaną usługę backendu, niezależnie od tego, czy wszystkie encje pomocnicze są w danej chwili widoczne w Home Assistant. Po zamknięciu okna, ponownym otwarciu karty lub restarcie Home Assistant wszystkie zapisane wartości profilu powinny pozostać bez zmian. Formularz korzysta również z zapisanego profilu w atrybutach statusu managera, jeśli pomocnicza encja nie opublikowała jeszcze stanu. Tabela harmonogramu pokazuje zgodę **Ładowanie z sieci** zawsze jako **TAK** albo **NIE**. Jeżeli walidacja albo zapis się nie powiedzie, integracja zachowuje ostatni poprawny profil i wyświetla błąd.

Pomocnicze encje profili (`charge_profile_*`, `normal_profile_*`) mogą być wyłączone w rejestrze encji. Integracja nie zmienia automatycznie ich stanu. Ich brak lub wyłączenie nie blokuje zapisu profili ani kopiowania szablonów Charge — źródłem prawdy pozostają usługi backendu i atrybuty `sensor.deye_energy_manager_manager_status`.

Zakładka **Deye Time Of Use** udostępnia bezpośrednią edycję sześciu fizycznych zakresów falownika. Jest to ścieżka dla świadomej konfiguracji i diagnostyki; późniejsze zastosowanie Harmonogramu sprzedaży może ponownie zapisać te zakresy zgodnie z mapowaniem 24 h.

Stop Sell, zatrzymanie awaryjne oraz błąd sterowania nie zerują automatycznie mocy ani prądów Deye. Integracja stosuje 1:1 pełny zestaw zapisany w **Ustawieniach domyślnych**, włącznie z trybem `Zero Export To CT`, `Zero Export To Load` albo `Selling First`. Integracja nie odgaduje topologii instalacji i nie zastępuje wybranego trybu innym. Przycisk **Zastosuj ustawienia domyślne teraz** pozwala wykonać świadome ręczne przywrócenie.
