# Deye Energy Manager 0.7.9

Stabilne wydanie oznaczone tagiem `v0.7.9`.

## Optimizer Core i profile

- `allow_partial=false` blokuje niepełny profil, ale pokazuje możliwą energię
  i brakującą część celu.
- `min_net_result` porównuje profil z planem bazowym po kosztach zakupu,
  dystrybucji, stratach, cyklu baterii i wartości energii końcowej.
- `profitable_only` rozróżnia późniejszą sprzedaż, uniknięty import domu,
  jawną rezerwę oraz cel mieszany.
- `purpose`, `deadline`, `charge_missing_only`, `use_corrected_pv` i
  `allow_earlier_grid_charge` mają bezpośredni wpływ na plan.
- Ładowanie może być uzasadnione wyłącznie zdarzeniem późniejszym i przed
  terminem profilu.
- Ceny zerowe i ujemne są poprawnymi danymi; ujemna cena sprzedaży blokuje
  automatyczny eksport z baterii.
- `preserve_pv_room` wylicza miejsce z prognozy PV, obciążenia domu,
  możliwego eksportu, pojemności i ustawionego minimum.

## Wykonanie, pewność i bezpieczeństwo

- `profile_execution` przechowuje cel, plan, wykonanie, pozostałą energię,
  planowany i rzeczywisty SOC, ceny, import, eksport, wynik oraz jakość danych.
- Cykl wykonania zapisuje wszystkie statusy: oczekiwanie, realizację,
  zakończenie, wykonanie częściowe, blokadę, błąd, pominięcie, anulowanie
  i ręczne przejęcie sterowania.
- Pewność uwzględnia pokrycie cen, Solcast, uczenie, próbki domu i PV,
  zagnieżdżoną jakość encji, SOC oraz kompletność taryfy/OSD.
- Miękkie cele końcowego SOC wariantów to 55%, 45% i 30%; nie ma ukrytego
  limitu 1/3/4 godzin sprzedaży.
- Każdy zaakceptowany slot planu na jutro jest ponownie sprawdzany przed
  rozpoczęciem. Niespełniony slot zostaje zablokowany bez zmiany innych slotów.

## Telemetria i historia godzinowa

- Telemetria PV, domu, sieci, baterii, SOC i cen jest próbkowana co minutę.
  Brak odczytu jest zapisywany jako brak danych, a nie jako sztuczne zero.
- Każdy kanał ma niezależnie ocenianą kompletność. Zakończona godzina zachowuje
  energię kanałów, SOC start/koniec/minimum/maksimum/średni, tryb i moc,
  migawkę Solcast i pogody oraz kontrolę bilansu energii.
- Niepełne, ale użyteczne godziny pozostają w historii z odpowiednio mniejszą
  wagą zamiast być bezwarunkowo odrzucane.
- Optimizer Core otrzymuje historię godzinową, bieżący stan i część otwartej
  godziny. Bieżąca godzina jest zakotwiczona na zmierzonym SOC i aktualnych
  mocach, a historyczny SOC pozostaje oddzielony od prognozy.
- Diagnostyka jakości pokazuje liczbę użytecznych godzin, zakres historii oraz
  osobne pokrycie poszczególnych kanałów.

## Sugestie AI

- Backendowy Optimizer Core pozostaje jedynym źródłem planu. Stary planer JS,
  jego martwy widok i alternatywna ścieżka zapisu zostały usunięte. Brak
  backendu daje stan „Brak planu” i blokuje zapis.
- Przegląd pokazuje rankingi Porannej i Wieczornej sprzedaży, ranking kosztu
  zakupu z OSD, cel/plan/wykonanie profili, status i ostrzeżenia.
- Szczegóły ładowania pokazują przeznaczenie, późniejszy cel, oczekiwaną marżę,
  źródło prognozy PV i wyliczone miejsce na produkcję.
- Wykresy mają oś energii od 0 kWh, SOC 0–100%, twarde i efektywne minimum.
- Nowa zakładka **Plan i wykonanie** łączy Dziś, Jutro, 48 h i Historię,
  pokazuje zamrożony plan, akceptację, wdrożenie oraz wynik rzeczywisty.
- Godzinowe archiwum plan/real ma retencję 90 dni. Pełny wybrany dzień jest
  pobierany usługą tylko do odczytu, bez zapisu do harmonogramu lub Deye.
- Komunikaty i odpowiedzi zewnętrznego asystenta są po polsku; błąd 401 ma
  czytelny komunikat o kluczu API.

## Harmonogram pracy

- Po potwierdzeniu zmiany encji tabela odświeża tryb oraz zależne parametry
  właściwego slotu bez wymagania przeładowania strony albo otwierania innego
  panelu.
- Tryb wybrany podczas edycji pojedynczego slotu jest pokazywany
  optymistycznie, a następnie zastępowany stanem potwierdzonym przez Home
  Assistant.
- Przycisk **Zastosuj zmiany** w bocznym panelu edycji zbiorczej zapisuje
  wyłącznie zaznaczone godziny i pola. Trwający zapis blokuje kolejne
  kliknięcie, natomiast błąd zachowuje formularz oraz zaznaczone godziny.
- Poprawki interfejsu nie zmieniają backendu, Optimizer Core, mapowania Deye
  Time Of Use ani logiki sterowania falownikiem.

## Wersja i instalacja

- integracja: `0.7.9`
- karta: `0.7.9`
- aktywna rewizja zasobu: `v=0.7.9.11`
- zasób integracji:
  `/deye_energy_manager/deye-energy-manager-card.js?v=0.7.9.11`
- alternatywnie tylko przy ręcznej kopii:
  `/local/deye-energy-manager-card.js?v=0.7.9.11`

Nie konfiguruj obu zasobów równocześnie.

## Weryfikacja lokalna

- Pełna regresja: `375 passed, 18 subtests passed`.
- Obie kopie karty przechodzą `node --check` i mają identyczny SHA-256.
- Testy zachowania profilu Charge, profilu Normalnej Pracy i harmonogramu
  przechodzą poprawnie.
- Nie wykonywano fizycznych zapisów do falownika ani testów na rzeczywistej
  instalacji Home Assistant.

## Dokumentacja repozytorium

- Nie znaleziono roboczych kopii `*_work`, `*_new`, `card_work.js`, trzeciej
  karty ani duplikatu `optimizer_core.py`.
- Nieaktualne, nieśledzone raporty audytowe i notatki niedoszłego wydania
  `0.7.8` usunięto z katalogu projektu. Historię zmian utrzymuje `CHANGELOG.md`,
  a niniejszy plik opisuje wydanie `0.7.9`.

## Znane ograniczenia

- Plan nadal jest propozycją i wymaga działania użytkownika oraz lokalnej
  walidacji.
- Jakość planu zależy od kompletnych cen, OSD, SOC, Solcast i historii.
- Zewnętrzny asystent AI nie steruje falownikiem i nie zapisuje harmonogramu.
- Walidację wizualną i zachowanie rzeczywistych encji należy sprawdzić w
  testowym Home Assistant przed publikacją.
