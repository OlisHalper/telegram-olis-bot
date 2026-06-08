import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import os
import time
import datetime
import logging
from telebot import apihelper 
from flask import Flask
import threading

# === НАЛАШТУВАННЯ ЛОГУВАННЯ ===
# Налаштовуємо логування, щоб бачити, що відбувається в консолі
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === КОНФІГУРАЦІЯ БОТА ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.error("❌ BOT_TOKEN не знайдено. Встановіть його в змінні оточення!")
    # Виходимо, якщо токен не знайдено
    # exit(1) 

# Ініціалізація бота
bot = telebot.TeleBot(TOKEN)

# === ОСНОВНІ ПОСИЛАННЯ ТА ID ===
CHANNEL_USERNAME = "@whoisolis"
# ВАШІ АКТУАЛЬНІ ID
CHANNEL_ID = -1003083438241 
DISCUSSION_GROUP_ID = -1003210182852 

GIF_URL = "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExY3Q0ZGl1anh6Z3NuOWR2azF5OTlsc2w3ajBuN2ZobWgybGR2c2VybCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/QgCdJJ8yTiVpcSNNQI/giphy.gif"
CHANNEL_LINK = "https://www.youtube.com/@thisolis"
INST_LINK = "https://www.instagram.com/whoisolis/"
RULES_LINK = "https://olishalper.github.io/olis-chat-rules/"

# === МОДЕРАЦІЯ ===
STOP_WORDS = [
    "тероризм",
    "зароби",
    "швидкий дохід",
    "крипта",
    "злив",
    "продаю",
    "куплю",

    # Війни / Екстремізм
    "геноцид",
    "фашизм",
    "нацизм",
    "екстремізм",
    "терор",
    "путін",
    "русня",
    "хохли",
    "хохол",
    "підор",
    "зеля",
    "зеленський",

    # Заборонений контент (Педофілія, Зоофілія)
    "педофілія",
    "педофіл",
    "зоофілія",
    "нсфл", # NSFW/NSFL в українському сленгу
    "дитяче порно",
    "порнографія з тваринами",

    # Дискримінація (Расизм, Сексизм, Гомофобія)
    "підораси",
    "педик",
    "здохни",
    "лесбуха",
    "лесбухи",
    "лезбуха",
    "лезбухи",
    "націоналізм",
    "ксенофобія",
    
    # Додайте сюди інші слова та фрази (наприклад, нецензурна лексика, екстремізм і т.д.)

    
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

    # Додайте сюди інші слова та фрази (наприклад, нецензурна лексика, екстремізм і т.д.)
]

MUTE_DURATION_SECONDS = 3600 # 1 година
FLOOD_LIMIT = 10
TIME_WINDOW_SECONDS = 10
USER_ACTIVITY = {} # {user_id: [(timestamp, message_id), ...]}

# === ВІДСТЕЖЕННЯ МЕДІА-ГРУП для усунення дублювання ===
# Словник для відстеження вже оброблених медіа-груп (альбомів)
PROCESSED_MEDIA_GROUPS = {} # {media_group_id: timestamp}
MEDIA_GROUP_TIMEOUT = 10 # Час, протягом якого повідомлення вважаються частиною групи (в секундах)

# === КНОПКИ ===
def get_buttons():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("🧾 Правила", url=RULES_LINK))
    return keyboard

# === ФУНКЦІЯ ВІДПРАВКИ ПРИВІТАННЯ З ПОВТОРНИМИ СПРОБАМИ ===
def send_welcome_message(chat_id, reply_to_message_id=None):
    """Відправляє привітання, намагаючись повторно, щоб уникнути помилки 'message to be replied not found'."""
    caption = (
        "👋 Привіт, ти потрапив у коментарі. Внизу цікаві посилання та правила поведінки (будь ласка, почитай їх)🐳\n\n"
        "📸 Мій <a href='{inst}'>инстаграм</a>\n"
        "🔴 Мій <a href='{yt}'>ютуб</a>\n\n"
        "Написавши коментар, ти погоджуєшся з "
        "<a href='{rules}'>правилами</a> чату 🐳"
    ).format(inst=INST_LINK, yt=CHANNEL_LINK, rules=RULES_LINK)

    max_retries = 3
    delay = 1.0 # Початкова затримка

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
            logging.info(f"✅ Привітання відправлено (спроба {attempt+1}) у відповідь на ID: {reply_to_message_id}")
            return # Успіх
        
        except apihelper.ApiTelegramException as e:
            error_message = str(e)
            
            # Обробка частої помилки (повідомлення ще не доступне в Telegram API)
            if attempt < max_retries - 1 and "Bad Request: message to be replied not found" in error_message:
                logging.warning(f"⚠️ Помилка 400: Повідомлення для відповіді {reply_to_message_id} не знайдено. Повтор через {delay:.1f} сек. ({attempt+1}/{max_retries})")
                time.sleep(delay)
                delay *= 1.5 
                continue
            
            # У разі інших помилок API, пробуємо відправити просто текст
            logging.warning(f"⚠️ Помилка відправки GIF-привітання (спроба {attempt+1}): {e}. Відправка текстової версії.")
            
            try:
                bot.send_message(
                    chat_id, 
                    caption, 
                    parse_mode="HTML", 
                    reply_markup=get_buttons(),
                    reply_to_message_id=reply_to_message_id
                )
                logging.info(f"✅ Привітання (текст) відправлено.")
                return 
            except Exception as e_text:
                logging.error(f"❌ Критична помилка: не вдалося відправити навіть текстове привітання: {e_text}", exc_info=True)
                return 

        except Exception as e:
            logging.error(f"❌ Невідома помилка при відправці привітання: {e}", exc_info=True)
            return

    logging.error(f"❌ Не вдалося відправити привітання після {max_retries} спроб.")


# === КОМАНДА /start ===
@bot.message_handler(commands=['start'])
def send_rules(message):
    reply_id = getattr(message.reply_to_message, 'message_id', None)
    send_welcome_message(message.chat.id, reply_to_message_id=reply_id)


# === ОБРОБКА АВТОМАТИЧНО ПЕРЕСЛАНИХ ДОПИСІВ (ТРИГЕР ПРИВІТАННЯ) ===
@bot.message_handler(
    func=lambda m: m.chat.id == DISCUSSION_GROUP_ID and m.is_automatic_forward, 
    content_types=['text', 'photo', 'video', 'audio', 'voice', 'video_note', 'document', 'sticker', 'animation', 'poll']
)
def handle_forwarded_channel_post(message):
    global PROCESSED_MEDIA_GROUPS
    
    logging.info(f"👀 [ТРИГЕР] Отримано автоматичний форвард. ID: {message.message_id}. Media Group ID: {message.media_group_id}")
    
    try:
        # --- БЛОК АНТИ-ДУБЛІКАТ ДЛЯ МЕДІА-ГРУП ---
        if message.media_group_id:
            now = time.time()
            
            # 1. Очищення старих записів
            PROCESSED_MEDIA_GROUPS = {k: v for k, v in PROCESSED_MEDIA_GROUPS.items() if now - v < MEDIA_GROUP_TIMEOUT}
            
            # 2. Перевірка, чи була ця медіа-група вже оброблена
            if message.media_group_id in PROCESSED_MEDIA_GROUPS:
                logging.info(f"⏭ [ТРИГЕР] Пропуск дубліката медіа-групи {message.media_group_id}. Привітання вже відправлено.")
                return # Виходимо, щоб уникнути дублювання
            
            # 3. Позначення групи як обробленої
            PROCESSED_MEDIA_GROUPS[message.media_group_id] = now
            logging.info(f"📢 [ТРИГГЕР] Новий допис (медіа-група {message.media_group_id}). Запуск привітання...")
            
        else:
            # Поодинокий допис (текст, одне фото, одне відео і т.д.)
            logging.info(f"📢 [ТРИГЕР] Новий поодинокий допис. Запуск привітання...")

        # Відправляємо привітання, відповідаючи на сам пересланий допис із каналу
        send_welcome_message(DISCUSSION_GROUP_ID, reply_to_message_id=message.message_id)
        
    except Exception as e:
        logging.error(f"⚠️ Помилка при обробці пересланого допису: {e}", exc_info=True)


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
            f"@{username} ⚠️ {reason}\nМут на 1 годину.",
            reply_to_message_id=reply_to_message_id
        )
        logging.warning(f"🔇 Мут {username} до {mute_until}. Причина: {reason}")
    except Exception as e:
        logging.error(f"❌ Помилка при видачі муту. Перевірте права бота: {e}", exc_info=True)

# === ФУНКЦІЯ ДЛЯ ПОШУКУ ВИХІДНОГО ДОПИСУ КАНАЛУ ===
def find_channel_post_id(message):
    """Знаходить ID автоматично пересланого допису каналу, на який потрібно відповісти в треді"""
    try:
        if message.reply_to_message:
            # Перевіряємо, чи є батьківське повідомлення автоматичним форвардом
            if getattr(message.reply_to_message, 'is_automatic_forward', False):
                return message.reply_to_message.message_id
            # Рекурсивно перевіряємо ланцюжок відповідей
            return find_channel_post_id(message.reply_to_message)
        return None
    except:
        return None

# === АНТИФЛУД І СТОП-СЛОВА (МОДЕРАЦІЯ КОМЕНТАРІВ) ===
@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document', 'audio', 'voice', 'animation'])
def handle_messages(message):
    global USER_ACTIVITY
    
    # 1. Ігноруємо автоматично переслані дописи
    if getattr(message, 'is_automatic_forward', False):
        return
    
    # 2. Обробляємо тільки в цільовій групі коментарів
    if message.chat.id != DISCUSSION_GROUP_ID:
        return
        
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id
    
    logging.info(f"👀 [МОДЕРАЦІЯ] Отримано коментар від @{username}. Тип: {message.content_type}")
    
    # Шукаємо вихідний допис каналу для відповіді-повідомлення про мут
    channel_post_id = find_channel_post_id(message)

    # --- Антифлуд ---
    now = datetime.datetime.now().timestamp()
    USER_ACTIVITY.setdefault(user_id, [])
    
    # Очищаємо старі записи
    USER_ACTIVITY[user_id] = [(t, msg_id) for t, msg_id in USER_ACTIVITY[user_id] if now - t < TIME_WINDOW_SECONDS]
    USER_ACTIVITY[user_id].append((now, message.message_id))

    if len(USER_ACTIVITY[user_id]) >= FLOOD_LIMIT:
        logging.warning(f"🚨 [МОДЕРАЦІЯ] Виявлено флуд від @{username}. Видача муту.")
        
        # Видаляємо ВСІ повідомлення з флуду
        for timestamp, msg_id in USER_ACTIVITY[user_id]:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                logging.error(f"⚠️ Не вдалося видалити повідомлення {msg_id} під час флуду: {e}")
            
        apply_mute(
            chat_id, 
            user_id, 
            username, 
            f"Флуд ({FLOOD_LIMIT}+ повідомлень за {TIME_WINDOW_SECONDS} секунд)",
            reply_to_message_id=channel_post_id
        )
        USER_ACTIVITY[user_id] = [] # Очищаємо активність після муту
        return

    # --- Стоп-слова ---
    if message.text:
        text = message.text.lower()
        for word in STOP_WORDS:
            # Використовуємо пошук слова в тексті
            if word in text:
                logging.warning(f"🚨 [МОДЕРАЦІЯ] Виявлено стоп-слово '{word}' від @{username}. Видача муту.")
                
                try:
                    bot.delete_message(chat_id, message.message_id)
                except Exception as e:
                    logging.error(f"⚠️ Не вдалося видалити повідомлення зі стоп-словом: {e}")
                
                apply_mute(
                    chat_id, 
                    user_id, 
                    username, 
                    f"Стоп-слово: {word}",
                    reply_to_message_id=channel_post_id
                )
                return
    
    logging.info(f"✅ [МОДЕРАЦІЯ] Коментар від @{username} пройшов перевірку.")
            
# === ЗАПУСК (АДАПТАЦІЯ ДЛЯ GUNICORN/FLASK) ===

# Ініціалізація Flask додатка (необхідно для Gunicorn)
app = Flask(__name__)

# Функція, яка запускатиме Polling у фоновому потоці
def run_polling():
    # Ця функція виконується у фоновому потоці
    logging.info("🧹 Спроба видалення старого Webhook...")
    try:
        bot.remove_webhook() 
        logging.info("✅ Webhook видалено успішно")
        time.sleep(1)
    except Exception as e:
        logging.warning(f"⚠️ Помилка при видаленні webhook (можливо, його не було): {e}")

    logging.info("🚀 [КРИТИЧНИЙ ЛОГ] Бот готовий до запуску Infinity Polling...")
    try:
        # Запуск Polling. Вказуємо всі типы оновлень для надійності.
        bot.infinity_polling(allowed_updates=['message', 'channel_post', 'my_chat_member', 'chat_member'])
    except Exception as e:
        logging.critical(f"❌ Критична помилка Polling: {e}", exc_info=True)


# Маршрути Flask (необхідні для health check хостингу)
@app.route('/')
def index():
    return 'Telegram bot running (polling mode)', 200

@app.route('/health')
def health():
    return 'OK', 200

# Запуск бота в окремому потоці
if __name__ == '__main__':
    # При локальному запуску (python bot.py)
    run_polling()
else:
    # При запуску через Gunicorn (gunicorn bot:app)
    # Gunicorn імпортує 'app', а ми запускаємо Polling у фоновому потоці.
    logging.info("☁️ Запуск через Gunicorn. Polling буде запущено в окремому потоці.")
    polling_thread = threading.Thread(target=run_polling, daemon=True)
    polling_thread.start()
