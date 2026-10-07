# Запуск KORSHI TAP на сервере Google Cloud

Бот работает в режиме long polling: он сам обращается к Telegram за новыми сообщениями.
Поэтому **не нужны** домен, HTTPS-сертификат, вебхук и открытые порты. Нужен только сервер,
на котором бот работает круглосуточно.

Админка на сервере открыта только «внутри» (127.0.0.1) — заходить в неё через SSH-туннель (шаг 7).

---

## 1. Сервисный аккаунт для Vertex AI (ключ-файл не понадобится)

Google Cloud Console → проект **korshi-tap** → **IAM & Admin → Service Accounts → Create service account**
- Имя: `korshi-bot`
- Роль: **Vertex AI User**

Сервер будет работать от этого аккаунта, поэтому `vertex_key.json` на сервер копировать **не нужно**.

## 2. Создать сервер

**Compute Engine → VM instances → Create instance**

| Поле | Значение |
|---|---|
| Name | `korshi-tap` |
| Region / Zone | `europe-west4` (Нидерланды) / любая зона, например `europe-west4-a` — рядом с серверами Telegram |
| Machine type | `e2-small` (2 ГБ памяти). Цена видна справа при создании, порядка $15 в месяц |
| Boot disk | **Ubuntu 24.04 LTS**, 20 ГБ |
| Identity and API access → Service account | `korshi-bot` |
| Access scopes | **Allow full access to all Cloud APIs** |
| Firewall | галочки HTTP/HTTPS **не ставить** |

Нажать **Create**. Затем в списке серверов нажать **SSH** — откроется терминал сервера в браузере.
Все команды ниже выполняются в этом терминале.

## 3. Ключ для скачивания кода с GitHub

Репозиторий приватный, поэтому серверу нужен свой ключ только для чтения:

```bash
sudo ssh-keygen -t ed25519 -f /root/.ssh/korshi_deploy -N ""
sudo cat /root/.ssh/korshi_deploy.pub
```

Скопировать выведенную строку → GitHub → репозиторий **korshitap → Settings → Deploy keys → Add deploy key**
(название `gcp-server`, галочку «Allow write access» **не ставить**).

## 4. Скачать код

```bash
sudo GIT_SSH_COMMAND="ssh -i /root/.ssh/korshi_deploy -o StrictHostKeyChecking=accept-new" \
  git clone --branch main git@github.com:armansapiolda/korshitap.git /opt/korshitap
```

> Пока изменения не слиты в `main`, вместо `main` укажи ветку `claude/trusting-ritchie-t2d6u5`.

## 5. Установка

```bash
sudo bash /opt/korshitap/deploy/setup.sh
```

Скрипт ставит Python-зависимости, создаёт системного пользователя `korshi`, автозапуск бота
и ежедневную резервную копию базы. В конце он попросит заполнить `.env`.

## 6. Настройки и запуск

```bash
sudo nano /opt/korshitap/.env
```

Заполнить:

```env
TELEGRAM_BOT_TOKEN=токен_от_BotFather
AI_PROVIDER=vertex
USE_VERTEX_AI=true
GOOGLE_CLOUD_PROJECT=korshi-tap
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=
ADMIN_PASSWORD=придумай_надёжный_пароль
```

Сохранить (Ctrl+O, Enter, Ctrl+X) и запустить:

```bash
sudo systemctl start korshi-tap
sudo journalctl -u korshi-tap -f      # логи; выход — Ctrl+C
```

В логах должно появиться `Starting Telegram Bot long-polling`. Напиши боту `/start` — он ответит.

> ⚠️ Один токен — один запущенный бот. Если бот запущен ещё и на твоём компьютере,
> выключи его там, иначе они будут мешать друг другу (ошибка `Conflict: terminated by other getUpdates request`).

## 7. Как зайти в админку

**Вариант А — через Cloud Shell (ничего не нужно устанавливать).**
В Google Cloud Console нажать значок **Cloud Shell** (`>_` вверху справа) и выполнить:

```bash
gcloud compute ssh korshi-tap --zone=europe-west4-a -- -N -L 8080:127.0.0.1:8000
```

Затем в Cloud Shell нажать **Web Preview → Preview on port 8080** и дописать в адресе `/admin`.
Логин `admin`, пароль — `ADMIN_PASSWORD` из `.env`.

**Вариант Б — со своего компьютера** (если установлен [gcloud CLI](https://cloud.google.com/sdk/docs/install)):

```bash
gcloud compute ssh korshi-tap --zone=europe-west4-a -- -N -L 8000:127.0.0.1:8000
```

и открыть в браузере http://localhost:8000/admin

Тестовые анкеты (сиды) добавляются и удаляются на странице **/admin/seed**.

## 8. Обновить код на сервере

```bash
sudo bash /opt/korshitap/deploy/update.sh
```

Скрипт делает резервную копию базы, скачивает новый код, ставит зависимости и перезапускает бота.
Схема базы обновляется сама при запуске.

## Полезные команды

```bash
sudo systemctl status korshi-tap      # работает ли бот
sudo systemctl restart korshi-tap     # перезапустить
sudo systemctl stop korshi-tap        # остановить
sudo journalctl -u korshi-tap -n 200  # последние 200 строк логов
ls /var/backups/korshitap/            # резервные копии базы (хранятся последние 14)
```

## Резервные копии

- Каждый день в 03:30 (по времени сервера, UTC) база копируется в `/var/backups/korshitap/`.
- Дополнительно советую в Console включить **снимки диска**: Compute Engine → Snapshots →
  **Create snapshot schedule** (ежедневно) и привязать его к диску сервера — так копия хранится вне сервера.
- Когда пользователей станет много, лучше перейти на Postgres (Cloud SQL): в `.env` поменять
  `DATABASE_URL=postgresql+asyncpg://...`, схема создастся сама.
