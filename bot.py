import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
import os
import time
import datetime
import logging
from telebot import apihelper
from flask import Flask, request
import threading
from google import genai
from google.genai import types

# === НАЛАШТУВАННЯ ЛОГУВАННЯ ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === КОНФІГУРАЦІЯ БОТА ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.error("❌ BOT_TOKEN не знайдено. Встановіть його в змінні оточення!")

bot = telebot.TeleBot(TOKEN, threaded=False)

bot.set_my_commands([
    telebot.types.BotCommand("start", "🚀 Запустити бота / Головне меню")
])

# === GEMINI AI ===
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    logging.error("❌ GEMINI_API_KEY не знайдено! Модерація Gemini не працюватиме.")
else:
    logging.info("✅ GEMINI_API_KEY знайдено, Gemini модерація активна.")

gemini_client = genai.Client(api_key=API_KEY)

GEMINI_SAFETY_SETTINGS = [
    types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
    types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
    types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
    types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
]
logging.info("✅ Gemini клієнт ініціалізовано (google-genai)")

# === ОСНОВНІ ПОСИЛАННЯ ТА ID ===
CHANNEL_USERNAME = "@whoisolis"
CHANNEL_ID = -1003083438241
DISCUSSION_GROUP_ID = -1003210182852
ADMIN_CHAT_ID = -1003994825567

THANK_YOU_GIF_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExY2VhZXI0eXE5ZTNncHFpZDFwaXJkbXYwZzRxcWo1YTY4eXd3cW14OSZlcD12MV9naWZzX3RyZW5kaW5nJmN0PWc/MDJ9IbxxvDUQM/giphy.gif"

PROCESSED_TEXT_IDEAS = set()
PROCESSED_FILE_IDEAS = set()

GIF_URL = "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExY3Q0ZGl1anh6Z3NuOWR2azF5OTlsc2w3ajBuN2ZobWgybGR2c2VybCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/QgCdJJ8yTiVpcSNNQI/giphy.gif"
CHANNEL_LINK = "https://www.youtube.com/@thisolis"
INST_LINK = "https://www.instagram.com/whoisolis/"
RULES_LINK = "https://olishalper.github.io/olis-chat-rules/"
BOT_LINK = "https://t.me/olisos_bot"

from telebot.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True)
    markup.add(KeyboardButton("💡 Надіслати ідею"))
    markup.add(KeyboardButton("🧾 Правила чату"))
    return markup

def get_cancel_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("❌ Скасувати"))
    return markup

# === МОДЕРАЦІЯ ===
STOP_WORDS = [
    # Спам / Скам
    "переходи по ссылке", "переходь за посиланням", "click the link",
    "заработай", "зароби", "earn money",
    "быстрый доход", "швидкий дохід", "quick income",
    "крипта", "крипта", "crypto",
    "слив", "злив", "leak",
    "продаю", "selling",
    "ставки", "betting",
    "куплю", "buying",
    "ссылка в профиле", "посилання в профілі", "link in bio",
    "приватка", "private channel",
    "приватный канал", "приватний канал",
    "успей вступить", "встигни вступити", "join now",
    "сливы", "зливи", "leaks",
    "заработок", "заробіток", "earnings",
    "ищу воркеров", "шукаю воркерів", "looking for workers",
    "схема заработка", "схема заробітку", "money scheme",
    "легкие деньги", "легкі гроші", "easy money",
    "раскрутка счета", "розкрутка рахунку", "account boosting",
    "трейдинг", "trading",
    "арбитраж", "арбітраж", "arbitrage",
    "капер", "capper",
    "казино", "casino",
    "слоты", "слоти", "slots",
    "букмекерская", "букмекерська", "bookmaker",
    "премиум бесплатно", "преміум безкоштовно", "free premium",
    "дарю прем", "giving away premium",
    "подтвердите аккаунт", "підтвердіть акаунт", "verify account",
    "аккаунт заблокирован", "акаунт заблоковано", "account blocked",
    "введите пароль", "введіть пароль", "enter password",
    "пройдите верификацию", "пройдіть верифікацію", "verify identity",
    "дарю премиум", "дарю преміум", "gift premium",
    "раздача прем", "роздача прем", "premium giveaway",
    "раздача премиум", "роздача преміум",
    "раздача премиума", "роздача преміуму",
    "раздача премиумов", "роздача преміумів",
    "розыгрыш", "розіграш", "giveaway",
    "заберите приз", "заберіть приз", "claim prize",
    "акция телеграм", "акція телеграм", "telegram promo",
    # Екстремізм / Самопошкодження
    "суицид", "суїцид", "suicide",
    "самоубийство", "самогубство",
    "повешался", "повісився", "hanged himself",
    "повесился",
    "вскрылся", "вскрывся", "slit wrists",
    "вскрыться", "вскритися",
    "вскроюсь", "вскриюся",
    "вскройся", "вскрийся",
    "повешайся", "повішайся", "hang yourself",
    "повешусь", "повішуся",
    "повесься", "повісься",
    "прирезать", "прирізати", "to stab",
    "взорвать", "підірвати", "to blow up",
    "купить ствол", "купити ствол", "buy a gun",
    "купить пистолет", "купити пістолет",
    "купить нож", "купити ніж",
    "трупы", "трупи", "corpses",
    "расчлененка", "розчленування", "dismemberment",
    "пытки", "тортури", "torture",
    "избиение", "побиття", "beating",
    "террор", "терор", "terror",
    "путин", "путін", "putin",
    "русня", "rusnya",
    "хохлы", "хохли", "khokhols",
    "хохол", "khokhol",
    "зеля", "zelensky",
    # Наркотики
    "нсфл", "nsfl",
    "детское порно", "дитяче порно", "child porn",
    "порнография с животными", "зоофілія", "bestiality",
    "кладка", "закладка", "drug stash",
    "меф", "mephedrone",
    "бошки", "weed",
    "гаш", "hash",
    "амф", "amphetamine",
    "mdma", "мдма",
    "экстази", "екстазі", "ecstasy",
    "кокс", "coke",
    "героин", "героїн", "heroin",
    "гашиш", "hashish",
    "hydra", "гидра", "гідра",
    # Дискримінація та образи
    "пидоросня", "підоросня",
    "пидорасня", "підорасня",
    "сдохни", "здохни",
    "лесбуха", "лезбуха",
    "нига", "ніга", "nigger",
    "негр",
    "черножопый", "чорножопий",
    "черномазый", "чорномазий",
    "инцел", "інцел", "incel",
    "даун",
    "аутист",
    "урод", "виродок",
    "тварь", "потвора",
    "мразь",
    "гнида",
    "скотина",
    "ничтожество", "нікчема",
    "выродок",
    "недоносок",
    "падаль",
    "шлюха", "whore",
    "шалава", "slut",
    # Контент 18+
    "порно", "porn", "porno",
    "порнуха",
    "нюдсы", "нюдси", "nudes",
    "слив фото", "злив фото", "leak photo",
    "сливы интим", "зливи інтим",
    "сливы интимок", "зливи інтимок",
    "слив интимок", "злив інтимок",
    "слив интим", "злив інтим",
    "вирт", "вірт", "cybersex",
]

MUTE_DURATION_SECONDS = 900
FLOOD_LIMIT = 10
TIME_WINDOW_SECONDS = 10
USER_ACTIVITY = {}

PROCESSED_MEDIA_GROUPS = {}
MEDIA_GROUP_TIMEOUT = 10

# === GEMINI ФУНКЦІЯ ПЕРЕВІРКИ ===
def check_with_gemini(text=None, photo_bytes=None):
    try:
        if not text and not photo_bytes:
            return False

        system_instruction = (
            "Ти — суворий модератор Telegram-чату. "
            "Визнач, чи містить контент: мат, образи, агресію, булінг, ненормативну лексику "
            "(включаючи російський та український мат, замасковані слова). "
            "Відповідай ТІЛЬКИ ОДНИМ СЛОВОМ без пояснень: YES (є порушення) або NO (все чисто)."
        )

        if photo_bytes and text:
            contents = [
                types.Part.from_bytes(data=photo_bytes, mime_type='image/jpeg'),
                f"Текст до фото: '{text}'"
            ]
        elif photo_bytes:
            contents = [types.Part.from_bytes(data=photo_bytes, mime_type='image/jpeg')]
        else:
            contents = f"Перевір цей текст: '{text}'"

        response = gemini_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                safety_settings=GEMINI_SAFETY_SETTINGS
            )
        )

        if response.text:
            result = response.text.strip().upper()
            preview = (text[:60] + '...') if text and len(text) > 60 else (text or 'фото')
            logging.info(f"🤖 [GEMINI] '{preview}' → {result}")
            return "YES" in result
        else:
            logging.warning(f"🤖 [GEMINI] Пуста відповідь для: '{text[:60] if text else 'фото'}'")
            return False

    except Exception as e:
        logging.error(f"❌ [GEMINI ERROR] {e}", exc_info=True)
        return False

# === КНОПКИ ===
def get_buttons():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("🧾 Правила", url=RULES_LINK))
    return keyboard

# === ФУНКЦІЯ ВІДПРАВКИ ПРИВІТАННЯ ===
def send_welcome_message(chat_id, reply_to_message_id=None):
    caption = (
        "👋 Привіт, ти потрапив у коментарі. Внизу цікаві посилання та правила поведінки (будь ласка, почитай їх)🐳\n\n"
        "📸 Мій <a href='{inst}'>инстаграм</a>\n"
        "🔴 Мій <a href='{yt}'>ютуб</a>\n\n"
        "💡 <a href='{bot}'>Тут</a> ти можеш запропонувати мне свою ідею для відео\n\n"
        "Написавши коментар, ти погоджуєшся з "
        "<a href='{rules}'>правилами</a> чату"
    ).format(inst=INST_LINK, yt=CHANNEL_LINK, rules=RULES_LINK, bot=BOT_LINK)

    max_retries = 3
    delay = 1.0

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
            logging.info(f"✅ Привітання відправлено (спроба {attempt+1})")
            return

        except apihelper.ApiTelegramException as e:
            error_message = str(e)
            if attempt < max_retries - 1 and "Bad Request: message to be replied not found" in error_message:
                logging.warning(f"⚠️ Повідомлення для відповіді не знайдено. Повтор через {delay:.1f} сек.")
                time.sleep(delay)
                delay *= 1.5
                continue

            logging.warning(f"⚠️ Помилка відправки GIF (спроба {attempt+1}): {e}. Відправка тексту.")
            try:
                bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=get_buttons(), reply_to_message_id=reply_to_message_id)
                logging.info("✅ Привітання (текст) відправлено.")
                return
            except Exception as e_text:
                logging.error(f"❌ Не вдалося відправити навіть текст: {e_text}", exc_info=True)
                return

        except Exception as e:
            logging.error(f"❌ Невідома помилка при відправці привітання: {e}", exc_info=True)
            return

    logging.error(f"❌ Не вдалося відправити привітання після {max_retries} спроб.")


# === ОБРОБКА ІДЕЇ ===
def process_idea_step(message):
    try:
        if message.content_type == 'text':
            if message.text == "❌ Скасувати" or message.text.startswith('/'):
                bot.send_message(message.chat.id, "❌ Відправку ідеї скасовано. Повертаємось до головного меню. 👇", reply_markup=get_main_menu_keyboard())
                return

        is_valid = False
        idea_text = ""
        normalized_text = ""

        if message.content_type == 'text':
            is_valid = True
            idea_text = message.text

            import re
            normalized_text = re.sub(r'[^a-zA-Z0-9а-яА-ЯёЁіІїЇєЄґҐ]', '', idea_text).lower()

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

        if not is_valid:
            bot.send_message(
                message.chat.id,
                "❌ **Недопустимий формат файлу!**\n\nБот приймає виключно **звичайний текст** або **PDF-документи**.\nБудь ласка, надішли ідею у правильному форматі або натисни «❌ Скасувати».",
                parse_mode="Markdown",
                reply_markup=get_cancel_keyboard()
            )
            bot.register_next_step_handler(message, process_idea_step)
            return

        if message.content_type == 'text':
            if normalized_text in PROCESSED_TEXT_IDEAS:
                bot.send_message(message.chat.id, "⚠️ **Ця ідея вже була надіслана раніше!**\n\nБудь ласка, надішли іншу пропозицію або натисни «❌ Скасувати».", parse_mode="Markdown", reply_markup=get_cancel_keyboard())
                bot.register_next_step_handler(message, process_idea_step)
                return
        elif message.content_type == 'document':
            file_uid = message.document.file_unique_id
            if file_uid in PROCESSED_FILE_IDEAS:
                bot.send_message(message.chat.id, "⚠️ **Цей файл уже був надісланий раніше!**\n\nБудь ласка, надішли інший файл або натисни «❌ Скасувати».", parse_mode="Markdown", reply_markup=get_cancel_keyboard())
                bot.register_next_step_handler(message, process_idea_step)
                return

        triggered_words = [word for word in STOP_WORDS if word.lower() in idea_text.lower()]
        if triggered_words:
            found_words_str = ", ".join(f'"{word}"' for word in triggered_words)
            bot.send_message(
                message.chat.id,
                f"⚠️ **У твоїй ідеї знайдено заборонене слово:** {found_words_str}\n\nБудь ласка, перефразуй свою пропозицію без цього слова та надішли знову:",
                parse_mode="Markdown",
                reply_markup=get_cancel_keyboard()
            )
            bot.register_next_step_handler(message, process_idea_step)
            return

        if idea_text and len(idea_text) > 3:
            if check_with_gemini(idea_text):
                bot.send_message(
                    message.chat.id,
                    "⚠️ **Твою ідею відхилено системою модерації!**\n\nБудь ласка, пиши культурно та без образ.",
                    parse_mode="Markdown",
                    reply_markup=get_main_menu_keyboard()
                )
                return

        user_username = f"@{message.from_user.username}" if message.from_user.username else "Немає юзернейму"
        user_info = f"👤 Від: {message.from_user.first_name} ({user_username}) | ID: `{message.from_user.id}`"

        if message.content_type == 'text':
            formatted_msg = f"💡 **Нова ідея через бота!**\n\n**{idea_text}**\n\n{user_info}\n\n#предложка"
            bot.send_message(ADMIN_CHAT_ID, formatted_msg, parse_mode="Markdown")
        elif message.content_type == 'document':
            caption_text = f"💡 **Нова ідея (PDF-файл) через бота!**\n\n📁 Файл: {message.document.file_name}\n**Опис:** {idea_text}\n\n{user_info}\n\n#предложка"
            bot.send_document(ADMIN_CHAT_ID, message.document.file_id, caption=caption_text, parse_mode="Markdown")

        if message.content_type == 'text':
            PROCESSED_TEXT_IDEAS.add(normalized_text)
        elif message.content_type == 'document':
            PROCESSED_FILE_IDEAS.add(message.document.file_unique_id)

        thank_you_caption = (
            "🥰 **Дякую! Твою ідею успішно відправлено автору.**\n\n"
            "Обов'язково чекай на згадку свого нікнейму у відео, якщо ідея сподобається і буде взята в роботу! 🎬🐳"
        )
        bot.send_animation(chat_id=message.chat.id, animation=THANK_YOU_GIF_URL, caption=thank_you_caption, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())
        logging.info(f"📩 Отримано нову ідею від {user_username}")

    except Exception as e:
        logging.error(f"Помилка в предложці: {e}")
        bot.send_message(message.chat.id, "❌ Сталася внутрішня помилка сервера. Спробуй ще раз пізніше.", reply_markup=get_main_menu_keyboard())


# === ГОЛОВНЕ МЕНЮ (ОСОБИСТА ПЕРЕПИСКА) ===
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


# === /start ===
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
            reply_markup=get_main_menu_keyboard()
        )
    else:
        reply_id = getattr(message.reply_to_message, 'message_id', None)
        send_welcome_message(message.chat.id, reply_to_message_id=reply_id)


# === АВТОМАТИЧНО ПЕРЕСЛАНІ ДОПИСИ (ТРИГЕР ПРИВІТАННЯ) ===
@bot.message_handler(
    func=lambda m: m.chat.id == DISCUSSION_GROUP_ID and m.is_automatic_forward,
    content_types=['text', 'photo', 'video', 'audio', 'voice', 'video_note', 'document', 'sticker', 'animation', 'poll']
)
def handle_forwarded_channel_post(message):
    global PROCESSED_MEDIA_GROUPS

    logging.info(f"👀 [ТРИГЕР] Форвард. ID: {message.message_id}. Media Group: {message.media_group_id}")

    try:
        if message.media_group_id:
            now = time.time()
            PROCESSED_MEDIA_GROUPS = {k: v for k, v in PROCESSED_MEDIA_GROUPS.items() if now - v < MEDIA_GROUP_TIMEOUT}
            if message.media_group_id in PROCESSED_MEDIA_GROUPS:
                logging.info(f"⏭ Пропуск дубліката медіа-групи {message.media_group_id}")
                return
            PROCESSED_MEDIA_GROUPS[message.media_group_id] = now
            logging.info(f"📢 Новий допис (медіа-група {message.media_group_id}). Запуск привітання...")
        else:
            logging.info("📢 Новий поодинокий допис. Запуск привітання...")

        send_welcome_message(DISCUSSION_GROUP_ID, reply_to_message_id=message.message_id)

    except Exception as e:
        logging.error(f"⚠️ Помилка при обробці форварду: {e}", exc_info=True)


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
        bot.send_message(chat_id, f"@{username} ⚠️ {reason}\nМут на 15 хвилин.", reply_to_message_id=reply_to_message_id)
        logging.warning(f"🔇 Мут {username} до {mute_until}. Причина: {reason}")
    except Exception as e:
        logging.error(f"❌ Помилка при видачі муту: {e}", exc_info=True)


def find_channel_post_id(message):
    try:
        if message.reply_to_message:
            if getattr(message.reply_to_message, 'is_automatic_forward', False):
                return message.reply_to_message.message_id
            return find_channel_post_id(message.reply_to_message)
        return None
    except:
        return None


# === МОДЕРАЦІЯ КОМЕНТАРІВ ===
@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document', 'audio', 'voice', 'animation'])
def handle_messages(message):
    global USER_ACTIVITY

    if getattr(message, 'is_automatic_forward', False) or message.sender_chat is not None:
        return

    if message.chat.id != DISCUSSION_GROUP_ID:
        return

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id

    logging.info(f"👀 [МОДЕРАЦІЯ] Коментар від @{username}. Тип: {message.content_type}")

    channel_post_id = find_channel_post_id(message)

    # --- Антиспам: перевірка посилань ---
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

    if has_link:
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception as e:
            logging.error(f"Помилка при видаленні посилання: {e}")
        return

    # --- Антифлуд ---
    now = datetime.datetime.now().timestamp()
    USER_ACTIVITY.setdefault(user_id, [])
    USER_ACTIVITY[user_id] = [(t, msg_id) for t, msg_id in USER_ACTIVITY[user_id] if now - t < TIME_WINDOW_SECONDS]
    USER_ACTIVITY[user_id].append((now, message.message_id))

    if len(USER_ACTIVITY[user_id]) >= FLOOD_LIMIT:
        logging.warning(f"🚨 Флуд від @{username}. Видача муту.")
        for timestamp, msg_id in USER_ACTIVITY[user_id]:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                logging.error(f"⚠️ Не вдалося видалити {msg_id}: {e}")
        apply_mute(chat_id, user_id, username, f"Флуд ({FLOOD_LIMIT}+ повідомлень за {TIME_WINDOW_SECONDS} секунд)", reply_to_message_id=channel_post_id)
        USER_ACTIVITY[user_id] = []
        return

    # --- Стоп-слова (текст І підпис до фото/файлу) ---
    text_for_stopwords = message.text or message.caption
    if text_for_stopwords:
        text = text_for_stopwords.lower()
        for word in STOP_WORDS:
            if word in text:
                logging.warning(f"🚨 Стоп-слово '{word}' від @{username}. Видача муту.")
                try:
                    bot.delete_message(chat_id, message.message_id)
                except Exception as e:
                    logging.error(f"⚠️ Не вдалося видалити повідомлення зі стоп-словом: {e}")
                apply_mute(chat_id, user_id, username, f"Стоп-слово: {word}", reply_to_message_id=channel_post_id)
                return

    # --- Gemini AI перевірка ---
    text_to_check = message.text or message.caption
    if text_to_check and len(text_to_check) > 3:
        if check_with_gemini(text_to_check):
            logging.warning(f"🤖 [GEMINI] Токсичність від @{username}.")
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception as e:
                logging.error(f"⚠️ Не вдалося видалити токсичне повідомлення: {e}")
            apply_mute(chat_id, user_id, username, "Прихована агресія (AI-модерація)", reply_to_message_id=channel_post_id)
            return

    logging.info(f"✅ [МОДЕРАЦІЯ] Коментар від @{username} пройшов перевірку.")


# === WEBHOOK (RENDER + GUNICORN) ===
app = Flask(__name__)

WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL", "https://telegram-olis-bot.onrender.com")
WEBHOOK_URL = f"{WEBHOOK_HOST}/{TOKEN}"

ALLOWED_UPDATES = ['message', 'channel_post', 'my_chat_member', 'chat_member', 'callback_query']

try:
    logging.info("🧹 Встановлюємо Webhook...")
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=WEBHOOK_URL, allowed_updates=ALLOWED_UPDATES)
    logging.info(f"✅ Webhook встановлено: {WEBHOOK_URL}")
except Exception as e:
    logging.error(f"❌ Помилка при встановленні Webhook: {e}")


@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Forbidden', 403


@app.route('/')
@app.route('/health')
def health():
    return 'Bot is running via Webhooks!', 200


if __name__ == '__main__':
    logging.info("🤖 Локальний запуск: вимикаємо вебхук та запускаємо Polling...")
    bot.remove_webhook()
    bot.infinity_polling(allowed_updates=ALLOWED_UPDATES)
