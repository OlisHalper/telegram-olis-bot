import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import os
import time
import datetime
import logging
from telebot import apihelper 
from flask import Flask, request
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
bot = telebot.TeleBot(TOKEN, threaded=False)

# === ОСНОВНІ ПОСИЛАННЯ ТА ID ===
CHANNEL_USERNAME = "@whoisolis"
# ВАШІ АКТУАЛЬНІ ID
CHANNEL_ID = -1003083438241 
DISCUSSION_GROUP_ID = -1003210182852 
# 1. Твой личный Telegram ID (куда будут приходить идеи)
ADMIN_CHAT_ID = -1003994825567 #идеи чат id

# 2. Ссылка на GIF-благодарность за идею
THANK_YOU_GIF_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExY2VhZXI0eXE5ZTNncHFpZDFwaXJkbXYwZzRxcWo1YTY4eXd3cW14OSZlcD12MV9naWZzX3RyZW5kaW5nJmN0PWc/MDJ9IbxxvDUQM/giphy.gif"

# 3. Списки для защиты от дубликатов (остаются в памяти пока бот запущен)
PROCESSED_TEXT_IDEAS = set()
PROCESSED_FILE_IDEAS = set()

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
    if message.chat.type == 'private':
        # Если пользователь пишет в ЛС боту — показываем меню предложки
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("💡 Надіслати ідею", callback_data="btn_submit_idea"))
        keyboard.row(InlineKeyboardButton("🧾 Rules / Правила чату", url=RULES_LINK))
        
        bot.send_message(
            message.chat.id,
            f"👋 **Привіт, {message.from_user.first_name}!**\n\n"
            f"У цьому боті ти можеш поділитися своєю цікавою ідеєю чи пропозицією для майбутніх відео. "
            f"Всі пропозиції розглядаються особисто автором!\n\n"
            f"Натискай на кнопку нижче, щоб розпочати 👇",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        reply_id = getattr(message.reply_to_message, 'message_id', None)
        send_welcome_message(message.chat.id, reply_to_message_id=reply_id)


# === БЛОК ОБРОБКИ ПРЕДЛОЖКИ (ІНЛАЙН-КНОПКА, ФІЛЬТРАЦІЯ ТА АНТИСПАМ) ===
@bot.callback_query_handler(func=lambda call: call.data == "btn_submit_idea")
def callback_idea(call):
    msg = bot.send_message(
        call.message.chat.id,
        "📝 **Чекаю на твою ідею!**\n\n"
        "Надішли її наступним повідомленням. Будь ласка, дотримуйся правил:\n"
        "✅ Можна надіслати **звичайний текст** або **PDF-файл**.\n"
        "❌ Заборонено надсилати: посилання, фото, відео, аудіо, стікери, гіфки та архіви.",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, save_suggestion)
    bot.answer_callback_query(call.id)

def save_suggestion(message):
    # Скасування, якщо ввели іншу команду
    if message.text and message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ Відправку ідеї скасовано.")
        return

    is_valid = False
    error_reason = ""

    # Перевірка на заборонені типи (стікери та гіфки)
    if message.content_type in ['sticker', 'animation']:
        bot.send_message(message.chat.id, "❌ **Помилка:** Надсилати стікери та гіфки в предложку заборонено! Будь ласка, надішли чистий текст або PDF.")
        return

    # Перевірка на тип контенту
    if message.content_type == 'text':
        normalized_text = message.text.strip().lower()
        
        # Перевірка на дублікат тексту
        if normalized_text in PROCESSED_TEXT_IDEAS:
            bot.send_message(message.chat.id, "❌ **Помилка:** Ця ідея вже була надіслана раніше! Будь ласка, не дублюй одне й те саме повідомлення.")
            return

        # Перевірка на наявність посилань через сутності Telegram API
        has_link = False
        if message.entities:
            for entity in message.entities:
                if entity.type in ['url', 'text_link']:
                    has_link = True
                    break
        
        if "http://" in normalized_text or "https://" in normalized_text or "t.me/" in normalized_text:
            has_link = True

        if has_link:
            error_reason = "❌ **Помилка:** Надсилати посилання (лінки) в предложку поки неможливо! Надішли чистий текст або PDF-файл."
        else:
            is_valid = True
            PROCESSED_TEXT_IDEAS.add(normalized_text)

    elif message.content_type == 'document':
        if message.document.file_name.lower().endswith('.pdf') or message.document.mime_type == 'application/pdf':
            # Перевірка на дублікат файлу
            if message.document.file_unique_id in PROCESSED_FILE_IDEAS:
                bot.send_message(message.chat.id, "❌ **Помилка:** Цей файл уже був надісланий раніше! Будь ласка, не надсилай дублікати.")
                return
            
            is_valid = True
            PROCESSED_FILE_IDEAS.add(message.document.file_unique_id)
        else:
            error_reason = "❌ **Помилка:** Цей формат файлу заборонений. Можна надсилати тільки текст або файли у форматі PDF."
    else:
        error_reason = "❌ **Помилка:** Надсилати фото, відео, аудіо, стікери, гіфки або архіви заборонено. Я приймаю тільки текст та PDF."

    if not is_valid:
        bot.send_message(message.chat.id, error_reason, parse_mode="Markdown")
        return

    # Збір інформації про автора
    user_username = f"@{message.from_user.username}" if message.from_user.username else "Немає юзернейму"
    user_info = f"👤 Від: {message.from_user.first_name} ({user_username}) | ID: `{message.from_user.id}`"

    try:
        if message.content_type == 'text':
            idea_text = (
                f"💡 **Нова ідея через бота!**\n\n"
                f"{message.text}\n\n"
                f"{user_info}\n\n"
                f"#предложка"
            )
            bot.send_message(ADMIN_CHAT_ID, idea_text, parse_mode="Markdown")
        
        elif message.content_type == 'document':
            caption_text = (
                f"💡 **Нова ідея (PDF-файл) через бота!**\n\n"
                f"📁 Файл: {message.document.file_name}\n\n"
                f"{user_info}\n\n"
                f"#предложка"
            )
            bot.send_document(ADMIN_CHAT_ID, message.document.file_id, caption=caption_text, parse_mode="Markdown")

        # Відповідь користувачу з подякою та GIF
        thank_you_caption = (
            "🥰 **Дякую! Твою ідею успішно відправлено автору.**\n\n"
            "Обов'язково чекай на згадку свого нікнейму у відео, якщо ідея сподобається і буде взята в роботу! 🎬🐳"
        )
        bot.send_animation(
            chat_id=message.chat.id,
            animation=THANK_YOU_GIF_URL,
            caption=thank_you_caption,
            parse_mode="Markdown"
        )
        logging.info(f"📩 Отримано нову ідею від {user_username}")

    except Exception as e:
        logging.error(f"❌ Не вдалося надіслати ідею адміну: {e}")
        bot.send_message(message.chat.id, "❌ Сталася помилка при відправці ідеї на сервер. Спробуй пізніше.")


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
            
# === ЗАПУСК ЧЕРЕЗ ВЕБХУКИ (ІДЕАЛЬНО ДЛЯ RENDER ТА GUNICORN) ===

app = Flask(__name__)

WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-olis-bot.onrender.com")
WEBHOOK_URL = f"{WEBHOOK_HOST}/{TOKEN}"

# Список обновлений, которые бот должен слушать (для модерации чатов и предложки)
ALLOWED_UPDATES = ['message', 'channel_post', 'my_chat_member', 'chat_member', 'callback_query']

try:
    logging.info("🧹 Видаляємо старі сесії пуллінгу та встановлюємо новий Webhook...")
    bot.remove_webhook()
    time.sleep(1)
    
    # Передаем список ALLOWED_UPDATES, чтобы Telegram присылал ВСЕ события
    bot.set_webhook(url=WEBHOOK_URL, allowed_updates=ALLOWED_UPDATES)
    logging.info(f"✅ Webhook успішно встановлено на адресу: {WEBHOOK_URL}")
except Exception as e:
    logging.error(f"❌ Помилка при встановленні Webhook: {e}")

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        
        # Теперь это выполнится строго до того, как Flask отдаст 200 OK
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Forbidden', 403

@app.route('/')
@app.route('/health')
def health():
    return 'Bot is running via Webhooks!', 200

if __name__ == '__main__':
    logging.info("🤖 Локальний запуск: вимикаємо вебхук та запускаємо стандартний Polling...")
    bot.remove_webhook()
    bot.infinity_polling(allowed_updates=ALLOWED_UPDATES)
