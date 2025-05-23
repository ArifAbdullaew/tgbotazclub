import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters,
    ContextTypes, ConversationHandler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    encoding='utf-8',
    filename='bot_logs.log',
)
logger = logging.getLogger(__name__)

# Файлы для хранения данных
REGISTERED_USERS_FILE = "registered_users.json"
CONTENT_FILE = "content.json"

# ID администраторов
ADMIN_IDS = {785773730, 755365654}

# Главное меню
REGISTERED_MENU = ReplyKeyboardMarkup(
    [["Информация о мероприятии", "Программа мероприятия"]],
    resize_keyboard=True
)

UNREGISTERED_MENU = ReplyKeyboardMarkup(
    [["О мероприятии", "Регистрация"]],
    resize_keyboard=True
)

# Шаги для регистрации
ENTER_ORGANIZATION, ENTER_NAME, ENTER_PHONE = range(3)
# Шаги для добавления гостя
ENTER_GUEST_ORGANIZATION, ENTER_GUEST_NAME, ENTER_GUEST_PHONE = range(3)


def read_text_file(file_path):
    """Читает содержимое текстового файла и возвращает его."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    return "Файл с информацией не найден."

# Загрузка и сохранение данных
def load_data(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(file_name, data):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

registered_users = load_data(REGISTERED_USERS_FILE)

async def about_event_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = read_text_file("about_event.txt")
    await update.message.reply_text(text,parse_mode="HTML", protect_content=True)

async def event_program(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = read_text_file("event_program.txt")
    await update.message.reply_text(text, protect_content=True)

# Команды и обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info(f"Пользователь {user.first_name} ({user.id}) запустил команду /start")

    if str(user.id) in registered_users and registered_users[str(user.id)].get("approved", False):
        menu = REGISTERED_MENU
    else:
        menu = UNREGISTERED_MENU

    await update.message.reply_text(
        "Добро пожаловать на День Культуры Азербайджана! Выберите действие:",
        reply_markup=menu,
        protect_content=True
    )

async def about_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "День Культуры Азербайджана: познакомьтесь с богатой культурой и традициями Азербайджана. "
        "Дата: 29 мая 2025 года, место: Центр конференций.",
        protect_content=True
    )

# Регистрация пользователя
async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if str(user.id) in registered_users:
        await update.message.reply_text(
            "Вы уже зарегистрированы или ожидаете одобрения.",
            protect_content=True
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Введите название вашей организации:",
        protect_content=True
    )
    return ENTER_ORGANIZATION

async def enter_organization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['organization'] = update.message.text
    await update.message.reply_text(
        "Теперь введите ваше ФИО:",
        protect_content=True
    )
    return ENTER_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text(
        "Введите ваш номер телефона (в формате +71234567890):",
        protect_content=True
    )
    return ENTER_PHONE

async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    phone_number = update.message.text

    if not phone_number.startswith("+") or not phone_number[1:].isdigit():
        await update.message.reply_text(
            "Пожалуйста, введите корректный номер телефона в формате +71234567890:",
            protect_content=True
        )
        return ENTER_PHONE

    context.user_data['phone'] = phone_number

    registered_users[str(user.id)] = {
        "name": context.user_data['name'],
        "organization": context.user_data['organization'],
        "phone": context.user_data['phone'],
        "approved": False
    }
    save_data(REGISTERED_USERS_FILE, registered_users)

    await update.message.reply_text(
        "Спасибо за регистрацию! Ожидайте подтверждения от администрации.",
        protect_content=True
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Одобрить", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("Отклонить", callback_data=f"reject_{user.id}")
        ]
    ])
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"Новая заявка на регистрацию:\n"
                 f"Имя: {context.user_data['name']}\n"
                 f"Организация: {context.user_data['organization']}\n"
                 f"Телефон: {context.user_data['phone']}\n"
                 f"ID: {user.id}",
            reply_markup=keyboard,
            protect_content=True
        )

    return ConversationHandler.END

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("_")
    user_id = str(user_id)

    if user_id not in registered_users:
        await query.edit_message_text(
            "Эта заявка уже обработана.",
        )
        return

    if action == "approve":
        registered_users[user_id]["approved"] = True
        save_data(REGISTERED_USERS_FILE, registered_users)
        await context.bot.send_message(
            chat_id=int(user_id),
            text="Ваша регистрация одобрена! Теперь у вас есть доступ к дополнительной информации.",
            reply_markup=REGISTERED_MENU,
            protect_content=True
        )
        await query.edit_message_text(
            "Заявка одобрена.",
        )
    elif action == "reject":
        del registered_users[user_id]
        save_data(REGISTERED_USERS_FILE, registered_users)
        await context.bot.send_message(
            chat_id=int(user_id),
            text="К сожалению, ваша заявка на регистрацию отклонена.",
            protect_content=True
        )
        await query.edit_message_text(
            "Заявка отклонена.",
        )

async def show_registered_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "У вас нет прав для выполнения этой команды.",
            protect_content=True
        )
        return

    if not registered_users:
        await update.message.reply_text(
            "Список зарегистрированных гостей пуст.",
            protect_content=True
        )
        return

    guest_list = "\n".join([
        f"{guest_data['name']} ({guest_data.get('organization', 'Не указано')}) - ID: {guest_id} - Телефон: {guest_data.get('phone', 'Не указан')}"
        for guest_id, guest_data in registered_users.items()
        if guest_data.get("approved", False)
    ])
    if not guest_list:
        await update.message.reply_text(
            "Нет одобренных гостей.",
            protect_content=True
        )
    else:
        await update.message.reply_text(
            f"Список зарегистрированных гостей:\n\n{guest_list}",
            protect_content=True
        )

async def start_add_guest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "У вас нет прав для выполнения этой команды.",
            protect_content=True
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Введите название организации гостя:",
        protect_content=True
    )
    return ENTER_GUEST_ORGANIZATION

async def enter_guest_organization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Сохраняем название организации гостя
    context.user_data['guest_organization'] = update.message.text
    await update.message.reply_text(
        "Теперь введите ФИО гостя:",
        protect_content=True
    )
    return ENTER_GUEST_NAME

async def enter_guest_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Сохраняем ФИО гостя
    context.user_data['guest_name'] = update.message.text
    await update.message.reply_text(
        "Введите номер телефона гостя (в формате +71234567890):",
        protect_content=True
    )
    return ENTER_GUEST_PHONE

async def enter_guest_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone_number = update.message.text

    # Проверяем корректность номера телефона
    if not phone_number.startswith("+") or not phone_number[1:].isdigit():
        await update.message.reply_text(
            "Пожалуйста, введите корректный номер телефона в формате +71234567890:",
            protect_content=True
        )
        return ENTER_GUEST_PHONE

    # Сохраняем номер телефона гостя
    context.user_data['guest_phone'] = phone_number

    # Получаем данные гостя из контекста
    guest_name = context.user_data.get('guest_name', 'Не указано')
    guest_organization = context.user_data.get('guest_organization', 'Не указано')

    # Генерируем уникальный ID гостя
    guest_id = f"manual_{len(registered_users) + 1}"
    registered_users[guest_id] = {
        "name": guest_name,
        "organization": guest_organization,
        "phone": phone_number,
        "approved": True
    }
    save_data(REGISTERED_USERS_FILE, registered_users)

    # Уведомляем об успешном добавлении
    await update.message.reply_text(
        f"Гость '{guest_name}' из организации '{guest_organization}' "
        f"с номером телефона {phone_number} успешно добавлен.",
        protect_content=True
    )
    return ConversationHandler.END


async def cancel_add_guest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Добавление гостя отменено.",
        protect_content=True
    )
    return ConversationHandler.END

async def delete_guest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "У вас нет прав для выполнения этой команды.",
            protect_content=True
        )
        return

    try:
        if not context.args or len(context.args) != 1:
            raise ValueError("Использование: /delete_guest <ID>")

        guest_id = context.args[0]
        if guest_id not in registered_users:
            await update.message.reply_text(
                f"Гость с ID {guest_id} не найден.",
                protect_content=True
            )
            return

        guest_data = registered_users[guest_id]
        del registered_users[guest_id]
        save_data(REGISTERED_USERS_FILE, registered_users)

        if guest_id.isdigit():
            try:
                await context.bot.send_message(
                    chat_id=int(guest_id),
                    text="Ваш статус участника был отменен администратором. Если это ошибка, свяжитесь с организатором.",
                    protect_content=True
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить сообщение пользователю {guest_id}: {e}")

        await update.message.reply_text(
            f"Гость '{guest_data['name']}' из организации '{guest_data.get('organization', 'Не указано')}' успешно удален.",
            protect_content=True
        )

    except ValueError as e:
        await update.message.reply_text(
            str(e),
            protect_content=True
        )

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "У вас нет прав для выполнения этой команды.",
            protect_content=True
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Используйте: /broadcast <сообщение>",
            protect_content=True
        )
        return

    message_text = " ".join(context.args)
    failed_users = []

    for user_id, user_data in registered_users.items():
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=message_text,
                protect_content=True
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            failed_users.append(user_id)

    if failed_users:
        failed_list = ", ".join(failed_users)
        await update.message.reply_text(
            f"Сообщение отправлено, но не удалось доставить следующим пользователям: {failed_list}.",
            protect_content=True
        )
    else:
        await update.message.reply_text(
            "Сообщение успешно отправлено всем пользователям.",
            protect_content=True
        )

# Обработчики и запуск бота
def main():
    app = Application.builder().token("7695616588:AAGO_9SdZZ6NJ6OHM4DRFQ-2w2V7vGJ7W_E").build()

    registration_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Регистрация$"), start_registration)],
        states={
            ENTER_ORGANIZATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_organization)],
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add_guest)]
    )

    add_guest_handler = ConversationHandler(
        entry_points=[CommandHandler("add_guest", start_add_guest)],
        states={
            ENTER_GUEST_ORGANIZATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_guest_organization)],
            ENTER_GUEST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_guest_name)],
            ENTER_GUEST_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_guest_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add_guest)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("registered_users", show_registered_users))
    app.add_handler(CommandHandler("delete_guest", delete_guest))
    app.add_handler(add_guest_handler)
    app.add_handler(CallbackQueryHandler(handle_approval))
    app.add_handler(registration_handler)
    app.add_handler(MessageHandler(filters.Regex("^О мероприятии$"), about_event))
    app.add_handler(CommandHandler("broadcast", broadcast_message))
    app.add_handler(MessageHandler(filters.Regex("^Информация о мероприятии$"), about_event_plan))
    app.add_handler(MessageHandler(filters.Regex("^Программа мероприятия$"), event_program))



    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
