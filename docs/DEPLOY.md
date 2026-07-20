# Деплой MOVIREVO Content Factory на сервер

Бот — постоянно работающий процесс (Telegram long polling + ежедневный
джоб), поэтому нужен сервер, который работает круглосуточно (VPS и т.п.),
а не serverless/CI. Ниже — деплой через Docker (не зависит от дистрибутива
ОС) + systemd-таймер, который сам подтягивает новые коммиты из git и
пересобирает контейнер.

## 0. Предварительные требования на сервере
- Ubuntu/Debian (команды ниже для них; на другом дистрибутиве — те же шаги
  через свой пакетный менеджер)
- Docker + Docker Compose plugin
- git

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo apt install -y git
```

## 1. Первичное разворачивание

```bash
sudo mkdir -p /opt/movirevo
sudo chown "$USER" /opt/movirevo
git clone -b main https://github.com/GGobya/Content_AI.git /opt/movirevo
cd /opt/movirevo

cp .env.example .env
nano .env   # заполнить все ключи (см. README.md)

mkdir -p photos output
touch state.json   # ОБЯЗАТЕЛЬНО: иначе Docker создаст на этом месте директорию

docker compose up -d --build
docker compose logs -f   # проверить, что бот стартовал без ошибок
```

На этом этапе бот уже работает: слушает Telegram, публикует по кнопкам
одобрения, стартует пайплайн в `DAILY_RUN_TIME`. Фото товара пока нужно
класть в `/opt/movirevo/photos` вручную (или сразу настроить Google Диск —
шаг 2).

## 2. (Опционально) Google Диск как источник фото товара

Идея: диск монтируется в файловую систему сервера через `rclone mount`,
`PHOTOS_DIR` смотрит на точку монтирования — что закинули в папку на Диске,
то через секунды видит бот (без перезапуска: `load_product_photos()`
сканирует папку при каждом запуске пайплайна).

### 2.1 Установка rclone и авторизация
```bash
sudo apt install -y rclone fuse3
sudo sed -i 's/#user_allow_other/user_allow_other/' /etc/fuse.conf   # для --allow-other

rclone config
# n) New remote → name: gdrive → Storage: drive (Google Drive)
# client_id / client_secret — оставить пустыми (использовать значения rclone по умолчанию)
# scope: 1 (полный доступ) или 2 (только файлы, созданные самим rclone)
# root_folder_id — оставить пустым
# service_account — n
# Edit advanced config — n
# Use auto config?
#   - если на сервере есть браузер (десктоп) — y, откроется окно логина
#   - если сервер headless (обычный VPS) — n, rclone даст ссылку вида
#     https://accounts.google.com/... — открой её на СВОЁМ компьютере,
#     войди под тем Google-аккаунтом, где будет папка с фото, разреши доступ,
#     скопируй код, который покажет Google, и вставь его в терминал сервера
```

На Google Диске (в том аккаунте, который авторизовали) создать папку
`MOVIREVO/photos` и положить туда фото товара (`scarf_1.jpg`, `sweater_1.jpg`,
`bomber_1.jpg`, `windbreaker_1.jpg`, ...).

Проверка, что rclone видит файлы:
```bash
rclone lsf gdrive:MOVIREVO/photos
```

### 2.2 Монтирование как systemd-сервис
```bash
sudo cp deploy/rclone-gdrive-photos.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rclone-gdrive-photos
ls /opt/movirevo/photos   # должны появиться файлы с Диска
```

### 2.3 Правильный порядок запуска при перезагрузке сервера
Важно: если Docker-контейнер стартует раньше, чем смонтирован Google Диск,
он "запомнит" пустую папку и не увидит файлы, пока не будет пересоздан.
Чтобы так не было, управляем запуском контейнера через systemd-юнит,
который явно ждёт монтирования Диска:

```bash
sudo cp deploy/movirevo-app.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable movirevo-app
# первый docker compose up -d из шага 1 можно больше не запускать руками —
# дальше им управляет systemd
sudo systemctl restart movirevo-app
```

Если Google Диск не нужен — юнит `movirevo-app.service` всё равно можно
использовать, `rclone-gdrive-photos.service` в нём указан как мягкая
зависимость (`Wants=`), без него он просто не будет ждать.

## 3. Автообновление после изменений в коде

`deploy/autoupdate.sh` раз в 10 минут проверяет `origin/main`, и если там
новые коммиты — подтягивает их и пересобирает контейнер. Дальше сервер
обновляется сам, без ручных действий.

```bash
sudo cp deploy/movirevo-autoupdate.service deploy/movirevo-autoupdate.timer /etc/systemd/system/
sudo chmod +x /opt/movirevo/deploy/autoupdate.sh
sudo systemctl daemon-reload
sudo systemctl enable --now movirevo-autoupdate.timer

# проверить вручную, что скрипт отрабатывает:
sudo systemctl start movirevo-autoupdate.service
journalctl -u movirevo-autoupdate.service -n 50
```

## 4. Полезные команды

```bash
docker compose logs -f          # логи бота
docker compose restart          # перезапуск после ручных правок .env
systemctl status movirevo-autoupdate.timer   # когда сработает автообновление в следующий раз
systemctl status rclone-gdrive-photos        # жив ли монтированный Диск
```
