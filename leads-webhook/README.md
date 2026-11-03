# Вебхук заявок

FastAPI принимает заявку с формы, проверяет поля, дописывает строку в Excel, по желанию — в Google Sheets, оценивает категорию и шлёт текст менеджеру в Telegram.

```bash
cd leads-webhook
uvicorn leads_webhook.main:app --reload --port 8000
```

- `GET /health` — `{"status":"ok"}`
- `POST /leads` — JSON заявки

```json
{
  "name": "Анна",
  "phone": "+7 999 123-45-67",
  "email": "",
  "message": "Сколько стоит связать заявки с Google Таблицей?",
  "source": "site"
}
```

Нужны имя (от 2 символов), сообщение (от 5) и хотя бы один контакт. Телефон — 10–15 цифр, лишние пробелы и скобки допустимы. Пустые `phone` и `email` можно не присылать. `source` по умолчанию `website`.

Если задан `WEBHOOK_SECRET`, запрос должен содержать заголовок `X-Webhook-Secret`.

## Куда пишется заявка

`data/leads.xlsx`, лист «Заявки»: ID, дата UTC, имя, телефон, email, сообщение, источник, категория, приоритет, краткое содержание, кто классифицировал (`rules` или `llm`). Шапка закреплена, ширины колонок выставлены.

Ответ `stored` содержит `excel` и, когда таблица Google ответила успешно, `google_sheets`. Сбой Sheets или Telegram не отменяет уже записанную строку Excel: в ответе будет `notified: "failed"`, а причина останется в логе.

## Классификация

Сначала вызывается модель, если заданы `OPENAI_API_BASE` и `OPENAI_MODEL`. Запрос совместим с OpenAI Chat Completions, поэтому подходят OpenRouter, Groq и Ollama (`http://127.0.0.1:11434/v1`). В модель уходят имя, источник и текст. Телефон и email не отправляются.

Если адреса нет, модель ответила ошибкой или вернула не тот JSON, срабатывают правила:

| Категория | Слова в тексте | Приоритет |
| --- | --- | --- |
| `support` | не работает, ошибка, баг, сломал, почин, support | high |
| `pricing` | цена, стоимость, прайс, сколько стоит, бюджет, price | normal |
| `partnership` | партнёр, сотрудничество, partnership | normal |
| `new_order` | заказ, купить, оформить, order | normal |
| `other` | ничего из списка | low |

Слова «срочно», «urgent», «asap», «немедленно» поднимают приоритет до high, категория при этом остаётся своей.

## Переменные

Смотрите также [`.env.example`](../.env.example).

| Переменная | Зачем |
| --- | --- |
| `LEADS_XLSX_PATH` | Файл Excel. По умолчанию `leads-webhook/data/leads.xlsx` |
| `WEBHOOK_SECRET` | Общий секрет входящего вебхука |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Уведомление менеджеру |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | JSON-ключ сервисного аккаунта |
| `GOOGLE_SHEET_ID` | Id таблицы из URL |
| `GOOGLE_SHEET_WORKSHEET` | Лист, по умолчанию `Leads` |
| `OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENAI_MODEL` | Необязательная LLM-классификация |

Таблицу нужно открыть сервисному аккаунту на редактирование. Если листа ещё нет, скрипт создаст его и подпишет шапку.

## Docker

Сборка из корня репозитория, потому что зависимости лежат в общем `requirements.txt`:

```bash
docker build -f leads-webhook/Dockerfile -t leads-webhook .
docker run --rm -p 8000:8000 --env-file .env \
  -v "$PWD/leads-webhook/data:/app/leads-webhook/data" \
  leads-webhook
```

Образ на Python 3.11. Контейнер слушает порт 8000 и проверяет `GET /health`.

## n8n

Файл [`n8n/leads-workflow.json`](../n8n/leads-workflow.json) импортируется в n8n через меню Workflows → Import from File.

Рабочая ветка: Webhook `POST /webhook/website-lead` отправляет тело формы в `http://127.0.0.1:8000/leads` и возвращает ответ API. Узлы Telegram и Google Sheets в файле выключены: это запасной путь, если вебхук на Python не нужен. Чтобы им пользоваться, выключите узел «Leads webhook», включите Telegram и Google Sheets и подставьте учётные данные уже в интерфейсе n8n. Секреты в JSON не зашиты.

Тело, которое ждёт вебхук n8n: `name`, `phone`, `email`, `message`, `source`.

## Тесты

Из корня: `pytest leads-webhook/tests`. Проверяются валидация, правила, ответ модели и запасной путь при обрыве LLM, запись Excel и секрет вебхука. Внешние API не вызываются.
