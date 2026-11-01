# Movie Finder Pro

Telegram-бот на Python для поиска фильмов и сериалов через [PoiskKino API](https://poiskkino.dev/). Интерфейс на русском языке; личные списки и история поиска хранятся отдельно для каждого Telegram-пользователя в SQLite.

## Возможности

- Поиск по названию, фильтрация по рейтингу, году, жанру и бюджету.
- Карточка с полями, которые реально пришли от API: русское и оригинальное название, год, жанры, рейтинг, возрастной рейтинг, страна, длительность, бюджет, описание и режиссёр.
- Избранное, просмотренные и «Хочу посмотреть» с открытием карточек и удалением нажатием на ту же кнопку списка.
- История запросов с повторным поиском.
- Случайный фильм и рекомендации. При наличии истории рекомендации используют наиболее частый жанр в избранном/просмотренном; при отсутствии данных показывается честно обозначенная выборка по рейтингу и числу голосов API.
- Курсорная пагинация поиска и постраничная пагинация поиска по названию.

PoiskKino поддерживает фильтр `budget.value`; сумма передаётся без предположения о валюте, поскольку валюта может различаться в данных. Режим «низкий бюджет» принимает верхний порог от пользователя, «высокий бюджет» — нижний. API не гарантирует заполнение бюджета у каждой записи. Бесплатный demo-тариф ограничивает суточные запросы и пагинацию — учитывайте эти лимиты.

## Установка

Нужен Python 3.10 или новее.

### Windows PowerShell

```powershell
cd MovieFinderPro
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### Linux / macOS

```bash
cd MovieFinderPro
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Отредактируйте `.env`:

```dotenv
TELEGRAM_BOT_TOKEN=токен_от_BotFather
POISKKINO_API_KEY=ключ_из_бота_@poiskkinodev_bot
DATABASE_PATH=movie_finder.sqlite3
LOG_LEVEL=INFO
```

Создайте Telegram-бота через [@BotFather](https://t.me/BotFather) и получите API-ключ PoiskKino через [@poiskkinodev_bot](https://t.me/poiskkinodev_bot). Ключи не добавляйте в исходный код и не отправляйте в Git. `.env` уже внесён в `.gitignore`.

## Запуск

```bash
python main.py
```

При старте создаются таблицы SQLite. Остановить polling можно `Ctrl+C`; соединение с БД закрывается при штатном завершении. Логи пишутся в консоль и `logs/movie_finder.log` с ротацией.

## Тесты

```bash
python -m pytest -q
```

Тесты используют временную SQLite-базу и mock HTTP-сессии, поэтому не требуют Telegram-токена, API-ключа или доступа к внешнему API.

## VPS и systemd

1. Установите Python 3.10+, Git и `python3-venv`.
2. Клонируйте репозиторий в `/opt/movie-finder-pro`.
3. Создайте отдельного системного пользователя, например `moviefinder`, и выдайте ему права на каталог.
4. Установите зависимости в `/opt/movie-finder-pro/.venv`, заполните `.env` с правами `0600`.
5. Скопируйте `deploy/movie-finder-pro.service` в `/etc/systemd/system/`, проверьте пути и пользователя в unit-файле.
6. Выполните `sudo systemctl daemon-reload`, `sudo systemctl enable --now movie-finder-pro`.
7. Проверяйте состояние через `sudo systemctl status movie-finder-pro` и журналы через `sudo journalctl -u movie-finder-pro -f`.

SQLite-файл и каталог логов должны оставаться доступными на запись системному пользователю бота. Для резервного копирования останавливать бота необязательно, но копию БД лучше делать штатными средствами SQLite.

## Структура

```text
main.py                 запуск приложения
config.py               настройки из .env
handlers/bot.py          команды, меню и callback-обработчики
keyboards/               inline-клавиатуры
database/                Peewee-модели и инициализация SQLite
services/movie_api.py    клиент PoiskKino v1.5
services/recommendation.py рекомендации
utils/                   форматирование и логирование
tests/                   тесты БД, API и карточек
deploy/                  пример systemd unit
```

## API

Используются документированные методы `GET /v1.5/movie/search`, `GET /v1.5/movie`, `GET /v1.5/movie/{id}`, `GET /v1.5/movie/random`, `GET /v1.5/dictionary/genres`; авторизация передаётся заголовком `X-API-KEY`. Синтаксис фильтров и формат курсорной пагинации сверяйте с [актуальной документацией PoiskKino](https://api.poiskkino.dev/documentation).
