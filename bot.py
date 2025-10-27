import os
import time
import datetime
import threading
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions

# === НАСТРОЙКИ ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден. Установи его в переменные окружения!")

bot = telebot.TeleBot(TOKEN)

# === ОСНОВНЫЕ ССЫЛКИ ===
CHANNEL_USERNAME = "whoisolis"  # без @
DISCUSSION_GROUP_ID = -1003083438241  # ID группы комментариев

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

MUTE_DURATION_SECONDS = 3600  # 1 час
MUTE_MESSAGE = "🚨 Сообщение удалено за нарушение правил. Мут на 1 час."

FLOOD_LIMIT = 10
TIME_WINDOW_SECONDS = 10
USER_ACTIVITY = {}  # {user_id: [timestamps...]}

# === КНОПКИ ===
def get_buttons():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("🧾 Правила", url=RULES_LINK))
    return keyboard

# === ПРИВЕТСТВИЕ ===
def send_welcome_message(chat_id, reply_to_message_id=None):
    caption = (
        "👋 Привет! Ты попал в комментарии под моим постом 🐳\n\n"
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
        print(f"✅ Приветствие отправлено в чат {chat_id}")
    except Exception as e:
        print(f"⚠️ Ошибка отправки приветствия: {e}")
        bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=get_buttons())

# === КОМАНДА /start ===
@bot.message_handler(commands=['start'])
def send_rules(message):
    send_welcome_message(message.chat.id)

# === ОТСЛЕЖИВАНИЕ ПОСТОВ ===
LAST_MEDIA_GROUP = {}

@bot.channel_post_handler(content_types=['all'])
def handle_channel_post(message):
    global LAST_MEDIA_GROUP
    username = message.chat.username
    media_group_id = getattr(message, 'media_group_id', None)

    # фильтр по каналу
    if not username or username.lower() != CHANNEL_USERNAME.lower():
        return

    # защита от дублирования при нескольких фото/видео
    if media_group_id:
        last_time = LAST_MEDIA_GROUP.get(media_group_id)
        if last_time and time.time() - last_time < 5:
            print(f"⏭ Пропущен дубликат альбома {media_group_id}")
            return
        LAST_MEDIA_GROUP[media_group_id] = time.time()

    print("📢 Новый пост в канале! Отправляю сообщение в комментарии...")
    time.sleep(1.5)
    send_welcome_message(DISCUSSION_GROUP_ID, reply_to_message_id=message.message_id)

# === МУТ ===
def apply_mute(chat_id, user_id, username, reason, reply_to_message_id=None):
    try:
        mute_until = datetime.datetime.now() + datetime.timedelta(seconds=MUTE_DURATION_SECONDS)
        bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=mute_until.timestamp()
        )
        bot.send_message(
            chat_id,
            f"@{username} ⚠️ {reason}\nМут на 1 час.",
            reply_to_message_id=reply_to_message_id
        )
        print(f"🔇 Мут выдан @{username} до {mute_until}")
    except Exception as e:
        print(f"❌ Ошибка при выдаче мута: {e}")

# === АНТИФЛУД И СТОП-СЛОВА ===
@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document', 'audio', 'voice'])
def handle_messages(message):
    if message.chat.type not in ['group', 'supergroup']:
        return

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id

    # антифлуд
    now = datetime.datetime.now().timestamp()
    USER_ACTIVITY.setdefault(user_id, [])
    USER_ACTIVITY[user_id] = [t for t in USER_ACTIVITY[user_id] if now - t < TIME_WINDOW_SECONDS]
    USER_ACTIVITY[user_id].append(now)

    if len(USER_ACTIVITY[user_id]) >= FLOOD_LIMIT:
        bot.delete_message(chat_id, message.message_id)
        apply_mute(chat_id, user_id, username, f"Флуд ({FLOOD_LIMIT}+ сообщений за {TIME_WINDOW_SECONDS} сек)")
        USER_ACTIVITY[user_id] = []
        return

    # стоп-слова
    if message.text:
        text = message.text.lower()
        for word in STOP_WORDS:
            if word in text:
                bot.delete_message(chat_id, message.message_id)
                apply_mute(chat_id, user_id, username, f"Стоп-слово: {word}")
                break

# === WEBHOOK для Render ===
app = Flask(__name__)

@app.route('/')
def index():
    return '🤖 Telegram bot is running via webhook', 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Unsupported Media Type', 415

# === ЗАПУСК ===
if __name__ == '__main__':
    print("🚀 Бот запущен в режиме WEBHOOK для Render")

    WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"

    # Удаляем старый вебхук и ставим новый
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL)

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
