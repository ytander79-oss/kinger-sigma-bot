import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    CallbackQueryHandler, filters, ContextTypes
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 7089083244  # вставь свой ID

state = {
    "active_chat": None,
    "chats": {},
    "reply_to_message_id": None,
    "reply_to_chat_id": None,
    "recent_messages": {}  # {chat_id: [список последних сообщений]}
}

def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

async def send_admin(context, text, **kwargs):
    await context.bot.send_message(chat_id=ADMIN_ID, text=text, **kwargs)

# =================== КОМАНДЫ ===================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text(
        "Команды:\n"
        "/chats — список чатов\n"
        "/switch <id> — переключиться на чат\n"
        "/current — текущий активный чат\n"
        "/read [кол-во] — последние сообщения (по умолчанию 10)\n\n"
        "Просто напиши текст — отправлю в активный чат\n"
        "Кинь аудио — отправлю голосовым\n"
        "Кинь видео — отправлю кружком"
    )

async def cmd_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not state["chats"]:
        await update.message.reply_text("Бот ещё не добавлен ни в один чат.")
        return
    text = "Известные чаты:\n\n"
    for chat_id, name in state["chats"].items():
        active = " ✅" if chat_id == state["active_chat"] else ""
        text += f"{name}{active}\nID: `{chat_id}`\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text("Укажи ID чата: /switch -100123456789")
        return
    try:
        chat_id = int(context.args[0])
        if chat_id not in state["chats"]:
            await update.message.reply_text("Такой чат не найден. Проверь /chats")
            return
        state["active_chat"] = chat_id
        name = state["chats"][chat_id]
        await update.message.reply_text(f"Переключился на: {name}")
    except ValueError:
        await update.message.reply_text("Неверный ID чата.")

async def cmd_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not state["active_chat"]:
        await update.message.reply_text("Активный чат не выбран.")
        return
    name = state["chats"].get(state["active_chat"], "Неизвестно")
    await update.message.reply_text(
        f"Активный чат: {name}\nID: `{state['active_chat']}`",
        parse_mode="Markdown"
    )

async def cmd_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not state["active_chat"]:
        await update.message.reply_text("Сначала выбери чат через /switch")
        return

    count = 10
    if context.args:
        try:
            count = int(context.args[0])
        except ValueError:
            pass

    chat_id = state["active_chat"]
    messages = state["recent_messages"].get(chat_id, [])

    if not messages:
        await update.message.reply_text("Нет сохранённых сообщений из этого чата.")
        return

    last_messages = messages[-count:]

    # Показываем сообщения
    text = f"📋 Последние {len(last_messages)} сообщений из {state['chats'].get(chat_id)}:\n\n"
    for i, msg in enumerate(last_messages):
        text += f"{i+1}. {msg['from']}: {msg['text']}\n"

    await update.message.reply_text(text)

    # Кнопки для ответа на каждое сообщение
    keyboard = []
    for i, msg in enumerate(last_messages):
        keyboard.append([InlineKeyboardButton(
            f"Ответить на #{i+1} ({msg['from']})",
            callback_data=f"reply_{chat_id}_{msg['message_id']}"
        )])

    await update.message.reply_text(
        "На какое сообщение ответить?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =================== CALLBACK КНОПОК ===================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    data = query.data

    if data.startswith("reply_"):
        parts = data.split("_")
        chat_id = int(parts[1])
        message_id = int(parts[2])

        state["reply_to_chat_id"] = chat_id
        state["reply_to_message_id"] = message_id
        state["active_chat"] = chat_id

        await query.edit_message_text("Выбрано! Теперь напиши текст ответа:")

# =================== ОТПРАВКА ОТ АДМИНА ===================

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if update.effective_chat.type != "private": return
    if not state["active_chat"]:
        await update.message.reply_text("Сначала выбери чат через /switch")
        return

    reply_to = state.get("reply_to_message_id")
    reply_chat = state.get("reply_to_chat_id")

    # Сбрасываем reply после использования
    state["reply_to_message_id"] = None
    state["reply_to_chat_id"] = None

    target_chat = reply_chat if reply_chat else state["active_chat"]

    await context.bot.send_message(
        chat_id=target_chat,
        text=update.message.text,
        reply_to_message_id=reply_to
    )

async def handle_admin_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if update.effective_chat.type != "private": return
    if not state["active_chat"]:
        await update.message.reply_text("Сначала выбери чат через /switch")
        return

    file = update.message.audio or update.message.voice or update.message.document
    if not file: return

    file_obj = await context.bot.get_file(file.file_id)
    file_bytes = await file_obj.download_as_bytearray()

    await context.bot.send_voice(
        chat_id=state["active_chat"],
        voice=bytes(file_bytes)
    )
    await update.message.reply_text("Голосовое отправлено ✅")

async def handle_admin_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if update.effective_chat.type != "private": return
    if not state["active_chat"]:
        await update.message.reply_text("Сначала выбери чат через /switch")
        return

    file = update.message.video or update.message.video_note or update.message.document
    if not file: return

    file_obj = await context.bot.get_file(file.file_id)
    file_bytes = await file_obj.download_as_bytearray()

    await context.bot.send_video_note(
        chat_id=state["active_chat"],
        video_note=bytes(file_bytes)
    )
    await update.message.reply_text("Кружок отправлен ✅")

# =================== ВХОДЯЩИЕ В ГРУППАХ ===================

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = chat.id
    message = update.message
    if not message: return

    # Запоминаем чат
    if chat_id not in state["chats"]:
        state["chats"][chat_id] = chat.title or str(chat_id)
        await send_admin(
            context,
            f"📌 Новый чат: {state['chats'][chat_id]}\nID: `{chat_id}`",
            parse_mode="Markdown"
        )

    # Сохраняем сообщение в историю
    if chat_id not in state["recent_messages"]:
        state["recent_messages"][chat_id] = []

    user = message.from_user
    name = user.full_name if user else "Неизвестно"
    text = message.text or "[не текст]"

    state["recent_messages"][chat_id].append({
        "from": name,
        "text": text,
        "message_id": message.message_id
    })

    # Храним только последние 50 сообщений на чат
    if len(state["recent_messages"][chat_id]) > 50:
        state["recent_messages"][chat_id].pop(0)

    # Проверяем — пинг или ответ на сообщение бота
    bot_username = context.bot.username
    is_reply_to_bot = (
        message.reply_to_message and
        message.reply_to_message.from_user and
        message.reply_to_message.from_user.username == bot_username
    )
    is_mention = (
        message.entities and
        any(e.type == "mention" and f"@{bot_username}" in text for e in message.entities)
    )

    if is_reply_to_bot or is_mention:
        chat_name = state["chats"].get(chat_id, str(chat_id))
        await send_admin(
            context,
            f"🔔 Тебя упомянули в {chat_name}!\n\n"
            f"👤 {name}:\n{text}\n\n"
            f"Чат: `{chat_id}` | Сообщение: `{message.message_id}`",
            parse_mode="Markdown"
        )

# =================== ВХОДЯЩИЕ В ЛС БОТУ ===================

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID: return

    user = update.effective_user
    name = user.full_name
    username = f"@{user.username}" if user.username else ""
    text = update.message.text or "[не текст]"

    keyboard = [[InlineKeyboardButton(
        "Ответить",
        callback_data=f"reply_{user.id}_{update.message.message_id}"
    )]]

    await send_admin(
        context,
        f"💬 ЛС от {name} {username}:\n\n{text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =================== ЗАПУСК ===================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("chats", cmd_chats))
    app.add_handler(CommandHandler("switch", cmd_switch))
    app.add_handler(CommandHandler("current", cmd_current))
    app.add_handler(CommandHandler("read", cmd_read))

    app.add_handler(CallbackQueryHandler(handle_callback))

    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & filters.User(ADMIN_ID),
        handle_admin_text
    ))
    app.add_handler(MessageHandler(
        (filters.AUDIO | filters.VOICE | filters.Document.AUDIO) &
        filters.ChatType.PRIVATE & filters.User(ADMIN_ID),
        handle_admin_audio
    ))
    app.add_handler(MessageHandler(
        (filters.VIDEO | filters.VIDEO_NOTE) &
        filters.ChatType.PRIVATE & filters.User(ADMIN_ID),
        handle_admin_video
    ))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & ~filters.User(ADMIN_ID),
        handle_private_message
    ))
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS,
        handle_group_message
    ))

    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
