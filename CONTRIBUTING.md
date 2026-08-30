# Współtworzenie Deye Energy Manager

Dziękujemy za pomoc w rozwoju projektu.

## Zgłoszenia błędów

Do zgłoszenia dołącz:

- wersję Home Assistant i Deye Energy Manager;
- model falownika;
- stan sensora diagnostycznego integracji;
- oczekiwane i rzeczywiste zachowanie;
- logi bez danych poufnych;
- informację, czy problem dotyczy Sprzedaży, Ładowania, Harmonogramu czy Deye Time Of Use.

## Zmiany w kodzie

1. Utwórz osobną gałąź.
2. Nie dodawaj `__pycache__`, plików `.pyc` ani danych z własnej instalacji HA.
   Testy muszą używać lokalnych fixture/mocks i nie mogą wymagać live HA, jego
   API/WebSocket, istniejącej sesji ani prawdziwych sekretów użytkownika.
3. Zachowaj fail-closed dla brakujących danych SOC, ceny i fizycznego readbacku.
4. Żadna fizyczna ścieżka zapisu Deye nie może omijać centralnego guarda
   Sterowania Deye.
5. Zapis TOU musi zachować diff-only, snapshot, confirmation i rollback tylko
   zmienionych encji.
6. Reverse sync może aktualizować wyłącznie fizyczne pola Harmonogramu; nie może
   nadpisywać trybu, enabled, mocy, prądów ani progów logicznych.
7. `minimum_sell_soc` i `tou_soc` muszą pozostać rozdzielone: pierwsze jest
   logicznym progiem Sprzedaży, drugie fizycznym SOC Deye TOU.
8. Karta nie może zgadywać surowych wartości providera. Backendowe capabilities
   są źródłem prawdy dla edytora TOU.
9. Komponentowa kopia `custom_components/deye_energy_manager/www/` jest źródłem
   runtime. Obie kopie `deye-energy-manager-card.js` muszą pozostać identyczne.
10. `CARD_RESOURCE_REVISION` w `frontend.py` jest centralnym źródłem query URL;
    po zmianie JS zwiększ rewizję dokładnie o jeden i zsynchronizuj nagłówek,
    diagnostykę karty, dokumentację oraz testy.
11. Fizyczna segmentacja 24 h → 6/6 zależy wyłącznie od `tou_soc` i
    `charge_enabled`. Nie dodawaj do niej trybu, mocy, prądów ani
    `minimum_sell_soc`. Per-slot `0 A` oznacza unset/inherit, natomiast świadome
    globalne `0 A` pozostaje prawdziwą wartością tam, gdzie kontrakt na to pozwala.
12. Autodiscovery musi pozostać ograniczone do wybranego urządzenia i potwierdzać
    semantykę encji. Opcjonalne PV3/string/SOH nie może być wypełniane przez luźne
    dopasowanie nazwy, prefiksu ani samego słowa `deye`.
13. FuturePlan jest autorytatywną, datowaną intencją 24 h. Materializacja działa
    JIT tylko dla aktualnego slotu; późniejsza zmiana ręczna wygrywa, a stara
    intencja nie może wykonać catch-up ani powtórzyć się następnego dnia.
14. Cztery jawne mapowania cen są jedynym runtime source-of-truth. Frontend nie
    może zgadywać adaptera, jednostki ani roli ekonomicznej i nie może doliczać
    OSD do kanonicznej ceny backendu. Parser czasu musi zachować lokalne buckety,
    ceny zerowe/ujemne i deterministyczną politykę DST.
15. Zewnętrzny AI pozostaje doradczy: payload nie może zawierać sekretów, odpowiedź
    musi być związana z dokładnym planem, a kandydat ponownie symulowany lokalnie.
    AI nie może wywoływać usług HA/Deye ani omijać ręcznej akceptacji i guardów.
16. Nowy trigger runtime musi wejść do jawnej allowlisty i nie może reagować na
    sensory wyniku. Zachowaj single-flight/coalescing, deduplikację publikacji,
    ograniczoną historię, pracę ciężkich obliczeń poza event loop oraz pełny
    cleanup listenerów i zadań podczas unloadu.
17. Przed Pull Requestem uruchom pełny pytest oraz wszystkie pliki
    `tests/test_*.js` używane przez finalny gate. Repozytorium nie utrzymuje
    jednego osobnego runnera Node, dlatego nie ograniczaj kontroli do ręcznie
    wybranej części testów. Sprawdź również składnię obu kopii karty:

```text
python -m pytest tests -q
node --check custom_components/deye_energy_manager/www/deye-energy-manager-card.js
node --check www/deye-energy-manager-card.js
```

18. Opisz wpływ zmiany na bezpieczeństwo sterowania falownikiem oraz zgodność
    obu kopii karty.
