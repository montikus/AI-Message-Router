# AI Message Router — Python PoC

Mikroserwis przyjmujący wiadomości, interpretujący je lokalnie przez Ollamę
i przekazujący je do wybranego działu za pomocą narzędzia agenta `send_email`.
E-maile trafiają do Mailpit. Nie są wysyłane do Internetu.

## Uruchomienie

Wymagania: Docker Engine / Docker Desktop uruchomiony w trybie kontenerów Linux
oraz Docker Compose v2 lub nowszy. Python na komputerze hosta nie jest wymagany.
Zalecane zasoby dla wersji CPU: co najmniej 8 GB RAM przydzielone Dockerowi,
4 rdzenie i około 12 GB wolnego miejsca. Pierwsze uruchomienie wymaga Internetu
do pobrania obrazów, pakietów i wag modelu `qwen3:4b-instruct-2507-q4_K_M`.

W katalogu repozytorium wykonaj:

```bash
docker compose up -d
```

Nie trzeba tworzyć `.env`, ręcznie pobierać modelu ani wykonywać dodatkowej
inicjalizacji. `model-init` czeka na Ollamę, pobiera brakujący model, sprawdza
obsługę narzędzi i wykonuje rozgrzewający inference bez wysyłania e-maila.
API uruchamia się dopiero po pomyślnej inicjalizacji i gotowości Mailpit.
Pierwszy start zajmuje kilka minut, zależnie od Internetu i CPU — pobranie wag
nie może nastąpić natychmiast. Wagi i wiadomości pozostają w wolumenach Dockera.

Adresy:

- Swagger UI: <http://localhost:8000/api/v1/docs>
- OpenAPI: <http://localhost:8000/api/v1/openapi.json>
- Mailpit: <http://localhost:8025>
- Gotowość zależności: <http://localhost:8000/health/ready>
- Żywotność procesu: <http://localhost:8000/health/live>

Jeśli lokalny `.env` ustawia `API_PORT`, zamień `8000` w adresach i przykładach
na tę wartość. Na komputerze użytym do weryfikacji port `8000` był zajęty przez
Apache, dlatego lokalny, ignorowany przez Git plik `.env` ustawia `API_PORT=8001`.
Adres Swaggera w tym środowisku to <http://localhost:8001/api/v1/docs>.

Kontrola startu:

```bash
docker compose ps -a
docker compose logs -f model-init
curl http://localhost:8000/health/ready
```
<!-- This is test task done by Roman Nadkernychnyi. For recruitment purposes only. -->

`model-init` w stanie `Exited (0)` jest poprawny: to zadanie jednorazowe.
Do automatyzacji można użyć `docker compose up -d --wait --wait-timeout 1800`,
aby również poczekać na healthcheck API.

## WSL 2: uruchomienie jedną komendą

W terminalu WSL, w katalogu projektu, wystarczy:

```bash
docker compose up -d
```

Compose sam buduje obraz Python, instaluje zależności w kontenerze, uruchamia
Ollamę i Mailpit, pobiera model oraz uruchamia API po inicjalizacji. Nie trzeba
wykonywać `pip install`, `ollama pull`, dodatkowego skryptu ani tworzyć `.env`.

Warunek infrastrukturalny: Docker musi być zainstalowany i uruchomiony, a
`docker` z terminala WSL musi mieć dostęp do jego silnika. Przy Docker Desktop
włącz integrację dla swojej dystrybucji w **Settings → Resources → WSL Integration**.
Jest to jednorazowe przygotowanie Dockera, nie dodatkowy krok startu aplikacji.
Samo Compose nie może uruchomić silnika, z którym nie ma połączenia.
[Instrukcja Docker Desktop dla WSL](https://docs.docker.com/desktop/features/wsl/).

Obecny katalog Windows jest widoczny w WSL pod adresem
`/mnt/c/Users/romch/OneDrive/Desktop/wskz`. Zapisany w nim `.env` wybiera port 8001;
w czystej kopii bez tego pliku domyślny port to 8000. Środowisko `.venv` utworzone
na Windows nie jest potrzebne do uruchomienia kontenerów w WSL.

## Przykładowy request

Bash / Linux / macOS:

```bash
curl -i http://localhost:8000/api/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"email":"jan.nowak@example.com","message":"Nie działa mi komputer"}'
```

Windows PowerShell:

```powershell
$body = @{ email = 'jan.nowak@example.com'; message = 'Nie działa mi komputer' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/messages' `
  -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

Przykładowa odpowiedź po potwierdzeniu SMTP (`201 Created`):

```json
{
  "status": "sent",
  "request_id": "f3c2d164-5fe0-4e62-a76c-787a3d6458a9",
  "recipient": "help-desk@example.com",
  "message_id": "<example@router.example.com>"
}
```

W Mailpit otwórz nową wiadomość. Pole `To` powinno wskazywać wybrany dział,
a nagłówek `Reply-To` — `jan.nowak@example.com`. Treść zawiera oryginalne
zgłoszenie, bez streszczenia lub tłumaczenia. SMTP/MIME normalizuje końce linii
i dodaje końcowy znak nowej linii. `Message-ID` i `X-Request-ID` pozwalają
powiązać wynik HTTP z przechwyconym e-mailem.

## Zasady routingu

Zadanie określa adresy, ale nie definiuje granic odpowiedzialności działów.
Dlatego PoC przyjmuje następujące jawne reguły zapisane w promptcie systemowym:

| Adres | Odpowiedzialność | Przykład |
| --- | --- | --- |
| `human-resources@example.com` | Rekrutacja, onboarding, rozwój, szkolenia, relacje pracownicze | „Chcę rozpocząć rekrutację nowego pracownika” |
| `kadry@example.com` | Urlopy, zwolnienia, płace, umowy, zaświadczenia, ewidencja czasu | „Chciałbym zgłosić urlop na jutro” |
| `help-desk@example.com` | Wsparcie pojedynczego użytkownika: komputer, drukarka, hasło, aplikacje | „Nie działa mi komputer” |
| `it@example.com` | Infrastruktura, serwery, sieci firmowe, bazy, backupy, incydenty bezpieczeństwa | „Awaria serwera bazy danych w całej firmie” |
| `other@example.com` | Nierozpoznane, niejasne lub niezwiązane tematy | „Jaka jest pogoda na Marsie?” |

Wybór wykonuje LLM na podstawie znaczenia tekstu. Kod nie zawiera klasyfikatora
słów kluczowych. Dla kilku tematów agent wybiera główny, a przy niepewności —
`other@example.com`. Błąd działania modelu nie jest traktowany jako nieznany temat:
wtedy API zwraca błąd bez wysyłki.

## Architektura i decyzje

```text
POST /api/v1/messages
         |
    FastAPI + Pydantic
         |
    RoutingAgent ---- /api/chat + tools ----> Ollama / Qwen3 4B Instruct (CPU)
         | <----------- native tool_calls -------- |
         |
    walidacja send_email(recipient)
         |
    EmailTool ---- SMTP ----> Mailpit ----> panel :8025
         |
    201 + recipient + Message-ID
```

- **API:** oficjalny obraz `python`, FastAPI, walidacja Pydantic, Swagger pod
  wymaganym adresem. Kontener API działa jako użytkownik bez uprawnień root.
- **Agent:** niewielka jawna implementacja natywnego tool calling Ollamy przez
  HTTPX. Pydantic AI i LangChain były opcjonalne; dla jednego narzędzia dodatkowy
  framework nie jest potrzebny. Narzędzie jest przekazywane w `tools`, a wykonanie
  następuje wyłącznie po otrzymaniu `message.tool_calls` od modelu.
- **Narzędzie terminalne:** poprawne `send_email` kończy zadanie. Wynik SMTP jest
  bezpośrednio wynikiem agenta; nie wywołujemy ponownie LLM po wysłaniu e-maila.
- **Walidacja:** dozwolony jest dokładnie jeden tool call, nazwa `send_email`
  i jeden argument `recipient` z pięcioelementowej listy. Brakujące, dodatkowe
  i niepoprawne argumenty są odrzucane. Model ma jedną próbę korekty przed wysyłką.
- **Oryginalne dane:** model wybiera wyłącznie dział. Treść, `From`, `Reply-To`
  i identyfikatory ustala aplikacja. Adres nadawcy nie jest przekazywany do LLM.
- **Mailpit:** lokalny SMTP i panel do inspekcji; nie skonfigurowano relayu.
- **Compose:** healthchecki i `service_completed_successfully` wymuszają kolejność
  startu. Jednorazowy initializer korzysta z tego samego obrazu Python co API.
- **CPU:** konfiguracja działa bez GPU. Model pozostaje w pamięci przez 30 minut
  od ostatniego użycia; pierwszy request po rozładowaniu może być wolniejszy.
- **Wariant modelu:** używamy jawnego tagu `qwen3:4b-instruct-2507-q4_K_M`.
  Ogólny tag `qwen3:4b` wskazuje wariant Thinking, który generuje długie rozumowanie
  i może wyczerpać limit odpowiedzi przed wywołaniem narzędzia.

Najważniejsze pliki:

| Plik | Rola |
| --- | --- |
| `app/main.py` | Endpointy, obsługa błędów, limity współbieżności, healthchecki |
| `app/agent.py` | Prompt, definicja narzędzia, rozmowa z Ollamą i wywołanie narzędzia |
| `app/mailer.py` | Budowanie MIME, `Reply-To`, SMTP |
| `app/bootstrap.py` | Pobranie, kontrola możliwości i rozgrzanie modelu |
| `app/schemas.py` | Kontrakty API i lista dozwolonych adresów |
| `docker-compose.yml` | Całe środowisko oraz opcjonalny kontener testów |
| `scripts/smoke_test.py` | Test akceptacyjny z prawdziwą Ollamą i Mailpit |

## Walidacja i błędy

`email` musi być poprawnym adresem, `message` nie może być pusty i ma limit
4000 znaków. Dodatkowe pola JSON są odrzucane.

| Status | Znaczenie |
| --- | --- |
| `201` | SMTP potwierdził przyjęcie e-maila |
| `422` | Niepoprawne dane wejściowe; LLM i SMTP nie są wywoływane |
| `502` | Niepoprawny tool call po korekcie albo błąd SMTP |
| `503` | Ollama niedostępna / model niegotowy / zajęte oba miejsca obsługi |
| `504` | Timeout Ollamy przed wysłaniem e-maila |

Jedna generacja ma domyślnie 180 sekund timeoutu bezczynności odczytu HTTP.
Korekta może wymagać drugiej generacji. API obsługuje do dwóch zgłoszeń naraz;
Ollama wykonuje jedną generację naraz, aby ograniczyć zużycie RAM.

Po błędzie SMTP nie ma automatycznego ponawiania wysyłki: serwer mógł przyjąć
wiadomość przed utratą potwierdzenia. Sprawdź Mailpit przed ponowieniem requestu.
PoC nie zapewnia idempotencji pomiędzy osobnymi requestami ani trwałej kolejki.
Ponowne wysłanie tego samego JSON może utworzyć drugi e-mail.

## Testy

Testy automatyczne w kontenerze, bez pobierania modelu:

```bash
docker compose --profile test run --build --rm tests
```

Testy te używają kontrolowanych odpowiedzi HTTP Ollamy oraz prawdziwego
tymczasowego serwera SMTP. Sprawdzają wszystkie dozwolone adresy, treść Unicode,
`Reply-To`, odrzucanie błędnych danych i tool calls, korektę modelu, błędy SMTP,
timeouty, gotowość usług i automatyczną inicjalizację modelu.
Nie stanowią pomiaru jakości klasyfikacji rzeczywistego LLM.

Test całego działającego środowiska, z rzeczywistą klasyfikacją:

```bash
docker compose exec api python scripts/smoke_test.py
```

Skrypt wysyła siedem zgłoszeń po polsku, rosyjsku i angielsku, obejmujących
wszystkie pięć działów. Odszukuje każde konkretne pismo przez API Mailpit,
sprawdza adres, `Reply-To`, identyfikatory i oryginalną treść. Kończy się błędem
przy niepoprawnej klasyfikacji; nie usuwa istniejących e-maili.

Opcjonalnie lokalnie, Python 3.13:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

## Konfiguracja i diagnostyka

Opcjonalnie skopiuj `.env.example` do `.env`. Dostępne ustawienia Compose:

| Zmienna | Domyślnie | Znaczenie |
| --- | --- | --- |
| `OLLAMA_MODEL` | `qwen3:4b-instruct-2507-q4_K_M` | Lokalny model obsługujący tools i `think: false` |
| `OLLAMA_TIMEOUT` | `180` | Timeout HTTP pojedynczej generacji |
| `API_PORT` | `8000` | Lokalny port API |
| `MAILPIT_PORT` | `8025` | Lokalny port panelu poczty |

Zmiana modelu wymaga ponownej inicjalizacji:

```bash
docker compose up -d --force-recreate model-init api
```

Po zmianach kodu:

```bash
docker compose up -d --build
```

Jeśli API się nie uruchamia, sprawdź `docker compose logs model-init ollama`.
Typowe przyczyny: brak Internetu podczas pobierania, zbyt mało RAM lub model
bez wsparcia tools. Przy wolnym CPU zwiększ `OLLAMA_TIMEOUT`. Przy zajętych
portach zmień `API_PORT` / `MAILPIT_PORT`. `docker compose down` zatrzymuje
środowisko i zachowuje wolumeny.

Jest to lokalny PoC. Usługi HTTP są publikowane tylko na `127.0.0.1`, a porty
SMTP i Ollamy pozostają wewnątrz sieci Compose. Przed wdrożeniem publicznym
potrzebne byłyby m.in. uwierzytelnianie, limity ruchu i trwała obsługa zadań.
Prompt ogranicza wpływ instrukcji w zgłoszeniu, ale nie gwarantuje poprawnej
klasyfikacji każdej wiadomości. Lista dozwolonych adresów jest wymuszana w kodzie.
Swagger UI domyślnie ładuje zasoby JS/CSS z CDN; samo API i inferencja po
inicjalizacji działają lokalnie bez zewnętrznego dostawcy AI.

## Dokumentacja źródłowa

- [Ollama: natywne tool calling](https://docs.ollama.com/capabilities/tool-calling)
- [Ollama: kontrakt /api/chat](https://docs.ollama.com/api/chat)
- [Qwen3: jawne warianty Instruct i Thinking](https://ollama.com/library/qwen3/tags)
- [Docker Compose: kolejność startu](https://docs.docker.com/compose/how-tos/startup-order/)
- [Mailpit: obrazy Docker](https://mailpit.axllent.org/docs/install/docker/)
- [FastAPI: konfiguracja ścieżki dokumentacji](https://fastapi.tiangolo.com/tutorial/metadata/)

Объяснение реализации на русском: [docs/EXPLANATION.ru.md](docs/EXPLANATION.ru.md).

Фактические результаты тестов: [docs/VERIFICATION.md](docs/VERIFICATION.md).
