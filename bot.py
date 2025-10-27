import os
import time
import datetime
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import logging

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === КОНФИГУРАЦИЯ ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.error("❌ BOT_TOKEN не найден. Установи его в переменные окружения!")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# === ОСНОВНЫЕ ПАРАМЕТРЫ ===
CHANNEL_USERNAME = "whoisolis"  # без @
DISCUSSION_GROUP_ID = -1003083438241

GIF_URL = "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3bThjMXZkMTExb2IzZW9zdm0wNjRieG1haXVrcGVicHBsNzJqNXZ0eSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/dT6f2FnfY24C1L1TIR/giphy.gif"
CHANNEL_LINK = "https://www.youtube.com/@thisolis"
INST_LINK = "https://www.instagram.com/whoisolis/"
RULES_LINK = "https://olishalper.github.io/olis-chat-rules/"

# === ПОЛНЫЙ СТОП-ЛИСТ (включая все слова, как просили) ===
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
    "нсфл",  # NSFW/NSFL в русском сленге
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

    # Дополнительные слова/фразы, которые ты указывал ранее
    "пидор", "пидорас", "пидорассы", "пидорасик", "пидорок",
    "куплю", "продаю", "срочно", "помогите", "помогите заработать",
    "бот для заработка", "быстрые деньги", "быстро заработать",
    "скам", "scam", "развод", "памп", "шиткоин", "moon", "to the moon",
    "скилы", "ссылка на слив", "слив личных данных", "дамп", "продам аккаунт",
    # (оставил возможные вариации для устойчивой фильтрации)
]

MUTE_DURATION_SECONDS = 3600  # 1 час
FLOOD_LIMIT = 10
TIME_WINDOW_SECONDS = 10
USER_ACTIVITY = {}

LAST_MEDIA_GROUP = {}
MEDIA_GROUP_TIMEOUT = 5  # секунд

# === КНОПКИ ===
def get_buttons():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("🧾 Правила", url=RULES_LINK))
    return keyboard

# === ПРИВЕТСТВИЕ (точно как было указано тобой ранее) ===
def send_welcome_message(chat_id, reply_to_message_id=None):
    caption = (
        "👋 Привет ты попал в комментарии под моим постом. Внизу интересные ссылки и правила поведения (пожалуйста почитай их страничка сделана вроде симпатично)🐳\n\n"
        "📸 Мой <a href='{inst}'>инстаграм</a>.\n\n"
        "🔴 Мой <a href='{yt}'>ютуб</a>.\n\n"
        "Написав комментарий, вы соглашаетесь с "
        "<a href='{rules}'>правилами</a> чата.\n"
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
        logging.info("✅ Приветствие (GIF) отправлено.")
    except Exception as e:
        logging.warning(f"⚠️ Ошибка отправки GIF, отправляю текст: {e}")
        try:
            bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=get_buttons(), reply_to_message_id=reply_to_message_id)
            logging.info("✅ Приветствие (текст) отправлено.")
        except Exception as e_text:
            logging.error(f"❌ Не удалось отправить приветствие: {e_text}", exc_info=True)

# === КОМАНДА /start ===
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.chat.type == 'private':
        send_welcome_message(message.chat.id)
    elif message.chat.id == DISCUSSION_GROUP_ID:
        reply_id = getattr(message.reply_to_message, 'message_id', None)
        send_welcome_message(message.chat.id, reply_to_message_id=reply_id)

# === НОВЫЕ ПОСТЫ КАНАЛА (защита от дубликатов медиа-групп) ===
@bot.channel_post_handler(content_types=['all'])
def handle_channel_post(message):
    global LAST_MEDIA_GROUP
    username = message.chat.username
    media_group_id = getattr(message, 'media_group_id', None)

    # только наш канал
    if username and username.lower() != CHANNEL_USERNAME.lower():
        return

    # защита от альбомов (множество апдейтов с одним media_group_id)
    if media_group_id:
        last_time = LAST_MEDIA_GROUP.get(media_group_id)
        if last_time and time.time() - last_time < MEDIA_GROUP_TIMEOUT:
            logging.info(f"⏭ Пропущен дубликат альбома {media_group_id}")
            return
        LAST_MEDIA_GROUP[media_group_id] = time.time()
        time.sleep(1)

    logging.info(f"📢 Новый пост в канале (ID: {message.message_id}) — отправляю приветствие в комментарии")
    send_welcome_message(DISCUSSION_GROUP_ID, reply_to_message_id=message.message_id)

# === МУТ ===
def apply_mute(chat_id, user_id, username, reason, reply_to_message_id=None):
    try:
        mute_until = datetime.datetime.now() + datetime.timedelta(seconds=MUTE_DURATION_SECONDS)
        bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=int(mute_until.timestamp())
        )
        bot.send_message(chat_id, f"@{username} ⚠️ Причина: {reason}\nМут на 1 час.", reply_to_message_id=reply_to_message_id)
        logging.warning(f"🔇 Мут выдан @{username} до {mute_until}. Причина: {reason}")
    except Exception as e:
        logging.error(f"❌ Ошибка при выдаче мута: {e}", exc_info=True)

# === АНТИФЛУД + СТОП-слова ===
@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document', 'audio', 'voice', 'animation'])
def handle_messages(message):
    # только в группе обсуждений
    if message.chat.id != DISCUSSION_GROUP_ID:
        return

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id
    message_id = message.message_id
    now = datetime.datetime.now().timestamp()

    USER_ACTIVITY.setdefault(user_id, [])
    USER_ACTIVITY[user_id] = [(t, m) for t, m in USER_ACTIVITY[user_id] if now - t < TIME_WINDOW_SECONDS]
    USER_ACTIVITY[user_id].append((now, message_id))

    # флуд
    if len(USER_ACTIVITY[user_id]) >= FLOOD_LIMIT:
        logging.warning(f"🚨 Обнаружен флуд от {user_id} (@{username})")
        for _, msg_id in USER_ACTIVITY[user_id]:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                logging.error(f"⚠️ Не удалось удалить сообщение {msg_id}: {e}")
        apply_mute(chat_id, user_id, username, f"Флуд ({FLOOD_LIMIT}+ сообщений за {TIME_WINDOW_SECONDS} сек)", reply_to_message_id=message_id)
        USER_ACTIVITY[user_id] = []
        return

    # стоп-слова
    if message.text:
        text = message.text.lower()
        for word in STOP_WORDS:
            if word in text:
                logging.warning(f"🚨 Стоп-слово '{word}' от @{username}")
                try:
                    bot.delete_message(chat_id, message_id)
                except Exception as e:
                    logging.error(f"⚠️ Не удалось удалить сообщение: {e}")
                apply_mute(chat_id, user_id, username, f"Стоп-слово: {word}", reply_to_message_id=message_id)
                return

# === FLASK (WEBHOOK) ===
app = Flask(__name__)
WEBHOOK_PATH = f"/{TOKEN}"

@app.route('/')
def index():
    return f'🤖 Telegram bot is running via webhook on path {WEBHOOK_PATH}', 200

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        try:
            update = telebot.types.Update.de_json(request.get_data().decode('UTF-8'))
            bot.process_new_updates([update])
        except Exception as e:
            logging.error(f"❌ Ошибка обработки обновления: {e}", exc_info=True)
        return '', 200
    return 'Unsupported Media Type', 415

# === ЗАПУСК ===
if __name__ == '__main__':
    hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
    if not hostname:
        logging.error("❌ Переменная RENDER_EXTERNAL_HOSTNAME не найдена.")
        exit(1)

    WEBHOOK_URL = f"https://{hostname}{WEBHOOK_PATH}"
    try:
        bot.remove_webhook()
        time.sleep(0.5)
        bot.set_webhook(url=WEBHOOK_URL)
        logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}")
    except Exception as e:
        logging.error(f"❌ Не удалось установить Webhook: {e}", exc_info=True)
        exit(1)

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
