import os
import time
import datetime
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import logging

# === НАСТРОЙКИ ЛОГИРОВАНИЯ ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === КОНФИГУРАЦИЯ БОТА ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.error("❌ BOT_TOKEN не найден. Установи его в переменные окружения!")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# === ОСНОВНЫЕ ССЫЛКИ И ID ===
CHANNEL_USERNAME = "whoisolis"  # без @
# ID группы комментариев
DISCUSSION_GROUP_ID = -1003083438241

GIF_URL = "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3bThjMXZkMTExb2IzZW9zdm0wNjRieG1haXVrcGVicHBsNzJqNXZ0eSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/dT6f2FnfY24C1L1TIR/giphy.gif"
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

MUTE_DURATION_SECONDS = 3600  # 1 час
FLOOD_LIMIT = 10
TIME_WINDOW_SECONDS = 10
# {user_id: [(timestamp, message_id), ...]} - хранит метку времени и ID сообщения
USER_ACTIVITY = {}  

# === ОТСЛЕЖИВАНИЕ МЕДИА-ГРУПП ===
LAST_MEDIA_GROUP = {}
MEDIA_GROUP_TIMEOUT = 5 # секунд

# === КНОПКИ ===
def get_buttons():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("🧾 Правила", url=RULES_LINK))
    return keyboard

# === ПРИВЕТСТВИЕ ===
def send_welcome_message(chat_id, reply_to_message_id=None):
    caption = (
        "👋 Привет ты попал в комментарии под моим постом. Внизу интересные ссылки и правила поведения (пожалуйста почитай их страничка сделана вроде симпатично\n\n"
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
        logging.info(f"✅ Приветствие (GIF) отправлено в чат {chat_id}")
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

# === ОБРАБОТКА НОВЫХ ПОСТОВ В КАНАЛЕ (ЛУЧШИЙ МЕТОД) ===
@bot.channel_post_handler(content_types=['all'])
def handle_channel_post(message):
    global LAST_MEDIA_GROUP
    
    username = message.chat.username
    media_group_id = getattr(message, 'media_group_id', None)

    # Проверяем, что пост именно из нашего канала
    if username and username.lower() != CHANNEL_USERNAME.lower():
        return

    # Защита от дублирования при альбомах (медиа-группах)
    if media_group_id:
        last_time = LAST_MEDIA_GROUP.get(media_group_id)
        if last_time and time.time() - last_time < MEDIA_GROUP_TIMEOUT:
            logging.info(f"⏭ Пропущен дубликат альбома {media_group_id}")
            return
        LAST_MEDIA_GROUP[media_group_id] = time.time()
        time.sleep(1) # Небольшая задержка для альбомов, чтобы избежать гонки

    logging.info(f"📢 Новый пост в канале (ID: {message.message_id}). Отправляю приветствие в комментарии...")
    # message.message_id становится ID треда в группе комментариев
    send_welcome_message(DISCUSSION_GROUP_ID, reply_to_message_id=message.message_id)

# === МУТ ===
def apply_mute(chat_id, user_id, username, reason, reply_to_message_id=None):
    try:
        mute_until = datetime.datetime.now() + datetime.timedelta(seconds=MUTE_DURATION_SECONDS)
        bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            # Разрешаем только просматривать историю
            permissions=ChatPermissions(can_send_messages=False),
            until_date=int(mute_until.timestamp())
        )
        bot.send_message(
            chat_id,
            f"@{username} ⚠️ Причина: {reason}\nМут на 1 час.",
            reply_to_message_id=reply_to_message_id
        )
        logging.warning(f"🔇 Мут выдан {username} до {mute_until}. Причина: {reason}")
    except Exception as e:
        logging.error(f"❌ Ошибка при выдаче мута. Проверьте права бота: {e}", exc_info=True)


# === АНТИФЛУД И СТОП-СЛОВА ===
@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document', 'audio', 'voice', 'animation'])
def handle_messages(message):
    # Обрабатываем сообщения только в целевой группе
    if message.chat.id != DISCUSSION_GROUP_ID:
        return

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id
    message_id = message.message_id

    # --- Антифлуд логика ---
    now = datetime.datetime.now().timestamp()
    USER_ACTIVITY.setdefault(user_id, [])
    
    # 1. Фильтруем старые записи и добавляем текущее сообщение (timestamp, message_id)
    USER_ACTIVITY[user_id] = [(t, msg_id) for t, msg_id in USER_ACTIVITY[user_id] if now - t < TIME_WINDOW_SECONDS]
    USER_ACTIVITY[user_id].append((now, message_id))

    if len(USER_ACTIVITY[user_id]) >= FLOOD_LIMIT:
        logging.warning(f"🚨 Обнаружен флуд от пользователя {user_id} (@{username})")

        # 2. Удаляем все сообщения, которые вызвали флуд
        for timestamp, msg_id in USER_ACTIVITY[user_id]:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                logging.error(f"⚠️ Не удалось удалить сообщение {msg_id} во время флуда: {e}")
            
        # 3. Выдаем мут
        apply_mute(chat_id, user_id, username, f"Флуд ({FLOOD_LIMIT}+ сообщений за {TIME_WINDOW_SECONDS} сек)", reply_to_message_id=message_id)
        USER_ACTIVITY[user_id] = [] # Очищаем после мута, чтобы избежать повторного мута сразу же
        return

    # --- Стоп-слова логика ---
    if message.text:
        text = message.text.lower()
        for word in STOP_WORDS:
            if word in text:
                logging.warning(f"🚨 Обнаружено стоп-слово '{word}' от @{username}")
                
                try:
                    bot.delete_message(chat_id, message_id)
                except Exception as e:
                    logging.error(f"⚠️ Не удалось удалить сообщение со стоп-словом: {e}")
                
                apply_mute(chat_id, user_id, username, f"Стоп-слово: {word}", reply_to_message_id=message_id)
                return


# === WEBHOOK для Render (ИСПРАВЛЕНО) ===
app = Flask(__name__)

# Определяем путь вебхука как /ТОКЕН для совместимости с Telegram
WEBHOOK_PATH = f"/{TOKEN}"

@app.route('/')
def index():
    return f'🤖 Telegram bot is running via webhook on path {WEBHOOK_PATH}', 200

# !!! ИСПРАВЛЕННЫЙ РОУТ !!!
# Теперь Flask будет слушать ТОЧНО тот путь, который использует Telegram: /<token>
@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('UTF-8')
        
        try:
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
        except Exception as e:
            logging.error(f"❌ Ошибка обработки обновления: {e}", exc_info=True)
            # В случае ошибки все равно возвращаем 200, чтобы избежать повторных попыток Telegram
            
        return '', 200
    else:
        return 'Unsupported Media Type', 415

# === ЗАПУСК ===
if __name__ == '__main__':
    
    hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
    if not hostname:
        logging.error("❌ Переменная RENDER_EXTERNAL_HOSTNAME не найдена. Бот не сможет настроить вебхук.")
        exit(1)

    # Формируем полный URL с токеном в пути
    WEBHOOK_URL = f"https://{hostname}{WEBHOOK_PATH}"

    try:
        bot.remove_webhook()
        time.sleep(0.5)
        bot.set_webhook(url=WEBHOOK_URL)
        logging.info(f"✅ Webhook установлен успешно: {WEBHOOK_URL}")
    except Exception as e:
        logging.error(f"❌ Не удалось установить Webhook: {e}", exc_info=True)
        exit(1)

    logging.info("🚀 Бот запущен в режиме WEBHOOK для Render")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
