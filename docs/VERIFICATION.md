<!-- This is test task done by Roman Nadkernychnyi. For recruitment purposes only. -->
# Отчёт о проверке — 9 ноября 2026

Проверка выполнена на Windows с Docker Desktop (Linux containers / WSL2).
Docker Engine 29.3.1, Compose 5.1.0. Ollama 0.40.15,
модель `qwen3:4b-instruct-2507-q4_K_M`, Mailpit 1.27.4.
API использует официальный образ `python:3.13-slim-bookworm`.

## Автоматические проверки

- `docker compose config --quiet` — конфигурация корректна.
- `ruff check .` — ошибок нет.
- `ruff format --check .` — форматирование корректно.
- `pip check` в локальном виртуальном окружении — конфликтов зависимостей нет.
- `docker compose --profile test run --build --rm tests` — **37 тестов прошли**.

Тесты проверяют пять разрешённых получателей, реальную SMTP-передачу,
`Reply-To`, исходную Unicode-строку, идентификаторы, входную валидацию,
ошибочные и множественные tool calls, корректировку ответа, ошибки сети,
тайм-ауты, SMTP-отказ, ограничение параллелизма, OpenAPI и readiness.
Также проверяются скачивание отсутствующей модели, повторное использование
весов, неполная загрузка и отказ инициализации при отсутствии tool calling.

У тестового TestClient есть одно предупреждение Starlette о будущей замене
HTTPX на HTTPX2; тесты завершаются успешно. Ответы Ollamy в этих 37 тестах
контролируемые. Реальная модель проверена отдельно ниже.

## Сквозной тест с реальной LLM

Команда: `docker compose exec api python scripts/smoke_test.py`.

| Сообщение | Получатель | Время, с | Результат |
| --- | --- | ---: | --- |
| Nie działa mi komputer | help-desk@example.com | 2,97 | PASS |
| Chciałbym zgłosić urlop na jutro | kadry@example.com | 2,50 | PASS |
| Chcę rozpocząć rekrutację nowego pracownika do zespołu | human-resources@example.com | 2,56 | PASS |
| Awaria serwera bazy danych, wszystkie działy firmy utraciły dostęp | it@example.com | 2,71 | PASS |
| Jaka jest pogoda na Marsie? | other@example.com | 2,38 | PASS |
| Нужна справка о зарплате за прошлый месяц | kadry@example.com | 2,61 | PASS |
| I forgot my laptop password and cannot log in | help-desk@example.com | 2,54 | PASS |

Итог: **7/7**. Для каждого запроса проверены HTTP 201, правильная
классификация, ровно одно письмо с соответствующим идентификатором,
получатель в заголовке `To`, `Reply-To: acceptance.test@example.com`,
`Message-ID`, `X-Request-ID` и исходный текст.

Проверка использует реальную Ollama, вызов инструмента, SMTP и чтение
исходного MIME через API Mailpit. Письма оставлены в Mailpit для просмотра.
Времена относятся к прогретой модели на данном компьютере и не являются SLA.
Эта выборка подтверждает сценарии PoC, но не доказывает точность на любых текстах.

## Запуск и доступность

Инициализатор автоматически скачал отсутствующие веса Instruct-модели,
проверил инструмент и завершился с кодом 0. API был запущен после него.
В финальной конфигурации выбран точный тег Instruct: общий `qwen3:4b`
соответствует Thinking и не подходит для установленного короткого лимита
генерации. Это было выявлено и исправлено сквозным тестом.

Проверены с Windows-хоста:

- `http://localhost:8001/health/ready` — HTTP 200, `status: ready`.
- `http://localhost:8001/api/v1/docs` — HTTP 200.
- `http://localhost:8025` — HTTP 200.

Порт 8000 занят существующим Apache. Для данного рабочего каталога создан
локальный `.env` с `API_PORT=8001`. Этот файл исключён из Git; стандартный
порт чистой копии проекта — 8000. Существующий Apache не изменялся.

## Соответствие DoD

| Требование | Реализация и проверка |
| --- | --- |
| Запуск через Docker Compose | API, Ollama и Mailpit запущены; загрузка весов автоматическая |
| Python API на официальном образе | Dockerfile начинается с `python:3.13-slim-bookworm` |
| Swagger `/api/v1/docs` | Endpoint отвечает HTTP 200 |
| README с инструкциями и примером | README.md на польском, cURL и PowerShell |
| Анализ и письмо после HTTP-запроса | Семь реальных запросов, семь проверенных писем |
| Tool/function calling | Нативный `message.tool_calls` → проверка → `EmailTool.send_email` |
| Адрес из разрешённого списка | Enum из пяти адресов; все пять проверены на реальной модели |
| Правильный Reply-To | Проверен в исходном MIME всех семи писем |
