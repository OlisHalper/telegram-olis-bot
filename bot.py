import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import os
import time
import datetime
from flask import Flask, request
import traceback

# === НАСТРОЙКИ ===
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# === ОСНОВНЫЕ ССЫЛКИ ===
CHANNEL_USERNAME = "@whoisolis"
CHANNEL_ID = -1003083438241  # ID канала
DISCUSSION_GROUP_ID = -1003210182852  # ID группы комментариев

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

MUTE_DURATION_SECONDS = 3600
FLOOD_LIMIT = 10
TIME_WINDOW_SECONDS = 10
USER_ACTIVITY = {}
PROCESSED_MEDIA_GROUPS = {}
MEDIA_GROUP_TIMEOUT = 60

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
        print(f"✅ Приветствие отправлено как ответ на сообщение {reply_to_message_id} в чат {chat_id}")
    except Exception as e:
        print(f"⚠️ Ошибка отправки приветствия: {e}")
        traceback.print_exc()

# === КОМАНДА /start ===
@bot.message_handler(commands=['start'])
def send_rules(message):
    send_welcome_message(message.chat.id)

# === ОБРАБОТЧИК СООБЩЕНИЙ С ДЕТАЛЬНЫМ ЛОГИРОВАНИЕМ ===
@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'audio', 'voice', 'video_note', 'document', 'sticker', 'animation', 'poll'])
def handle_all_messages(message):
    global PROCESSED_MEDIA_GROUPS, USER_ACTIVITY
    
    # Детальное логирование каждого сообщения
    print(f"\n{'='*60}")
    print(f"📨 Получено сообщение:")
    print(f"   Chat ID: {message.chat.id}")
    print(f"   Chat Type: {message.chat.type}")
    print(f"   Message ID: {message.message_id}")
    print(f"   Content Type: {message.content_type}")
    print(f"   Is Automatic Forward: {message.is_automatic_forward}")
    if hasattr(message, 'sender_chat') and message.sender_chat:
        print(f"   Sender Chat ID: {message.sender_chat.id}")
    if hasattr(message, 'forward_from_chat') and message.forward_from_chat:
        print(f"   Forward From Chat ID: {message.forward_from_chat.id}")
    if message.media_group_id:
        print(f"   Media Group ID: {message.media_group_id}")
    print(f"{'='*60}\n")
    
    # ОБРАБОТКА АВТОМАТИЧЕСКИ ПЕРЕСЛАННЫХ ПОСТОВ ИЗ КАНАЛА
    if message.chat.id == DISCUSSION_GROUP_ID and message.is_automatic_forward:
        try:
            now = time.time()
            PROCESSED_MEDIA_GROUPS = {k: v for k, v in PROCESSED_MEDIA_GROUPS.items() if now - v < MEDIA_GROUP_TIMEOUT}
            
            if message.media_group_id:
                if message.media_group_id in PROCESSED_MEDIA_GROUPS:
                    print(f"⏭ Пропуск дубликата медиа-группы {message.media_group_id}")
                    return
                PROCESSED_MEDIA_GROUPS[message.media_group_id] = now
                print(f"📢 Новая медиа-группа из канала: {message.media_group_id}")
            else:
                print(f"📢 Новый пост из канала")
            
            time.sleep(1)
            send_welcome_message(DISCUSSION_GROUP_ID, reply_to_message_id=message.message_id)
        except Exception as e:
            print(f"⚠️ Ошибка при обработке пересланного поста: {e}")
            traceback.print_exc()
        return
    
    # ИГНОРИРУЕМ АВТОМАТИЧЕСКИЕ ПЕРЕСЫЛКИ В ОСТАЛЬНЫХ СЛУЧАЯХ
    if message.is_automatic_forward:
        print("⏭ Пропуск автоматической пересылки (не из нужной группы)")
        return
    
    # ОБРАБОТКА ОБЫЧНЫХ СООБЩЕНИЙ В ГРУППЕ (АНТИФЛУД И СТОП-СЛОВА)
    if message.chat.type not in ['group', 'supergroup']:
        print("⏭ Пропуск (не группа)")
        return

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id
    
    channel_post_id = find_channel_post_id(message)

    now = datetime.datetime.now().timestamp()
    USER_ACTIVITY.setdefault(user_id, [])
    USER_ACTIVITY[user_id] = [(t, msg_id) for t, msg_id in USER_ACTIVITY[user_id] if now - t < TIME_WINDOW_SECONDS]
    USER_ACTIVITY[user_id].append((now, message.message_id))

    if len(USER_ACTIVITY[user_id]) >= FLOOD_LIMIT:
        for timestamp, msg_id in USER_ACTIVITY[user_id]:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                print(f"⚠️ Не удалось удалить сообщение {msg_id}: {e}")
        
        apply_mute(chat_id, user_id, username, f"Флуд ({FLOOD_LIMIT}+ сообщений за {TIME_WINDOW_SECONDS} секунд)", reply_to_message_id=channel_post_id)
        USER_ACTIVITY[user_id] = []
        return

    if message.text:
        text = message.text.lower()
        for word in STOP_WORDS:
            if word in text:
                bot.delete_message(chat_id, message.message_id)
                apply_mute(chat_id, user_id, username, f"Стоп-слово: {word}", reply_to_message_id=channel_post_id)
                break

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
        bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=permissions, until_date=int(mute_until.timestamp()))
        bot.send_message(chat_id, f"@{username} ⚠️ {reason}\nМут на 1 час.", reply_to_message_id=reply_to_message_id)
        print(f"🔇 Мут {username} до {mute_until}")
    except Exception as e:
        print(f"❌ Ошибка при выдаче мута: {e}")
        traceback.print_exc()

def find_channel_post_id(message):
    try:
        if message.reply_to_message:
            if message.reply_to_message.is_automatic_forward:
                return message.reply_to_message.message_id
            return find_channel_post_id(message.reply_to_message)
        return None
    except:
        return None

# === ЗАПУСК С WEBHOOK ===
print("🚀 Бот запущен и слушает события...")

if 'RENDER' in os.environ:
    app = Flask(__name__)
    WEBHOOK_URL = os.getenv('RENDER_EXTERNAL_URL')
    
    if WEBHOOK_URL:
        webhook_path = f"/{TOKEN}"
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=f"{WEBHOOK_URL}{webhook_path}")
            print(f"✅ Webhook установлен: {WEBHOOK_URL}{webhook_path}")
        except Exception as e:
            print(f"❌ Ошибка установки webhook: {e}")
            traceback.print_exc()
    
    @app.route('/')
    def index():
        return 'Telegram bot running (webhook mode)'
    
    @app.route('/health')
    def health():
        return 'OK'
    
    @app.route(f'/{TOKEN}', methods=['POST'])
    def webhook():
        try:
            json_string = request.get_data().decode('utf-8')
            print(f"📥 Получен webhook")
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            print(f"✅ Update обработан успешно")
            return 'OK', 200
        except Exception as e:
            print(f"❌ Ошибка обработки webhook: {e}")
            traceback.print_exc()
            return 'ERROR', 500
    
    port = int(os.environ.get('PORT', 5000))
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=port)
else:
    bot.infinity_polling()
