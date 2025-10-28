import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import os
import time
import datetime
import logging
from telebot import apihelper 
from flask import Flask
import threading

# === НАСТРОЙКИ ЛОГИРОВАНИЯ ===
# Настраиваем логирование, чтобы видеть, что происходит в консоли
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === КОНФИГУРАЦИЯ БОТА ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.error("❌ BOT_TOKEN не найден. Установите его в переменные окружения!")
    # Выходим, если токен не найден
    # exit(1) 

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

# === ОСНОВНЫЕ ССЫЛКИ И ID ===
CHANNEL_USERNAME = "@whoisolis"
# ВАШИ АКТУАЛЬНЫЕ ID
CHANNEL_ID = -1003083438241 
DISCUSSION_GROUP_ID = -1003210182852 

GIF_URL = "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3bThjMXZkMTExb2IzZW9zdm0wNjRieG1haXVrcGVicHBsNzJqNXZ0eSZlcF92MV9naWZzX3NlYXJjaCZjdD1n/dT6f2FnfY24C1L1TIR/giphy.gif"
CHANNEL_LINK = "https://www.youtube.com/@thisolis"
INST_LINK = "https://www.instagram.com/whoisolis/"
RULES_LINK = "https://olishalper.github.io/olis-chat-rules/"

# === МОДЕРАЦИЯ ===
STOP_WORDS = [
    "терроризм",
    "заработай",
    "быстрый доход",
    "крипта",
    "слив",
    "продаю",
    "куплю",

    # Войны / Экстремизм
    "геноцид",
    "фашизм",
    "нацизм",
    "экстремизм",
    "террор",
    "путин",
    "русня",
    "хохлы",
    "хохол",
    "пидор",
    "зеля",
    "зеленский",

    # Запрещенный контент (Педофилия, Зоофилия)
    "педофилия",
    "педофил",
    "зоофилия",
    "нсфл", # NSFW/NSFL в русском сленге
    "детское порно",
    "порнография с животными",

    # Дискриминация (Расизм, Сексизм, Гомофобия)
    "пидорасы",
    "педик",
    "сдохни",
    "лесбуха",
    "лесбухи",
    "лезбуха",
    "лезбухи",
    "национализм",
    "ксенофобия",

    # Добавьте сюда другие слова и фразы (например, нецензурная лексика, экстремизм и т.д.)
]

MUTE_DURATION_SECONDS = 3600 # 1 час
FLOOD_LIMIT = 10
TIME_WINDOW_SECONDS = 10
USER_ACTIVITY = {} # {user_id: [(timestamp, message_id), ...]}

# === ОТСЛЕЖИВАНИЕ МЕДИА-ГРУПП для устранения дублирования ===
# Словарь для отслеживания уже обработанных медиа-групп (альбомов)
PROCESSED_MEDIA_GROUPS = {} # {media_group_id: timestamp}
MEDIA_GROUP_TIMEOUT = 10 # Время, в течение которого сообщения считаются частью группы (в секундах)

# === КНОПКИ ===
def get_buttons():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("🧾 Правила", url=RULES_LINK))
    return keyboard

# === ФУНКЦИЯ ОТПРАВКИ ПРИВЕТСТВИЯ С ПОВТОРНЫМИ ПОПЫТКАМИ ===
def send_welcome_message(chat_id, reply_to_message_id=None):
    """Отправляет приветствие, пытаясь повторно, чтобы избежать ошибки 'message to be replied not found'."""
    caption = (
        "👋 Привет ты попал в комментарии под моим постом. Внизу интересные ссылки и правила поведения (пожалуйста почитай их страничка сделана вроде симпатично)🐳\n\n"
        "📸 Мой <a href='{inst}'>инстаграм</a>\n"
        "🔴 Мой <a href='{yt}'>ютуб</a>\n\n"
        "Написав комментарий, ты соглашаешься с "
        "<a href='{rules}'>правилами</a> чата 🐳"
    ).format(inst=INST_LINK, yt=CHANNEL_LINK, rules=RULES_LINK)

    max_retries = 3
    delay = 1.0 # Начальная задержка

    for attempt in range(max_retries):
        try:
            bot.send_animation(
                chat_id=chat_id,
                animation=GIF_URL,
                caption=caption,
                parse_mode="HTML",
                reply_markup=get_buttons(),
                reply_to_message_id=reply_to_message_id
            )
            logging.info(f"✅ Приветствие отправлено (попытка {attempt+1}) в ответ на ID: {reply_to_message_id}")
            return # Успех
        
        except apihelper.ApiTelegramException as e:
            error_message = str(e)
            
            # Обработка частой ошибки (сообщение еще не доступно в Telegram API)
            if attempt < max_retries - 1 and "Bad Request: message to be replied not found" in error_message:
                logging.warning(f"⚠️ Ошибка 400: Сообщение для ответа {reply_to_message_id} не найдено. Повтор через {delay:.1f} сек. ({attempt+1}/{max_retries})")
                time.sleep(delay)
                delay *= 1.5 
                continue
            
            # В случае других ошибок API, пробуем отправить просто текст
            logging.warning(f"⚠️ Ошибка отправки GIF-приветствия (попытка {attempt+1}): {e}. Отправка текстовой версии.")
            
            try:
                bot.send_message(
                    chat_id, 
                    caption, 
                    parse_mode="HTML", 
                    reply_markup=get_buttons(),
                    reply_to_message_id=reply_to_message_id
                )
                logging.info(f"✅ Приветствие (текст) отправлено.")
                return 
            except Exception as e_text:
                logging.error(f"❌ Критическая ошибка: не удалось отправить даже текстовое приветствие: {e_text}", exc_info=True)
                return 

        except Exception as e:
            logging.error(f"❌ Неизвестная ошибка при отправке приветствия: {e}", exc_info=True)
            return

    logging.error(f"❌ Не удалось отправить приветствие после {max_retries} попыток.")


# === КОМАНДА /start ===
@bot.message_handler(commands=['start'])
def send_rules(message):
    reply_id = getattr(message.reply_to_message, 'message_id', None)
    send_welcome_message(message.chat.id, reply_to_message_id=reply_id)


# === ОБРАБОТКА АВТОМАТИЧЕСКИ ПЕРЕСЛАННЫХ ПОСТОВ (ТРИГГЕР ПРИВЕТСТВИЯ) ===
@bot.message_handler(
    func=lambda m: m.chat.id == DISCUSSION_GROUP_ID and m.is_automatic_forward, 
    content_types=['text', 'photo', 'video', 'audio', 'voice', 'video_note', 'document', 'sticker', 'animation', 'poll']
)
def handle_forwarded_channel_post(message):
    global PROCESSED_MEDIA_GROUPS
    
    logging.info(f"👀 [ТРИГГЕР] Получен автоматический форвард. ID: {message.message_id}. Media Group ID: {message.media_group_id}")
    
    try:
        # --- БЛОК АНТИ-ДУБЛИКАТ ДЛЯ МЕДИА-ГРУПП ---
        if message.media_group_id:
            now = time.time()
            
            # 1. Очистка старых записей
            PROCESSED_MEDIA_GROUPS = {k: v for k, v in PROCESSED_MEDIA_GROUPS.items() if now - v < MEDIA_GROUP_TIMEOUT}
            
            # 2. Проверка, была ли эта медиа-группа уже обработана
            if message.media_group_id in PROCESSED_MEDIA_GROUPS:
                logging.info(f"⏭ [ТРИГГЕР] Пропуск дубликата медиа-группы {message.media_group_id}. Приветствие уже отправлено.")
                return # Выходим, чтобы избежать дублирования
            
            # 3. Пометка группы как обработанной
            PROCESSED_MEDIA_GROUPS[message.media_group_id] = now
            logging.info(f"📢 [ТРИГГЕР] Новый пост (медиа-группа {message.media_group_id}). Запуск приветствия...")
            
        else:
            # Одиночный пост (текст, одно фото, одно видео и т.д.)
            logging.info(f"📢 [ТРИГГЕР] Новый одиночный пост. Запуск приветствия...")

        # Отправляем приветствие, отвечая на сам пересланный пост из канала
        send_welcome_message(DISCUSSION_GROUP_ID, reply_to_message_id=message.message_id)
        
    except Exception as e:
        logging.error(f"⚠️ Ошибка при обработке пересланного поста: {e}", exc_info=True)


# === МУТ ===
def apply_mute(chat_id, user_id, username, reason, reply_to_message_id=None):
    try:
        mute_until = datetime.datetime.now() + datetime.timedelta(seconds=MUTE_DURATION_SECONDS)
        
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
        
        bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions,
            until_date=int(mute_until.timestamp())
        )
        
        bot.send_message(
            chat_id, 
            f"@{username} ⚠️ {reason}\nМут на 1 час.",
            reply_to_message_id=reply_to_message_id
        )
        logging.warning(f"🔇 Мут {username} до {mute_until}. Причина: {reason}")
    except Exception as e:
        logging.error(f"❌ Ошибка при выдаче мута. Проверьте права бота: {e}", exc_info=True)

# === ФУНКЦИЯ ДЛЯ ПОИСКА ИСХОДНОГО ПОСТА КАНАЛА ===
def find_channel_post_id(message):
    """Находит ID автоматически пересланного поста канала, на который нужно ответить в треде"""
    try:
        if message.reply_to_message:
            # Проверяем, является ли родительское сообщение автоматическим форвардом
            if getattr(message.reply_to_message, 'is_automatic_forward', False):
                return message.reply_to_message.message_id
            # Рекурсивно проверяем цепочку ответов
            return find_channel_post_id(message.reply_to_message)
        return None
    except:
        return None

# === АНТИФЛУД И СТОП-СЛОВА (МОДЕРАЦИЯ КОММЕНТАРИЕВ) ===
@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document', 'audio', 'voice', 'animation'])
def handle_messages(message):
    global USER_ACTIVITY
    
    # 1. Игнорируем автоматически пересланные посты
    if getattr(message, 'is_automatic_forward', False):
        return
    
    # 2. Обрабатываем только в целевой группе комментариев
    if message.chat.id != DISCUSSION_GROUP_ID:
        return
        
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id
    
    logging.info(f"👀 [МОДЕРАЦИЯ] Получен комментарий от @{username}. Тип: {message.content_type}")
    
    # Ищем исходный пост канала для ответа-уведомления о муте
    channel_post_id = find_channel_post_id(message)

    # --- Антифлуд ---
    now = datetime.datetime.now().timestamp()
    USER_ACTIVITY.setdefault(user_id, [])
    
    # Очищаем старые записи
    USER_ACTIVITY[user_id] = [(t, msg_id) for t, msg_id in USER_ACTIVITY[user_id] if now - t < TIME_WINDOW_SECONDS]
    USER_ACTIVITY[user_id].append((now, message.message_id))

    if len(USER_ACTIVITY[user_id]) >= FLOOD_LIMIT:
        logging.warning(f"🚨 [МОДЕРАЦИЯ] Обнаружен флуд от @{username}. Выдача мута.")
        
        # Удаляем ВСЕ сообщения из флуда
        for timestamp, msg_id in USER_ACTIVITY[user_id]:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                logging.error(f"⚠️ Не удалось удалить сообщение {msg_id} во время флуда: {e}")
            
        apply_mute(
            chat_id, 
            user_id, 
            username, 
            f"Флуд ({FLOOD_LIMIT}+ сообщений за {TIME_WINDOW_SECONDS} секунд)",
            reply_to_message_id=channel_post_id
        )
        USER_ACTIVITY[user_id] = [] # Очищаем активность после мута
        return

    # --- Стоп-слова ---
    if message.text:
        text = message.text.lower()
        for word in STOP_WORDS:
            # Используем поиск слова в тексте
            if word in text:
                logging.warning(f"🚨 [МОДЕРАЦИЯ] Обнаружено стоп-слово '{word}' от @{username}. Выдача мута.")
                
                try:
                    bot.delete_message(chat_id, message.message_id)
                except Exception as e:
                    logging.error(f"⚠️ Не удалось удалить сообщение со стоп-словом: {e}")
                
                apply_mute(
                    chat_id, 
                    user_id, 
                    username, 
                    f"Стоп-слово: {word}",
                    reply_to_message_id=channel_post_id
                )
                return
    
    logging.info(f"✅ [МОДЕРАЦИЯ] Комментарий от @{username} прошел проверку.")
            
# === ЗАПУСК (АДАПТАЦИЯ ДЛЯ GUNICORN/FLASK) ===

# Инициализация Flask приложения (необходимо для Gunicorn)
app = Flask(__name__)

# Функция, которая будет запускать Polling в фоновом потоке
def run_polling():
    # Эта функция выполняется в фоновом потоке
    logging.info("🧹 Попытка удаления старого Webhook...")
    try:
        bot.remove_webhook() 
        logging.info("✅ Webhook удален успешно")
        time.sleep(1)
    except Exception as e:
        logging.warning(f"⚠️ Ошибка при удалении webhook (возможно, его не было): {e}")

    logging.info("🚀 [КРИТИЧЕСКИЙ ЛОГ] Бот готов к запуску Infinity Polling...")
    try:
        # Запуск Polling. Указываем все типы обновлений для надежности.
        bot.infinity_polling(allowed_updates=['message', 'channel_post', 'my_chat_member', 'chat_member'])
    except Exception as e:
        logging.critical(f"❌ Критическая ошибка Polling: {e}", exc_info=True)


# Маршруты Flask (необходимы для health check хостинга)
@app.route('/')
def index():
    return 'Telegram bot running (polling mode)', 200

@app.route('/health')
def health():
    return 'OK', 200

# Запуск бота в отдельном потоке
if __name__ == '__main__':
    # При локальном запуске (python bot.py)
    run_polling()
else:
    # При запуске через Gunicorn (gunicorn bot:app)
    # Gunicorn импортирует 'app', а мы запускаем Polling в фоновом потоке.
    logging.info("☁️ Запуск через Gunicorn. Polling будет запущен в отдельном потоке.")
    polling_thread = threading.Thread(target=run_polling, daemon=True)
    polling_thread.start()
