import os
import time
import datetime
import logging
from flask import Flask, request
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions

# === НАСТРОЙКИ ЛОГИРОВАНИЯ ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === КОНФИГУРАЦИЯ БОТА ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.error("❌ BOT_TOKEN не найден. Установи его в переменные окружения!")
    # Выход при отсутствии токена
    exit(1) 

bot = telebot.TeleBot(TOKEN)

# === ОСНОВНЫЕ ССЫЛКИ И ID ===
CHANNEL_USERNAME = "whoisolis" # Использовать без @ для проверки в коде
# ВНИМАНИЕ: Если бот не отвечает в группе комментариев, возможно, эти ID нужно перепроверить!
CHANNEL_ID = -1003083438241 # ID канала (или группы, куда приходят посты)
DISCUSSION_GROUP_ID = -1003210182852 # ID группы комментариев

GIF_URL = "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3bThjMXZkMTExb2IzZW9zdm0wNjRieG1haXVrcGVicHBsNzJqNXZ0eSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/dT6f2FnfY24C1L1TIR/giphy.gif"
CHANNEL_LINK = "https://www.youtube.com/@thisolis"
INST_LINK = "https://www.instagram.com/whoisolis/"
RULES_LINK = "https://olishalper.github.io/olis-chat-rules/"

# === МОДЕРАЦИЯ ===

STOP_WORDS = [
    "терроризм", "заработай", "быстрый доход", "крипта", "слив", 
    "продаю", "куплю", "геноцид", "фашизм", "нацизм", "экстремизм", 
    "террор", "путин", "русня", "хохлы", "хохол", "пидор", "зеля", 
    "зеленский", "педофилия", "педофил", "зоофилия", "нсфл", 
    "детское порно", "порнография с животными", "пидорасы", 
    "педик", "сдохни", "лесбуха", "лесбухи", "лезбуха", 
    "лезбухи", "национализм", "ксенофобия",
]

MUTE_DURATION_SECONDS = 3600 # 1 час
FLOOD_LIMIT = 10
TIME_WINDOW_SECONDS = 10
USER_ACTIVITY = {} # {user_id: [(timestamp, message_id), ...]}

# === ОТСЛЕЖИВАНИЕ МЕДИА-ГРУПП ===
PROCESSED_MEDIA_GROUPS = {} # {media_group_id: timestamp}
MEDIA_GROUP_TIMEOUT = 60 # секунд
MEDIA_GROUP_LOCK = threading.Lock() # Блокировка для атомарной проверки медиа-групп

# === КНОПКИ ===
def get_buttons():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("🧾 Правила", url=RULES_LINK))
    return keyboard

# === ПРИВЕТСТВИЕ ===
def send_welcome_message(chat_id, reply_to_message_id=None):
    caption = (
        "👋 Привет ты попал в комментарии под моим постом. Внизу интересные ссылки и правила поведения (пожалуйста почитай их страничка сделана вроде симпатично)🐳\n\n"
        "📸 Мой <a href='{inst}'>инстаграм</a>\n"
        "🔴 Мой <a href='{yt}'>ютуб</a>\n\n"
        "Написав комментарий, ты соглашаешься с "
        "<a href='{rules}'>правилами</a> чата 🐳"
    ).format(inst=INST_LINK, yt=CHANNEL_LINK, rules=RULES_LINK)

    try:
        bot.send_animation(
            chat_id=chat_id,
            animation=GIF_URL,
            caption=caption,
            parse_mode="HTML",
            reply_markup=get_buttons(),
            reply_to_message_id=reply_to_message_id
        )
        logging.info(f"✅ Приветствие отправлено как ответ на сообщение {reply_to_message_id} в чат {chat_id}")
    except Exception as e:
        logging.warning(f"⚠️ Ошибка отправки GIF-приветствия: {e}. Отправка текстовой версии.")
        try:
            bot.send_message(
                chat_id, 
                caption, 
                parse_mode="HTML", 
                reply_markup=get_buttons(),
                reply_to_message_id=reply_to_message_id
            )
            logging.info(f"✅ Приветствие (текст) отправлено.")
        except Exception as e_text:
            logging.error(f"❌ Критическая ошибка: не удалось отправить даже текстовое приветствие: {e_text}", exc_info=True)


# === КОМАНДА /start ===
@bot.message_handler(commands=['start'])
def send_rules(message):
    # Отправляем приветствие в ЛС или в ответ на сообщение в группе
    if message.chat.type == 'private':
        send_welcome_message(message.chat.id)
    elif message.chat.id == DISCUSSION_GROUP_ID:
        # Находим ID поста, на который отвечает сообщение, если это тред
        reply_id = getattr(message.reply_to_message, 'message_id', None)
        send_welcome_message(message.chat.id, reply_to_message_id=reply_id)

# === ОБРАБОТКА ПОСТОВ В КАНАЛЕ (ПЕРВЫЙ ЭТАП) ===
@bot.channel_post_handler(content_types=['all'])
def handle_channel_post(message):
    global PROCESSED_MEDIA_GROUPS
    
    # 0. Обрабатываем только посты из целевого канала
    if message.chat.id != CHANNEL_ID:
        logging.info(f"⏭ Игнорируется пост из чата {message.chat.id} (ожидался {CHANNEL_ID}).")
        return

    try:
        now = time.time()
        
        # 1. Очищаем старые медиа-группы (до блокировки, чтобы минимизировать время блокировки)
        PROCESSED_MEDIA_GROUPS = {k: v for k, v in PROCESSED_MEDIA_GROUPS.items() if now - v < MEDIA_GROUP_TIMEOUT}
        
        should_send_welcome = True

        # 2. Проверяем, является ли это частью медиа-группы, и управляем дублированием
        if message.media_group_id:
            # Используем блокировку для обеспечения атомарной проверки
            with MEDIA_GROUP_LOCK:
                if message.media_group_id in PROCESSED_MEDIA_GROUPS:
                    logging.info(f"⏭ Пропуск дубликата медиа-группы {message.media_group_id} (ID поста: {message.message_id}).")
                    # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: немедленно выходим для дубликатов
                    return 
                else:
                    # Помечаем медиа-группу как обработанную, чтобы следующие сообщения были пропущены
                    PROCESSED_MEDIA_GROUPS[message.media_group_id] = now
                    logging.info(f"📢 Новая медиа-группа из канала: {message.media_group_id} (ID поста: {message.message_id}).")
        else:
            logging.info(f"📢 Новый одиночный пост в канале (ID: {message.message_id}).")
        
        # 3. Отправляем приветствие, только если оно не было пропущено (т.е. это не дубликат)
        time.sleep(1) # Небольшая задержка, чтобы дать время треду открыться
        send_welcome_message(DISCUSSION_GROUP_ID, reply_to_message_id=message.message_id)
            
    except Exception as e:
        # ЭТО ВАЖНАЯ ПРОВЕРКА. Если тут ошибка, то бот, возможно, не админ в группе комментариев.
        logging.error(f"❌ Критическая ошибка при обработке поста в канале или отправке приветствия. Проверьте права бота в группе {DISCUSSION_GROUP_ID}: {e}", exc_info=True)

# === МУТ ===
def apply_mute(chat_id, user_id, username, reason, reply_to_message_id=None):
    try:
        mute_until = datetime.datetime.now() + datetime.timedelta(seconds=MUTE_DURATION_SECONDS)
        
        # Разрешаем все, кроме отправки сообщений и медиа
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
        
        # Отправляем уведомление
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
    """Находит ID автоматически пересланного поста канала в треде"""
    try:
        # Если это ответ на сообщение, проверяем родительское сообщение
        if message.reply_to_message:
            # Телеграм обычно помечает первый пересланный пост как automatic_forward
            if getattr(message.reply_to_message, 'is_automatic_forward', False):
                return message.reply_to_message.message_id
            # Если это ответ на чей-то комментарий, рекурсивно проверяем цепочку
            return find_channel_post_id(message.reply_to_message)
        return None
    except:
        return None

# === АНТИФЛУД И СТОП-СЛОВА ===
@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document', 'audio', 'voice', 'animation'])
def handle_messages(message):
    global USER_ACTIVITY
    
    # Игнорируем автоматически пересланные посты из канала
    if getattr(message, 'is_automatic_forward', False):
        return
    
    # Обрабатываем только в группе комментариев
    if message.chat.id != DISCUSSION_GROUP_ID:
        return

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id
    
    # Ищем исходный пост канала для ответа-уведомления
    channel_post_id = find_channel_post_id(message)
    reply_to_id = channel_post_id if channel_post_id else message.message_id # Если не нашли пост, отвечаем на само сообщение

    # --- Антифлуд ---
    now = datetime.datetime.now().timestamp()
    USER_ACTIVITY.setdefault(user_id, [])
    
    # Очищаем старые записи и добавляем текущее
    USER_ACTIVITY[user_id] = [(t, msg_id) for t, msg_id in USER_ACTIVITY[user_id] if now - t < TIME_WINDOW_SECONDS]
    USER_ACTIVITY[user_id].append((now, message.message_id))

    if len(USER_ACTIVITY[user_id]) >= FLOOD_LIMIT:
        logging.warning(f"🚨 Обнаружен флуд от @{username}")
        
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
            reply_to_message_id=reply_to_id
        )
        USER_ACTIVITY[user_id] = []
        return

    # --- Стоп-слова ---
    if message.text:
        text = message.text.lower()
        for word in STOP_WORDS:
            if word in text:
                logging.warning(f"🚨 Обнаружено стоп-слово '{word}' от @{username}")
                
                try:
                    bot.delete_message(chat_id, message.message_id)
                except Exception as e:
                    logging.error(f"⚠️ Не удалось удалить сообщение со стоп-словом: {e}")
                
                apply_mute(
                    chat_id,
                    user_id,
                    username,
                    f"Стоп-слово: {word}",
                    reply_to_message_id=reply_to_id
                )
                return
            
# === ЗАПУСК ===

# Переменная Flask, которую Render ожидает увидеть
app = Flask(__name__)

# Функция для запуска Polling в отдельном потоке
def run_polling():
    logging.info("🧹 Попытка удаления старого Webhook...")
    try:
        # Очень важно удалять Webhook перед Polling
        bot.remove_webhook() 
        logging.info("✅ Webhook удален успешно")
        time.sleep(1)
    except Exception as e:
        logging.warning(f"⚠️ Ошибка при удалении webhook (возможно, его не было): {e}")

    logging.info("🚀 Запуск бота в режиме Infinity Polling...")
    try:
        # Запуск Polling
        bot.infinity_polling(allowed_updates=['message', 'channel_post'])
    except Exception as e:
        logging.critical(f"❌ Критическая ошибка Polling: {e}", exc_info=True)


if 'RENDER_EXTERNAL_HOSTNAME' in os.environ:
    # 1. Запуск Polling в отдельном потоке
    polling_thread = threading.Thread(target=run_polling, daemon=True)
    polling_thread.start()
    
    # 2. Определение роутов Flask для заглушки
    @app.route('/')
    def index():
        return 'Telegram bot running (polling mode, thread is active: {})'.format(polling_thread.is_alive()), 200

    @app.route('/health')
    def health():
        return 'OK', 200

    # 3. Запуск Flask
    if __name__ == '__main__':
        port = int(os.environ.get('PORT', 5000))
        logging.info(f"🌐 Запуск Flask-заглушки на порту {port}")
        app.run(host='0.0.0.0', port=port)

else:
    # Обычный запуск на локальном ПК
    logging.info("🖥️ Локальный запуск (Polling)")
    run_polling()
