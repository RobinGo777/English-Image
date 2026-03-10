# 🇬🇧 English A2 Telegram Bot

Автоматична публікація 8 навчальних карток щодня в Telegram.

## Розклад
| Час (Київ) | Рубрика |
|---|---|
| 09:00 | 💬 Daily Phrase |
| 10:00 | 📦 Word Pack |
| 11:00 | 💡 Fun Fact |
| 12:00 | 📖 Quote |
| 13:00 | ✈️ Situation Phrases |
| 14:00 | 💬 Chat Expressions |
| 15:00 | ⚔️ Synonyms Battle |
| 16:00 | 🚀 Motivation |

## Налаштування

### 1. API ключі які потрібні:
- `TELEGRAM_BOT_TOKEN` — від @BotFather
- `TELEGRAM_CHAT_ID` — ID чату або каналу
- `GEMINI_API_KEY` — від aistudio.google.com
- `GROQ_API_KEY` — від console.groq.com
- `REDIS_URL` — від cloud.redis.io

### 2. Як отримати TELEGRAM_CHAT_ID:
1. Напишіть боту будь-яке повідомлення
2. Відкрийте: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Знайдіть `"chat":{"id": ...}` — це і є ваш ID
4. Для Saved Messages — використовуйте ваш особистий ID

### 3. Деплой на Render.com:
1. Завантажте код на GitHub
2. Створіть новий **Web Service** на render.com
3. Підключіть репозиторій
4. Додайте всі ENV змінні
5. Deploy!

### 4. Keep-alive:
Render автоматично пінгує сервіс через вбудований HTTP сервер на порту 10000.

## Структура моделей (fallback)
```
gemini-2.5-flash → gemini-2.0-flash → gemini-2.0-flash-lite → gemini-2.5-pro → Groq llama-3.3-70b
```

## Локальний запуск для тесту
```bash
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium

export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
export GEMINI_API_KEY=...
export GROQ_API_KEY=...
export REDIS_URL=redis://localhost:6379

python main.py
```
