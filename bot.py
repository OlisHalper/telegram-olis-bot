import os
import time
import datetime
import logging
from flask import Flask
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions

# === НАСТРОЙКИ ЛОГИРОВАНИЯ ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === КОНФИГУРАЦИЯ БОТА ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logging.error("❌ BOT_TOKEN не найден. Установи его в переменные окружения!")
    exit(1) 

bot = telebot.TeleBot(TOKEN)

# === ОСНОВНЫЕ ССЫЛКИ И ID (Используем ваши ID) ===
CHANNEL_USERNAME = "@whoisolis"
CHANNEL_ID = -1003083438241 # ID канала
DISCUSSION_GROUP_ID = -1003084315849 # ID группы комментариев

GIF_URL = "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3bThjMXZkMTExb2IzZW9zdm0wNjRieG1haXVrcGVicHBsNzJqNXZ0eSZlcF92MV9naWZzX3NlYXJjaCZjdD1n/dT6f2FnfY24C1L1TIR/giphy.gif"
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

MUTE_DURATION_SECONDS = 3600 # 1 час
FLOOD_LIMIT = 10
TIME_WINDOW_SECONDS = 10
USER_ACTIVITY = {} # {user_id: [(timestamp, message_id), ...]}

# === ОТСЛЕЖИВАНИЕ МЕДИА-ГРУПП ===
# Словарь для отслеживания уже обработанных медиа-групп, чтобы не дублировать приветствие
PROCESSED_MEDIA_GROUPS = {} # {media_group_id: timestamp}
MEDIA_GROUP_TIMEOUT = 10 # Время, в течение которого сообщения считаются частью группы (в секундах)

# === КНОПКИ ===
def get_buttons():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("🧾 Правила", url=RULES_LINK))
    return keyboard

# === ПРИВЕТСТВИЕ С ПОВТОРНЫМИ ПОПЫТКАМИ ===
def send_welcome_message(chat_id, reply_to_message_id=None):
    caption = (
        "👋 Привет ты попал в комментарии под моим постом. Внизу интересные ссылки и правила поведения (пожалуйста почитай их страничка сделана вроде симпатично)🐳\n\n"
        "📸 Мой <a href='{inst}'>инстаграм</a>\n"
        "🔴 Мой <a href='{yt}'>ютуб</a>\n\n"
        "Написав комментарий, ты соглашаешься с "
        "<a href='{rules}'>правилами</a> чата 🐳"
    ).format(inst=INST_LINK, yt=CHANNEL_LINK, rules=RULES_LINK)

    max_retries = 3
    delay = 1.5 

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
            logging.info(f"✅ Приветствие отправлено (попытка {attempt+1}) в ответ на ID: {reply_to_message_id}")
            return # Успех
        
        except telebot.apihelper.ApiTelegramException as e:
            error_message = str(e)
            
            if attempt < max_retries - 1 and "Bad Request: message to be replied not found" in error_message:
                logging.warning(f"⚠️ Ошибка 400: Сообщение для ответа {reply_to_message_id} еще не найдено. Повтор через {delay} сек.")
                time.sleep(delay)
                delay *= 1.5 
                continue
            
            logging.warning(f"⚠️ Ошибка отправки GIF-приветствия (попытка {attempt+1}): {e}. Отправка текстовой версии.")
            
            try:
                bot.send_message(
                    chat_id, 
                    caption, 
                    parse_mode="HTML", 
                    reply_markup=get_buttons(),
                    reply_to_message_id=reply_to_message_id
                )
                logging.info(f"✅ Приветствие (текст) отправлено.")
                return 
            except Exception as e_text:
                logging.error(f"❌ Критическая ошибка: не удалось отправить даже текстовое приветствие: {e_text}", exc_info=True)
                return 

        except Exception as e:
            logging.error(f"❌ Неизвестная ошибка при отправке приветствия: {e}", exc_info=True)
            return

    logging.error(f"❌ Не удалось отправить приветствие после {max_retries} попыток.")


# === КОМАНДА /start ===
@bot.message_handler(commands=['start'])
def send_rules(message):
    reply_id = getattr(message.reply_to_message, 'message_id', None)
    send_welcome_message(message.chat.id, reply_to_message_id=reply_id)


# === ОБРАБОТКА АВТОМАТИЧЕСКИ ПЕРЕСЛАННЫХ ПОСТОВ (ФИКС ДУБЛИРОВАНИЯ) ===
@bot.message_handler(func=lambda m: m.chat.id == DISCUSSION_GROUP_ID and m.is_automatic_forward, content_types=['text', 'photo', 'video', 'audio', 'voice', 'video_note', 'document', 'sticker', 'animation', 'poll'])
def handle_forwarded_channel_post(message):
    global PROCESSED_MEDIA_GROUPS
    
    logging.info(f"👀 [ТРИГГЕР] Обнаружен автоматический форвард. ID: {message.message_id}. Media Group ID: {message.media_group_id}")
    
    try:
        # --- БЛОК АНТИ-ДУБЛИКАТ ДЛЯ МЕДИА-ГРУПП ---
        if message.media_group_id:
            now = time.time()
            # 1. Очистка старых записей
            PROCESSED_MEDIA_GROUPS = {k: v for k, v in PROCESSED_MEDIA_GROUPS.items() if now - v < MEDIA_GROUP_TIMEOUT}
            
            # 2. Проверка, была ли группа уже обработана
            if message.media_group_id in PROCESSED_MEDIA_GROUPS:
                logging.info(f"⏭ [ТРИГГЕР] Пропуск дубликата медиа-группы {message.media_group_id}.")
                return # Выходим, чтобы не отправлять приветствие N раз
            
            # 3. Пометка группы как обработанной
            PROCESSED_MEDIA_GROUPS[message.media_group_id] = now
            logging.info(f"📢 [ТРИГГЕР] Новый пост (медиа-группа {message.media_group_id}). Отправка приветствия.")
            
        else:
            # Одиночный пост
            logging.info(f"📢 [ТРИГГЕР] Новый одиночный пост. Отправка приветствия.")

        # Небольшая задержка, чтобы дать Telegram время создать тред
        time.sleep(1.5)
        send_welcome_message(DISCUSSION_GROUP_ID, reply_to_message_id=message.message_id)
        
    except Exception as e:
        logging.error(f"⚠️ Ошибка при обработке пересланного поста: {e}", exc_info=True)

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
        if message.reply_to_message:
            if getattr(message.reply_to_message, 'is_automatic_forward', False):
                return message.reply_to_message.message_id
            return find_channel_post_id(message.reply_to_message)
        return None
    except:
        return None

# === АНТИФЛУД И СТОП-СЛОВА (ТОЛЬКО ДЛЯ ПОЛЬЗОВАТЕЛЬСКИХ КОММЕНТАРИЕВ) ===
@bot.message_handler(content_types=['text', 'sticker', 'photo', 'video', 'document', 'audio', 'voice', 'animation'])
def handle_messages(message):
    global USER_ACTIVITY
    
    # 1. Игнорируем автоматически пересланные посты из канала (их обрабатывает handle_forwarded_channel_post)
    if getattr(message, 'is_automatic_forward', False):
        return
    
    # 2. Обрабатываем только в целевой группе
    if message.chat.id != DISCUSSION_GROUP_ID:
        return
        
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    chat_id = message.chat.id
    
    logging.info(f"👀 [МОДЕРАЦИЯ] Получен комментарий от @{username}. Тип: {message.content_type}")
    
    # Ищем исходный пост канала для ответа-уведомления о муте
    channel_post_id = find_channel_post_id(message)

    # --- Антифлуд ---
    now = datetime.datetime.now().timestamp()
    USER_ACTIVITY.setdefault(user_id, [])
    
    USER_ACTIVITY[user_id] = [(t, msg_id) for t, msg_id in USER_ACTIVITY[user_id] if now - t < TIME_WINDOW_SECONDS]
    USER_ACTIVITY[user_id].append((now, message.message_id))

    if len(USER_ACTIVITY[user_id]) >= FLOOD_LIMIT:
        logging.warning(f"🚨 [МОДЕРАЦИЯ] Обнаружен флуд от @{username}")
        
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
            reply_to_message_id=channel_post_id
        )
        USER_ACTIVITY[user_id] = []
        return

    # --- Стоп-слова ---
    if message.text:
        text = message.text.lower()
        for word in STOP_WORDS:
            if word in text:
                logging.warning(f"🚨 [МОДЕРАЦИЯ] Обнаружено стоп-слово '{word}' от @{username}")
                
                try:
                    bot.delete_message(chat_id, message.message_id)
                except Exception as e:
                    logging.error(f"⚠️ Не удалось удалить сообщение со стоп-словом: {e}")
                
                apply_mute(
                    chat_id, 
                    user_id, 
                    username, 
                    f"Стоп-слово: {word}",
                    reply_to_message_id=channel_post_id
                )
                return
    
    logging.info(f"✅ [МОДЕРАЦИЯ] Комментарий от @{username} прошел проверку.")
            
# === ЗАПУСК (АДАПТАЦИЯ ДЛЯ RENDER/CLOUD) ===

# Переменная Flask, которую Render ожидает увидеть
app = Flask(__name__)

# Функция для запуска Polling в отдельном потоке
def run_polling():
    logging.info("🧹 Попытка удаления старого Webhook...")
    try:
        bot.remove_webhook() 
        logging.info("✅ Webhook удален успешно")
        time.sleep(1)
    except Exception as e:
        logging.warning(f"⚠️ Ошибка при удалении webhook (возможно, его не было): {e}")

    logging.info("🚀 Запуск бота в режиме Infinity Polling...")
    try:
        # Убеждаемся, что бот слушает все нужные типы обновлений
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
