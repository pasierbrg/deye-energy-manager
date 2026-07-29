# Deye Energy Manager 0.7.7

Wydanie 0.7.7 rozwija Sugestie AI w lokalny, deterministyczny system planowania.
Optimizer Core tworzy plan bazowy i trzy warianty 48 h, symuluje przepływy oraz
SOC, liczy pełny wynik netto i nie zapisuje niczego do falownika bez istniejącej
walidacji i ręcznego zatwierdzenia.

## Najważniejsze nowości

- lokalny profil domu 7×24 i korekta prognozy PV miesiąc×godzina;
- osobne prognozy Solcast initial/latest/corrected i ochrona uczenia przed
  curtailmentem;
- sekwencyjny model SOC 48 h z rezerwą, sprawnościami i limitami;
- plan bazowy, wariant bezpieczny, zrównoważony i maksymalny zysk;
- profile Poranna sprzedaż, Wieczorna sprzedaż i Ładowanie;
- rozbicie finansowe obejmujące import, eksport, dystrybucję, straty, cykl
  baterii i końcową wartość energii;
- rozszerzona jakość danych, źródła/fallbacki i migracja historii do schematu v2;
- opcjonalny asystent przez Gemini, OpenRouter, OpenAI, OpenCode lub własny
  zgodny endpoint HTTPS.

## Bezpieczeństwo i prywatność

Zewnętrzny model jest wyłącznie asystentem opisowym. Nie ma dostępu do warstwy
zapisu Deye, nie stosuje alternatywy i nie zastępuje Safety Engine. Klucz API nie
jest ujawniany w encjach, historii ani diagnostyce. Payload jest ograniczony do
zagregowanych danych godzinowych i nie zawiera lokalizacji, identyfikatorów
urządzeń/encji ani surowej historii.

OpenCode / OpenCode Go działa warunkowo przez oficjalny publiczny endpoint i
klucz usługi wprowadzony przez użytkownika. Integracja nie używa lokalnego
logowania OpenCode i nie uruchamia lokalnego agenta ani poleceń powłoki.

## Aktualizacja

1. Zaktualizuj integrację przez HACS.
2. Uruchom ponownie Home Assistant.
3. Ustaw rewizję zasobu karty na `v=24` i wykonaj twarde odświeżenie.
4. Sprawdź w diagnostyce wersję `0.7.7` i migrację historii do schematu v2.
5. Skonfiguruj profile i pozostaw je wyłączone do czasu świadomej walidacji.

Migracja zachowuje historię, liczbę zapisanych dni, mapowania, taryfę, ustawienia
i harmonogram. Nowe profile użytkownika są domyślnie wyłączone.

## Okres uczenia

Pierwsze 0–2 pełne dni to zbieranie danych, 3–6 dni daje plan wstępny, 7–20 dni
wstępne uczenie, 21–59 dni profil podstawowy, a 60+ dni profil rozszerzony.
Zalecamy pracę w trybie sugestii co najmniej przez pierwszy tydzień.

## Znane ograniczenia

- API AI jest opcjonalne i zależy od dostępności, limitów oraz modelu dostawcy;
  awaria API nie wpływa na lokalny plan.
- Test fizycznego zapisu i potwierdzenia zależy od konkretnego falownika oraz
  mapowania Home Assistant; release zachowuje dotychczasową warstwę confirm/retry.
- Jakość pierwszych prognoz jest celowo ograniczona do czasu zebrania historii.
