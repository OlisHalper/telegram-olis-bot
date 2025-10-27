import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import os
import time
import datetime

# === ДОБАВЛЕНО ДЛЯ РЕНДЕРА: Импорт Flask и threading ===
from flask import Flask, request
import threading
# --- ------------------------------------------------- ---

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

MUTE_DURATION_SECONDS = 3600  # 1 час
FLOOD_LIMIT = 10
TIME_WINDOW_SECONDS = 10
USER_ACTIVITY = {}  # {user_id: [(timestamp, message_id), ...]}

# === НОВОЕ: ОТСЛЕЖИВАНИЕ МЕДИА-ГРУПП ===
PROCESSED_MEDIA_GROUPS = {}  # {media_group_id: timestamp}
MEDIA_GROUP_TIMEOUT = 60  # секунд

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

# === КОМАНДА /start ===
@bot.message_handler(commands=['start'])
def send_rules(message):
    send_welcome_message(message.chat.id)

# === ОБРАБОТКА АВТОМАТИЧЕСКИ ПЕРЕСЛАННЫХ ПОСТОВ В ГРУППУ КОММЕНТАРИЕВ ===
@bot.channel_post_handler(content_types=['text', 'photo', 'video', 'audio', 'voice', 'video_note', 'document', 'sticker', 'animation', 'poll'])
def handle_channel_post(message):
    global PROCESSED_MEDIA_GROUPS
    
    try:
        # Проверяем, что это пост из нужного канала
        if message.chat.id == CHANNEL_ID:
            # Очищаем старые медиа-группы
            now = time.time()
            PROCESSED_MEDIA_GROUPS = {k: v for k, v in PROCESSED_MEDIA_GROUPS.items() if now - v < MEDIA_GROUP_TIMEOUT}
            
            # Проверяем, является ли это частью медиа-группы
            if message.media_group_id:
                # Если уже обработали эту медиа-группу, пропускаем
                if message.media_group_id in PROCESSED_MEDIA_GROUPS:
                    print(f"⏭ Пропуск дубликата медиа-группы {message.media_group_id}")
                    return
                
                # Отмечаем медиа-группу как обработанную
                PROCESSED_MEDIA_GROUPS[message.media_group_id] = now
                print(f"📢 Новая медиа-группа из канала: {message.media_group_id}")
            else:
                print(f"📢 Новый пост в канале (ID: {message.message_id})")
            
            print(f"   Тип: {message.content_type}")
            
            # Отправляем приветствие в группу комментариев
            time.sleep(1)
            send_welcome_message(DISCUSSION_GROUP_ID, reply_to_message_id=message.message_id)
        else:
            print(f"⏭ Игнорируется пост из чата {message.chat.id}")
    except Exception as e:
        print(f"⚠️ Ошибка при обработке поста: {e}")

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
        
        # Отправляем уведомление как ответ на пост канала (если есть)
        bot.send_message(
            chat_id,
            f"@{username} ⚠️ {reason}\nМут на 1 час.",
            reply_to_message_id=reply_to_message_id
        )
        print(f"🔇 Мут {username} до {mute_until}")
    except Exception as e:
        print(f"❌ Ошибка при выдаче мута: {e}")

# === ФУНКЦИЯ ДЛЯ ПОИСКА ИСХОДНОГО ПОСТА КАНАЛА ===
def find_channel_post_id(message):
    """Находит ID автоматически пересланного поста канала в треде"""
    try:
        # Если это ответ на сообщение, проверяем родительское сообщение
        if message.reply_to_message:
            if message.reply_to_message.is_automatic_forward:
                return message.reply_to_message.message_id
            # Рекурсивно проверяем цепочку ответов
            return find_channel_post_id(message.reply_to_message)
        return None
    except:
        return None

# === АНТИФЛУД И СТОП-СЛОВА ===
@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document', 'audio', 'voice'])
def handle_messages(message):
    global USER_ACTIVITY
    
    # Игнорируем автоматически пересланные посты из канала
    if message.is_automatic_forward:
        return
    
    if message.chat.type not in ['group', 'supergroup']:
        return

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id
    
    # Ищем исходный пост канала для ответа
    channel_post_id = find_channel_post_id(message)

    # антифлуд - теперь сохраняем также message_id
    now = datetime.datetime.now().timestamp()
    USER_ACTIVITY.setdefault(user_id, [])
    
    # Очищаем старые записи
    USER_ACTIVITY[user_id] = [(t, msg_id) for t, msg_id in USER_ACTIVITY[user_id] if now - t < TIME_WINDOW_SECONDS]
    USER_ACTIVITY[user_id].append((now, message.message_id))

    if len(USER_ACTIVITY[user_id]) >= FLOOD_LIMIT:
        # Удаляем ВСЕ сообщения из флуда
        for timestamp, msg_id in USER_ACTIVITY[user_id]:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                print(f"⚠️ Не удалось удалить сообщение {msg_id}: {e}")
        
        apply_mute(
            chat_id,
            user_id,
            username,
            f"Флуд ({FLOOD_LIMIT}+ сообщений за {TIME_WINDOW_SECONDS} секунд)",
            reply_to_message_id=channel_post_id
        )
        USER_ACTIVITY[user_id] = []
        return

    # стоп-слова
    if message.text:
        text = message.text.lower()
        for word in STOP_WORDS:
            if word in text:
                bot.delete_message(chat_id, message.message_id)
                apply_mute(
                    chat_id,
                    user_id,
                    username,
                    f"Стоп-слово: {word}",
                    reply_to_message_id=channel_post_id
                )
                break

# === ЗАПУСК ===
print("🚀 Бот запущен и слушает события...")

# --- Новый запуск с Flask для совместимости с бесплатным Web Service Render ---
# Используем Flask для прослушивания порта, чтобы Render не выдавал ошибку,
# а сам бот запускаем в отдельном потоке (threading), чтобы он работал 24/7.

if 'RENDER' in os.environ:
    # ВАЖНО: Удаляем webhook перед запуском polling
    try:
        bot.remove_webhook()
        print("✅ Webhook удален")
        time.sleep(1)
    except Exception as e:
        print(f"⚠️ Ошибка при удалении webhook: {e}")
    
    # 1. Запуск Polling в отдельном потоке
    polling_thread = threading.Thread(target=lambda: bot.infinity_polling(allowed_updates=['message', 'channel_post']), daemon=True)
    polling_thread.start()

    # 2. Создание заглушки Flask для прослушивания порта 
    app = Flask(__name__)

    @app.route('/')
    def index():
        return 'Telegram bot running (polling mode)'

    @app.route('/health')
    def health():
        return 'OK'

    port = int(os.environ.get('PORT', 5000))
    # Flask запускается в фоновом режиме, чтобы бот мог работать
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=port)

else:
    # Обычный запуск на локальном ПК
    bot.infinity_polling()

# --- ------------------------------------------------------------------- ---
