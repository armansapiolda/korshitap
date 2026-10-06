# KORSHI TAP — Руководство для Claude (Architecture & Handover)

Сервис поиска соседей и совместной аренды жилья в Казахстане (Алматы, Астана, Шымкент) через Telegram-бота с панелью администратора и ИИ-ранжированием на базе Google Cloud Vertex AI (Gemini 2.5 Flash).

---

## 🛠 Стек технологий
- **Язык**: Python 3.9+
- **Telegram Bot Framework**: aiogram 3.x (Async, FSM, Router)
- **База данных**: SQLite + aiosqlite, SQLAlchemy 2.0 (Async ORM)
- **ИИ-провайдер**: Google GenAI SDK (`google-genai`), модель `gemini-2.5-flash` через Google Cloud Vertex AI (проект `korshi-tap`, локация `us-central1`, ключ `vertex_key.json`). Резерв: `MockAIProvider`.
- **Веб-панель / Admin**: FastAPI + Jinja2 + Tailwind CSS (`http://127.0.0.1:8000/admin`)
- **Тесты**: Pytest + pytest-asyncio (20 автоматических тестов)

---

## 🏗 Архитектура проекта

```
KORSHI TAP/
├── app/
│   ├── ai/
│   │   ├── base.py                 # Pydantic-модели: AIRankingResult, RankedCandidateItem, etc.
│   │   ├── factory.py              # Фабрика провайдеров (get_ai_provider)
│   │   ├── gemini_provider.py      # Реализация Vertex AI (Gemini 2.5 Flash, асинхронный клиент, thinking_budget=0)
│   │   └── mock_provider.py        # Детерминированный офлайн-ранжировщик (fallback)
│   ├── admin/                      # FastAPI админ-панель (статистика, модерация, сиды)
│   ├── bot/
│   │   ├── bot.py                  # Инициализация бота, диспетчера и роутеров
│   │   ├── handlers/
│   │   │   ├── start.py            # Анкета /start (ветвление: есть квартира / ищу квартиру)
│   │   │   ├── recommendations.py  # 2-этапный поиск: Холодный фильтр + AI-ранжирование
│   │   │   ├── district_search.py  # Просмотр кандидатов по районам (без ИИ-блоков)
│   │   │   └── profile.py          # Просмотр и редактирование профиля
│   │   ├── keyboards/              # Клавиатуры (Reply & Inline)
│   │   └── states/                 # FSM-состояния анкеты
│   ├── db/
│   │   ├── base.py                 # Async engine, sessionmaker, миграции init_db()
│   │   └── models.py               # Модели: User, SeekerProfile, Listing, Like, Match
│   ├── matching/
│   │   ├── cold_search.py          # ЭТАП 1: Холодный фактологический поиск
│   │   └── reason_generator.py     # Вспомогательные генераторы текста
│   ├── seeds/
│   │   └── test_data.py            # Генератор 500 реалистичных пользователей (KZ/RU)
│   ├── services/                   # Сервисы: UserService, ListingService, MatchService
│   ├── config.py                   # Pydantic Settings
│   └── constants.py                # Районы Алматы, Астаны, Шымкента, смежные районы
├── tests/                          # 20 тестов (test_ai_ranking.py, test_matching_engine.py и др.)
├── run_bot.py                      # Запуск Telegram-бота
├── run_admin.py                    # Запуск веб-админки
├── CLAUDE.md                       # Этот файл документации
├── .env.example                    # Пример переменных окружения
└── .gitignore                      # Защита приватных ключей и баз данных
```

---

## ⚡ Ключевые бизнес-правила и логика (КРИТИЧЕСКИ ВАЖНО)

1. **Приоритет казахского языка**:
   - При `/start` первый вопрос строго на казахском: `Қай тілде сөйлесеміз? / На каком языке будем общаться?` (`🇰🇿 Қазақша` первая, `🇷🇺 Русский` вторая).
   - Приветствие на казахском начинается с `Сәлем! 👋`.
   - Обращение к пользователю строго на **«ты» / «сен»** (тёплый, дружелюбный тон, без скобок вида `ищет(ла)`).

2. **Двухэтапный AI-поиск соседей ([`app/matching/cold_search.py`](file:///app/matching/cold_search.py) & [`app/ai/gemini_provider.py`](file:///app/ai/gemini_provider.py))**:
   - **Этап 1 (Холодный поиск)**: Строго фактологическая фильтрация по БД (город, район, взаимный пол, бюджет, дата).
     - Если человек ищет квартиру: в первую очередь показывать людей, у кого **уже есть квартира** в этом районе с хотя бы 1 свободным местом.
     - **ВАЖНО**: количество искомых людей (`neighbors_needed`) **НЕ ДОЛЖНО** отсекать соискателей.
     - Если таких людей мало — дополнять ко-сикерами (теми, кто тоже ищет в районе).
     - Если у пользователя есть квартира — показывать только соискателей без квартиры.
   - **Этап 2 (AI-ранжирование через Gemini 2.5 Flash)**:
     - Сравнивает отобранных людей и ранжирует от наиболее подходящего к менее подходящему.
     - Генерирует **супер-короткое (1 предложение, до 15–18 слов) приземлённое объяснение строго по факту** (район, бюджет, сроки заезда, нюанс/быт).
     - **Категорически запрещены** рекламные клише («отличный вариант», «хороший кандидат»), проценты, веса и формулы.

3. **Скорость и асинхронность ИИ**:
   - Вызовы Gemini делаются через `client.aio.models.generate_content(...)`.
   - В конфиг всегда передаётся `thinking_config=types.ThinkingConfig(thinking_budget=0)` — это исключает 40-секундную задержку рассуждений Gemini 2.5 Flash и ускоряет ответ до **1.5–2 секунд**.
   - Установлен таймаут `asyncio.wait_for(..., timeout=7.0)` с автоматическим переходом на `mock_fallback`.

4. **Поиск по районам ([`app/bot/handlers/district_search.py`](file:///app/bot/handlers/district_search.py))**:
   - Работает напрямую из БД.
   - Передаётся `show_reason=False` — блок ИИ-совместимости (`💡 Неге сәйкес келеді:`) там намеренно **не выводится**.

---

## 🚀 Команды для работы

```bash
# Запуск тестов (все 20 тестов должны проходить)
.venv/bin/pytest -v

# Запуск Telegram-бота
.venv/bin/python run_bot.py

# Запуск панели администратора
.venv/bin/python run_admin.py

# Засеять 500 реалистичных пользователей (Алматы, Астана, Шымкент)
.venv/bin/python -m app.seeds.test_data --count 500

# Очистить тестовые данные
.venv/bin/python -m app.seeds.test_data --wipe
```

---

## 🔒 Безопасность
- Файл `vertex_key.json` (Google Cloud Service Account) и `korshi_tap.db` защищены в `.gitignore` и **никогда не должны попадать в публичные репозитории**.
