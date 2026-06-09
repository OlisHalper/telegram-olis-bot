import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import os
import time
import datetime
import logging
from telebot import apihelper 
from flask import Flask, request
import threading
import google.generativeai as genai

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

# === ДОБАВЛЯЕМ НА ТВОЙ СКРИНШОТ КНОПКУ МЕНЮ ===
bot.set_my_commands([
    telebot.types.BotCommand("start", "🚀 Запустити бота / Головне меню")
])

# Твой ключ
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    logging.error("❌ GEMINI_API_KEY не знайдено! Модерація Gemini не працюватиме. Встановіть змінну середовища GEMINI_API_KEY на render.com")
else:
    logging.info("✅ GEMINI_API_KEY знайдено, Gemini модерація активна.")
genai.configure(api_key=API_KEY)

# === НАЛАШТУВАННЯ БЕЗПЕКИ (ЦЕ ВАЖЛИВО!) ===
# Використовуємо enum-формат для сумісності з новими версіями google-generativeai (1.x+)
# Ми кажемо Google: "Не блокуй запити, навіть якщо там є мат або агресія"
try:
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    logging.info("✅ Gemini safety_settings: використовується новий enum-формат (google-generativeai 1.x+)")
except ImportError:
    # Старий формат для версій < 1.0
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    logging.info("✅ Gemini safety_settings: використовується старий рядковий формат (google-generativeai < 1.0)")

# Ініціалізація моделі ОБОВ'ЯЗКОВО з safety_settings
model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)

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
BOT_LINK = "https://t.me/olisos_bot"

from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# Постоянное нижнее меню (вместо ручного ввода /start)
def get_main_menu_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True)
    markup.add(KeyboardButton("💡 Надіслати ідею"))
    markup.add(KeyboardButton("🧾 Правила чату"))
    return markup

# Клавиатура с кнопкой отмены (появляется только во время ввода идеи)
def get_cancel_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("❌ Скасувати"))
    return markup

# === МОДЕРАЦІЯ ===
STOP_WORDS = [
    # РУССКИЙ / УКРАИНСКИЙ / ENGLISH
    # Спам / Скам
    "переходи по ссылке", "переходь за посиланням", "click the link",
    "заработай", "зароби", "earn money",
    "быстрый доход", "швидкий дохід", "quick income",
    "крипта", "крипта", "crypto",
    "слив", "злив", "leak",
    "продаю", "продаю", "selling",
    "ставки", "ставки", "betting",
    "куплю", "куплю", "buying",
    "ссылка в профиле", "посилання в профілі", "link in bio",
    "приватка", "приватка", "private channel",
    "приватный канал", "приватний канал", "private channel",
    "успей вступить", "встигни вступити", "join now",
    "сливы", "зливи", "leaks",
    "заработок", "заробіток", "earnings",
    "ищу воркеров", "шукаю воркерів", "looking for workers",
    "схема заработка", "схема заробітку", "money scheme",
    "легкие деньги", "легкі гроші", "easy money",
    "раскрутка счета", "розкрутка рахунку", "account boosting",
    "трейдинг", "трейдинг", "trading",
    "арбитраж", "арбітраж", "arbitrage",
    "капер", "капер", "capper",
    "казино", "казино", "casino",
    "слоты", "слоти", "slots",
    "букмекерская", "букмекерська", "bookmaker",
    "премиум бесплатно", "преміум безкоштовно", "free premium",
    "дарю прем", "дарю прем", "giving away premium",
    "подтвердите аккаунт", "підтвердіть акаунт", "verify account",
    "аккаунт заблокирован", "акаунт заблоковано", "account blocked",
    "введите пароль", "введіть пароль", "enter password",
    "пройдите верификацию", "пройдіть верифікацію", "verify identity",
    "premium бесплатно", "premium безкоштовно", "free premium",
    "дарю премиум", "дарю преміум", "gift premium",
    "раздача прем", "роздача прем", "premium giveaway",
    "раздача премиум", "роздача преміум", "premium giveaway",
    "раздача премиума", "роздача преміуму", "premium giveaway",
    "раздача премиумов", "роздача преміумів", "premium giveaways",
    "розыгрыш", "розіграш", "giveaway",
    "заберите приз", "заберіть приз", "claim prize",
    "акция телеграм", "акція телеграм", "telegram promo",

    # Войны / Экстремизм / Политика (UA/RU/EN)
    "суицид", "суїцид", "suicide",
    "самоубийство", "самогубство", "suicide",
    "повешался", "повісився", "hanged himself",
    "повесился", "повісився", "hanged himself",
    "вскрылся", "вскрывся", "slit wrists",
    "вскрыться", "вскритися", "to slit wrists",
    "вскроюсь", "вскриюся", "i will slit my wrists",
    "вскройся", "вскрийся", "slit your wrists",
    "повешайся", "повішайся", "hang yourself",
    "повешусь", "повішуся", "i will hang myself",
    "повесься", "повісься", "hang yourself",
    "прирезать", "прирізати", "to stab",
    "взорвать", "підірвати", "to blow up",
    "купить ствол", "купити ствол", "buy a gun",
    "купить пистолет", "купити пістолет", "buy a pistol",
    "купить нож", "купити ніж", "buy a knife",
    "трупы", "трупи", "corpses",
    "расчлененка", "розчленування", "dismemberment",
    "пытки", "тортури", "torture",
    "избиение", "побиття", "beating",
    "террор", "терор", "terror",
    "путин", "путін", "putin",
    "русня", "русня", "rusnya",
    "хохлы", "хохли", "khokhols",
    "хохол", "хохол", "khokhol",
    "зеля", "зеля", "zelensky",

    # Наркотики / Запрещенка
    "нсфл", "nsfl", "nsfl",
    "детское порно", "дитяче порно", "child porn",
    "порнография с животными", "зоофілія", "bestiality",
    "кладка", "закладка", "drug stash",
    "шоп", "шоп", "shop",
    "меф", "меф", "mephedrone",
    "бошки", "бошки", "weed",
    "гаш", "гаш", "hash",
    "амф", "амф", "amphetamine",
    "mdma", "mdma", "mdma",
    "мдма", "мдма", "mdma",
    "экстази", "екстазі", "ecstasy",
    "кокс", "кокс", "coke",
    "героин", "героїн", "heroin",
    "гашиш", "гашиш", "hashish",
    "hydra", "hydra", "hydra",
    "гидра", "гідра", "hydra",

    # Дискриминация и оскорбления
    "пидоросня", "підоросня", "faggots",
    "пидорасня", "підорасня", "faggots",
    "сдохни", "здохни", "die",
    "лесбуха", "лесбуха", "lesbian",
    "лесбухи", "лесбухи", "lesbians",
    "лезбуха", "лезбуха", "lesbian",
    "лезбухи", "лезбухи", "lesbians",
    "нига", "ніга", "nigger",
    "негр", "негр", "nigger",
    "черножопый", "чорножопий", "niger",
    "чорножопий", "чорножопий", "niga",
    "черножопый", "чорножопий", "nigga",
    "инцел", "інцел", "incel",
    "черномазый", "чорномазий", "nigger",
    "даун", "даун", "down syndrome",
    "аутист", "аутист", "autist",
    "урод", "виродок", "freak",
    "тварь", "потвора", "scum",
    "мразь", "мразь", "scum",
    "гнида", "гнида", "nit",
    "скотина", "скотина", "beast",
    "ничтожество", "нікчема", "nothingness",
    "выродок", "виродок", "bastard",
    "недоносок", "недоносок", "runt",
    "падаль", "падаль", "carrion",
    "шлюха", "шлюха", "whore",
    "шалава", "шалава", "slut",

    # Контент 18+
    "порно", "порно", "porn",
    "порнуха", "порнуха", "porn",
    "porno", "porno", "porno",
    "нюдсы", "нюдси", "nudes",
    "слив фото", "злив фото", "leak photo",
    "сливы интим", "зливи інтим", "intimate leaks",
    "сливы интимок", "зливи інтимок", "intimate leaks",
    "слив интимок", "злив інтимок", "intimate leak",
    "слив интим", "злив інтим", "intimate leak",
    "вирт", "вірт", "cybersex"

    # Додайте сюди інші слова та фрази (наприклад, нецензурна лексика, екстремізм і т.д.)

]

MUTE_DURATION_SECONDS = 900 # 15 хвилин
FLOOD_LIMIT = 10
TIME_WINDOW_SECONDS = 10
USER_ACTIVITY = {} # {user_id: [(timestamp, message_id), ...]}

# === ВІДСТЕЖЕННЯ МЕДІА-ГРУП для усунення дублювання ===
# Словник для відстеження вже оброблених media-груп (альбомів)
PROCESSED_MEDIA_GROUPS = {} # {media_group_id: timestamp}
MEDIA_GROUP_TIMEOUT = 10 # Час, протягом якого повідомлення вважаються частиною групи (в секундах)

def check_with_gemini(text=None, photo_bytes=None):
    try:
        # Захист: якщо нічого перевіряти, виходимо
        if not text and not photo_bytes:
            return False

        contents = []
        prompt = (
            "Ти — модератор чату. Твоє завдання: перевірити вхідний контент на наявність образ, "
            "булінгу, ненормативної лексики або заборонених тем.\n"
            "Відповідай ТІЛЬКИ ОДНИМ СЛОВОМ: 'YES' (якщо є порушення) або 'NO' (якщо все добре)."
        )
        contents.append(prompt)
        
        if text:
            contents.append(f"Контент: '{text}'")
            
        if photo_bytes:
            contents.append({'mime_type': 'image/jpeg', 'data': photo_bytes})
            
        # Запит до моделі
        response = model.generate_content(contents)
        
        # Логування результату, щоб бачити, що саме відповів AI
        if response.text:
            result = response.text.strip().upper()
            logging.info(f"🤖 [GEMINI DEBUG] Модель відповіла: {result}")
            return "YES" in result
        else:
            logging.warning("🤖 [GEMINI] Модель повернула пусту відповідь.")
            return False
            
    except Exception as e:
        # Тут ми бачимо, чому конкретно впав запит
        logging.error(f"❌ [GEMINI ERROR] Помилка запиту: {e}")
        return False

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
        "💡 <a href='{bot}'>Тут</a> ти можеш запропонувати мне свою ідею для відео\n\n"
        "Написавши коментар, ти погоджуєшся з "
        "<a href='{rules}'>правилами</a> чату 🐳"
    ).format(inst=INST_LINK, yt=CHANNEL_LINK, rules=RULES_LINK, bot=BOT_LINK)

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


def process_idea_step(message):
    try:
        # 1. ОБРАБОТКА КНОПКИ «СКАСУВАТИ» ИЛИ ЛЮБОЙ КОМАНДЫ (НАПРИМЕР, /start)
        if message.content_type == 'text':
            if message.text == "❌ Скасувати" or message.text.startswith('/'):
                bot.send_message(
                    message.chat.id, 
                    "❌ Відправку ідеї скасовано. Повертаємось до головного меню. 👇", 
                    reply_markup=get_main_menu_keyboard()
                )
                return

        # 2. СТРОГАЯ ФИЛЬТРАЦИЯ ПО ТИПУ (Только ТЕКСТ или PDF)
        is_valid = False
        idea_text = ""
        normalized_text = "" # Переменная для очищенного текста

        if message.content_type == 'text':
            is_valid = True
            idea_text = message.text
            
            # --- УМНАЯ ОЧИСТКА ТЕКСТА ОТ СМАЙЛОВ И ЗНАКОВ ПРЕПИНАНИЯ ---
            import re
            normalized_text = re.sub(r'[^a-zA-Z0-9а-яА-ЯёЁіІїЇєЄґҐ]', '', idea_text).lower()
            
            # Если после очистки ничего не осталось — значит, там были только смайлы/точки
            if not normalized_text:
                bot.send_message(
                    message.chat.id, 
                    "⚠️ **Ідея не може складатися лише зі смайликів або розділових знаків!**\n\nБудь ласка, напиши свою пропозицію текстом.", 
                    parse_mode="Markdown",
                    reply_markup=get_cancel_keyboard()
                )
                bot.register_next_step_handler(message, process_idea_step)
                return
            
        elif message.content_type == 'document':
            file_name = message.document.file_name.lower() if message.document.file_name else ""
            mime_type = message.document.mime_type if message.document.mime_type else ""
            
            if file_name.endswith('.pdf') or mime_type == 'application/pdf':
                is_valid = True
                idea_text = message.caption if message.caption else "Ідея знаходиться всередині PDF-файлу."

        # Если прислали фото, стикер или аудио — ругаемся и ждем заново
        if not is_valid:
            bot.send_message(
                message.chat.id, 
                "❌ **Недопустимий формат файлу!**\n\n"
                "Бот приймає виключно **звичайний текст** або **PDF-документи**.\n"
                "Будь ласка, надішли ідею у правильному форматі або натисни «❌ Скасувати».", 
                parse_mode="Markdown",
                reply_markup=get_cancel_keyboard()
            )
            bot.register_next_step_handler(message, process_idea_step)
            return

    # === 2.5 ПРОВЕРКА НА ДУБЛИКАТЫ И СПАМ ===
        if message.content_type == 'text':
            if normalized_text in PROCESSED_TEXT_IDEAS: # Проверяем именно очищенный текст
                bot.send_message(
                    message.chat.id, 
                    "⚠️ **Ця ідея вже була надіслана раніше!**\n\nБудь ласка, надішли іншу пропозицію або натисни «❌ Скасувати».", 
                    parse_mode="Markdown",
                    reply_markup=get_cancel_keyboard() # Возвращаем кнопку отмены вместо главного меню
                )
                bot.register_next_step_handler(message, process_idea_step) # Заставляем бота снова ждать идею
                return
        elif message.content_type == 'document':
            file_uid = message.document.file_unique_id
            if file_uid in PROCESSED_FILE_IDEAS:
                bot.send_message(
                    message.chat.id, 
                    "⚠️ **Цей файл уже був надісланий раніше!**\n\nБудь ласка, надішли інший файл або натисни «❌ Скасувати».", 
                    parse_mode="Markdown",
                    reply_markup=get_cancel_keyboard() # Возвращаем кнопку отмены
                )
                bot.register_next_step_handler(message, process_idea_step) # Заставляем бота снова ждать идею
                return

        # === 3. ФИЛЬТРАЦИЯ ПО ТРИГГЕР-СЛОВАМ (Сверяемся со STOP_WORDS) ===
        # Находим все стоп-слова, которые есть в тексте пользователя
        triggered_words = [word for word in STOP_WORDS if word.lower() in idea_text.lower()]
        
        if triggered_words:
            # Красиво оформляем найденные слова в кавычки через запятую
            found_words_str = ", ".join(f'"{word}"' for word in triggered_words)
            
            bot.send_message(
                message.chat.id, 
                f"⚠️ **У твоїй ідеї знайдено заборонене слово:** {found_words_str}\n\n"
                f"Будь ласка, перефразуй свою пропозицію без этого слова та надішли знову:", 
                parse_mode="Markdown",
                reply_markup=get_cancel_keyboard()
            )
            bot.register_next_step_handler(message, process_idea_step)
            return

        # --- ДОБАВЛЯЕМ ПРОВЕРКУ GEMINI ДЛЯ ПРЕДЛОЖКИ ---
        if idea_text and len(idea_text) > 3:
            if check_with_gemini(idea_text):
                bot.send_message(
                    message.chat.id, 
                    "⚠️ **Твою ідею відхилено системою модерації!**\n\nБудь ласка, пиши культурно та без образ.", 
                    parse_mode="Markdown",
                    reply_markup=get_main_menu_keyboard()
                )
                return

        
        # === 4. ПРЕСЫЛКА В ЧАТ С ВЫДЕЛЕНИЕМ ЖИРНЫМ ===
        user_username = f"@{message.from_user.username}" if message.from_user.username else "Немає юзернейму"
        user_info = f"👤 Від: {message.from_user.first_name} ({user_username}) | ID: `{message.from_user.id}`"
        
        if message.content_type == 'text':
            formatted_msg = f"💡 **Нова ідея через бота!**\n\n**{idea_text}**\n\n{user_info}\n\n#предложка"
            bot.send_message(ADMIN_CHAT_ID, formatted_msg, parse_mode="Markdown")
        elif message.content_type == 'document':
            caption_text = f"💡 **Нова ідея (PDF-файл) через бота!**\n\n📁 Файл: {message.document.file_name}\n**Опис:** {idea_text}\n\n{user_info}\n\n#предложка"
            bot.send_document(ADMIN_CHAT_ID, message.document.file_id, caption=caption_text, parse_mode="Markdown")

        # === 4.5 СОХРАНЕНИЕ В ПАМЯТЬ ДЛЯ ЗАЩИТЫ ОТ ПОВТОРОВ ===
        if message.content_type == 'text':
            PROCESSED_TEXT_IDEAS.add(normalized_text)
        elif message.content_type == 'document':
            PROCESSED_FILE_IDEAS.add(message.document.file_unique_id)

        # === 5. УСПЕШНЫЙ ФИНАЛ С АНИМАЦИЕЙ БЛАГОДАРНОСТИ И ВОЗВРАТ МЕНЮ ===
        thank_you_caption = (
            "🥰 **Дякую! Твою ідею успешно відправлено автору.**\n\n"
            "Обов'язково чекай на згадку свого нікнейму у відео, якщо ідея сподобається і буде взята в роботу! 🎬🐳"
        )
        bot.send_animation(
            chat_id=message.chat.id,
            animation=THANK_YOU_GIF_URL,
            caption=thank_you_caption,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
        logging.info(f"📩 Отримано нову ідею від {user_username}")

    except Exception as e:
        logging.error(f"Помилка в предложці: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Сталася внутрішня помилка сервера. Спробуй ще раз пізніше.",
            reply_markup=get_main_menu_keyboard()
        )

# Хэндлер, который ловит нажатия кнопок главного меню
@bot.message_handler(func=lambda message: message.text in ["💡 Надіслати ідею", "🧾 Правила чату"] and message.chat.type == 'private')
def handle_main_menu(message):
    if message.text == "🧾 Правила чату":
        bot.send_message(message.chat.id, f"Ознайомитись з правилами можна за посиланням: {RULES_LINK}")
        
    elif message.text == "💡 Надіслати ідею":
        bot.send_message(
            message.chat.id,
            "📝 **Напиши свою ідею в одному повідомленні** (або надішли PDF-документ з описом).\n\n"
            "⚠️ Дозволено тільки текст та PDF файли. Якщо передумав — тисни кнопку «❌ Скасувати» внизу.",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )
        bot.register_next_step_handler(message, process_idea_step)

# === КОМАНДА /start ===
@bot.message_handler(commands=['start'])
def send_rules(message):
    if message.chat.type == 'private':
        bot.send_message(
            message.chat.id,
            f"👋 **Привіт, {message.from_user.first_name}!**\n\n"
            f"У цьому боті ти можеш поділитися своєю цікавою ідеєю чи пропозицією для майбутніх відео. "
            f"Всі пропозиції розглядаються особисто автором!\n\n"
            f"Обирай дію в меню нижче 👇",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard() # <--- Вызываем нижнее меню
        )
    else:
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
            f"@{username} ⚠️ {reason}\nМут на 15 хвилин.",
            reply_to_message_id=reply_to_message_id
        )
        logging.warning(f"🔇 Мут {username} до {mute_until}. Причина: {reason}")
    except Exception as e:
        logging.error(f"❌ Помилка при видачі муту. Перевірте права бота: {e}", exc_info=True)

# === ФУНКЦІЯ ДЛЯ ПОШУКУ ВИХІДНОГО ДОПИСУ КАНАЛУ ===
def find_channel_post_id(message):
    """Знаходит ID автоматично пересланого допису каналу, на який потрібно відповісти в треді"""
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

# === АНТИФЛУД, СТОП-СЛОВА ТА АНТИСПАМ (МОДЕРАЦІЯ КОМЕНТАРІВ) ===
@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document', 'audio', 'voice', 'animation'])
def handle_messages(message):
    global USER_ACTIVITY
    
    # 1. Ігноруємо автоматично переслані дописи та повідомлення від самого каналу
    if getattr(message, 'is_automatic_forward', False) or message.sender_chat is not None:
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

    # --- 3. ПЕРЕВІРКА НА НАЯВНІСТЬ ПОСИЛАНЬ (АНТИСПАМ) ---
    has_link = False
    if message.entities:
        for entity in message.entities:
            if entity.type in ['url', 'text_link']:
                has_link = True
                break
    if message.caption_entities:
        for entity in message.caption_entities:
            if entity.type in ['url', 'text_link']:
                has_link = True
                break

    # Якщо звичайний юзер надіслав посилання — просто видаляємо і зупиняємо обробку
    if has_link:
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception as e:
            logging.error(f"Помилка при видаленні посилання в коментарях: {e}")
        return

    # --- 4. Антифлуд ---
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

    # --- 5. Стоп-слова (перевіряємо і текст, і підпис до фото/файлу) ---
    # ВИПРАВЛЕННЯ: раніше перевірявся тільки message.text, тепер також message.caption
    text_for_stopwords = message.text or message.caption
    if text_for_stopwords:
        text = text_for_stopwords.lower()
        for word in STOP_WORDS:
            # Використовуємо пошук слова в тексті або підписі
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

    # --- 6. Розумна перевірка через Gemini (якщо стоп-слова не спрацювали) ---
    # Створюємо змінну, яка бере або текст повідомлення, або підпис (caption)
    text_to_check = message.text or message.caption
    
    if text_to_check and len(text_to_check) > 3: 
        if check_with_gemini(text_to_check):
            logging.warning(f"🤖 [GEMINI] Виявлено токсичність від @{username}.")
            bot.delete_message(chat_id, message.message_id)
            apply_mute(chat_id, user_id, username, "Прихована агресія (AI-модерація)", reply_to_message_id=channel_post_id)
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
