import logging
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- CONFIGURATION ---
TOKEN = "8667960061:AAGXfbJlHvqhQ8A1RQSkCHWKinIzzDtJJEY"
ALLOWED_GROUP_ID = -1004413547137

USERS_FILE = "users.json"
BANNED_WORDS_FILE = "banned_words.json"
WARNS_FILE = "warns.json"

def load_data(filename, default):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump(default, f)
        return default
    with open(filename, "r") as f:
        return json.load(f)

def save_data(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

users_db = load_data(USERS_FILE, {})
banned_words = load_data(BANNED_WORDS_FILE, [])
warns_db = load_data(WARNS_FILE, {})

spam_tracker = {}

# Standard Permissions (PTB v20+ Compatible)
FULL_USER_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_documents=True,
    can_send_audios=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True
)

RESTRICTED_PERMISSIONS = ChatPermissions(can_send_messages=False)


# --- HELPER FUNCTIONS ---

def is_allowed_group(update: Update) -> bool:
    if update.effective_chat and update.effective_chat.id == ALLOWED_GROUP_ID:
        return True
    return False

async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    elif context.args:
        try:
            user_id = int(context.args[0].replace("@", ""))
            member = await context.bot.get_chat_member(ALLOWED_GROUP_ID, user_id)
            return member.user
        except Exception:
            if update.message and update.message.entities:
                for entity in update.message.entities:
                    if entity.type == "text_mention":
                        return entity.user
    return None

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    # Anonymous Admin Support
    if update and update.effective_message and update.effective_message.sender_chat:
        if update.effective_message.sender_chat.id == ALLOWED_GROUP_ID:
            return True
            
    uid = user_id or (update.effective_user.id if update and update.effective_user else None)
    if not uid:
        return False
        
    try:
        member = await context.bot.get_chat_member(ALLOWED_GROUP_ID, uid)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, action_text: str, target_user, buttons_type: str = "ban"):
    try:
        admins = await context.bot.get_chat_administrators(ALLOWED_GROUP_ID)
    except Exception:
        return

    keyboard = []
    if buttons_type == "ban":
        keyboard = [[InlineKeyboardButton("Unban", callback_data=f"adm_unban_{target_user.id}"), InlineKeyboardButton("Ignore", callback_data="adm_ignore")]]
    elif buttons_type == "mute":
        keyboard = [[InlineKeyboardButton("Unmute", callback_data=f"adm_unmute_{target_user.id}"), InlineKeyboardButton("Ignore", callback_data="adm_ignore")]]
    elif buttons_type == "unban":
        keyboard = [[InlineKeyboardButton("Ban Again", callback_data=f"adm_ban_{target_user.id}"), InlineKeyboardButton("Ignore", callback_data="adm_ignore")]]
    elif buttons_type == "unmute":
        keyboard = [[InlineKeyboardButton("Mute Again", callback_data=f"adm_mute_{target_user.id}"), InlineKeyboardButton("Ignore", callback_data="adm_ignore")]]

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    msg_body = (
        f"🔔 <b>Admin Update Alert</b>\n\n"
        f"👤 <b>User:</b> {target_user.mention_html()} (<code>{target_user.id}</code>)\n"
        f"⚡ <b>Action:</b> {action_text}"
    )

    for admin in admins:
        if not admin.user.is_bot:
            try:
                await context.bot.send_message(chat_id=admin.user.id, text=msg_body, parse_mode="HTML", reply_markup=reply_markup)
            except Exception:
                pass

async def notify_banned_user(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    msg = "AAP HAMARE GROUP SE BAN HUE HAI AGAR AAP ISSE GALAT FEHMI SAMAJHTE HO TOH PLEASE CONTACT - @epic_ind \nTHANK YOU 🌸"
    try:
        await context.bot.send_message(chat_id=user_id, text=msg)
    except Exception:
        pass


# --- COMMAND HANDLERS ---

async def cmd_adm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    msg_text = " ".join(context.args) if context.args else "Attention Admins!"
    admins = await update.effective_chat.get_administrators()
    mentions = [admin.user.mention_html() for admin in admins if not admin.user.is_bot]
    
    text = f"🚨 <b>Admin Call:</b> {msg_text}\n\n" + " ".join(mentions)
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_bye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text("Please reply to a user or mention user_id.")
        return

    await context.bot.ban_chat_member(ALLOWED_GROUP_ID, target.id)
    keyboard = [[InlineKeyboardButton("Unban User", callback_data=f"adm_unban_{target.id}")]]
    
    await update.message.reply_text(f"🚫 {target.mention_html()} ko ban kar diya gaya hai.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    await notify_banned_user(context, target.id)
    await notify_admins(context, "User BAN hua hai", target, "ban")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    target = await get_target_user(update, context)
    if not target: return
        
    await context.bot.unban_chat_member(ALLOWED_GROUP_ID, target.id, only_if_banned=True)
    await update.message.reply_text(f"✅ {target.mention_html()} unban ho gaye hain.", parse_mode="HTML")
    await notify_admins(context, "User UNBAN hua hai", target, "unban")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    target = await get_target_user(update, context)
    if not target: return

    await context.bot.restrict_chat_member(ALLOWED_GROUP_ID, target.id, RESTRICTED_PERMISSIONS)
    await update.message.reply_text(f"🔇 {target.mention_html()} ko mute kar diya hai.", parse_mode="HTML")
    await notify_admins(context, "User MUTE hua hai", target, "mute")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    target = await get_target_user(update, context)
    if not target: return

    await context.bot.restrict_chat_member(ALLOWED_GROUP_ID, target.id, FULL_USER_PERMISSIONS)
    await update.message.reply_text(f"🔊 {target.mention_html()} unmute ho gaye hain.", parse_mode="HTML")
    await notify_admins(context, "User UNMUTE hua hai", target, "unmute")

async def cmd_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return

    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text("Please user ke message par reply karein ya tag karein.")
        return

    uid = str(target.id)
    warns_db[uid] = 0
    save_data(WARNS_FILE, warns_db)

    await update.message.reply_text(f"🕊️ {target.mention_html()} ke saare warns reset kar diye gaye hain (0/4)!", parse_mode="HTML")

async def cmd_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    target = await get_target_user(update, context)
    if not target: return

    await context.bot.promote_chat_member(ALLOWED_GROUP_ID, target.id, can_delete_messages=True, can_restrict_members=True, can_pin_messages=True)
    await update.message.reply_text(f"👑 {target.mention_html()} ab Admin hain!", parse_mode="HTML")

async def cmd_take(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    target = await get_target_user(update, context)
    if not target: return

    await context.bot.promote_chat_member(ALLOWED_GROUP_ID, target.id, can_delete_messages=False, can_restrict_members=False, can_pin_messages=False)
    await update.message.reply_text(f"📉 {target.mention_html()} se admin rights le liye gaye hain.", parse_mode="HTML")

async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    if update.message.reply_to_message:
        await context.bot.pin_chat_message(ALLOWED_GROUP_ID, update.message.reply_to_message.message_id)
        await update.message.reply_text("📌 Message pin kar diya hai.")

async def cmd_unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    await context.bot.unpin_chat_message(ALLOWED_GROUP_ID)
    await update.message.reply_text("📌 Message unpin kar diya hai.")

async def cmd_restrict_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    if not context.args: return
    word = context.args[0].lower()
    if word not in banned_words:
        banned_words.append(word)
        save_data(BANNED_WORDS_FILE, banned_words)
        await update.message.reply_text(f"🚫 Word '{word}' banned list me add kar diya hai.")

async def cmd_remove_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    if not context.args: return
    word = context.args[0].lower()
    if word in banned_words:
        banned_words.remove(word)
        save_data(BANNED_WORDS_FILE, banned_words)
        await update.message.reply_text(f"✅ Word '{word}' unban kar diya hai.")

async def cmd_list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    if not banned_words:
        await update.message.reply_text("📝 Koi banned word nahi hai.")
        return

    text = "📝 <b>Banned Words List:</b>\n"
    keyboard = []
    
    for word in banned_words:
        text += f"• <code>{word}</code>\n"
        keyboard.append([InlineKeyboardButton(f"❌ Remove '{word}'", callback_data=f"delword_{word}")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def cmd_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    
    msg_text = " ".join(context.args) if context.args else "Group Announcement!"
    user_ids = list(users_db.keys())[:100]
    mentions = [f'<a href="tg://user?id={uid}">{users_db[uid]}</a>' for uid in user_ids]
    
    for i in range(0, len(mentions), 50):
        chunk = mentions[i:i + 50]
        text = f"📢 <b>{msg_text}</b>\n\n" + " ".join(chunk)
        await update.message.reply_text(text, parse_mode="HTML")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    
    target = await get_target_user(update, context) or update.effective_user
    uid = str(target.id)
    warn_count = warns_db.get(uid, 0)
    
    await update.message.reply_text(
        f"👤 <b>User Info:</b>\n"
        f"Name: {target.mention_html()}\n"
        f"ID: <code>{target.id}</code>\n"
        f"Warn Count: <b>{warn_count}/4</b>",
        parse_mode="HTML"
    )

# --- CALLBACK HANDLERS FOR BUTTONS ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    admin_id = query.from_user.id
    
    if not await is_admin(update, context, admin_id):
        await query.answer("Aap admin nahi ho!", show_alert=True)
        return

    if data.startswith("delword_"):
        word_to_remove = data.split("_")[1]
        if word_to_remove in banned_words:
            banned_words.remove(word_to_remove)
            save_data(BANNED_WORDS_FILE, banned_words)
            await query.answer(f"Word '{word_to_remove}' remove kar diya hai!")
            
            if banned_words:
                keyboard = [[InlineKeyboardButton(f"❌ Remove '{w}'", callback_data=f"delword_{w}")] for w in banned_words]
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.edit_message_text("📝 Saare banned words remove ho chuke hain.")
        return

    if data == "adm_ignore":
        await query.edit_message_text(f"{query.message.text}\n\n✅ <i>Marked as Ignored.</i>", parse_mode="HTML")
        return

    action, target_id = data.split("_")[1], int(data.split("_")[2])
    target_member = await context.bot.get_chat_member(ALLOWED_GROUP_ID, target_id)
    target_user = target_member.user

    if action == "unban":
        await context.bot.unban_chat_member(ALLOWED_GROUP_ID, target_id, only_if_banned=True)
        await query.edit_message_text(f"{query.message.text}\n\n✅ <b>Action Taken:</b> User Unbanned.", parse_mode="HTML")
        await notify_admins(context, "User UNBAN hua hai (via Admin DM)", target_user, "unban")

    elif action == "ban":
        await context.bot.ban_chat_member(ALLOWED_GROUP_ID, target_id)
        await query.edit_message_text(f"{query.message.text}\n\n🚫 <b>Action Taken:</b> User Banned.", parse_mode="HTML")
        await notify_banned_user(context, target_id)
        await notify_admins(context, "User BAN hua hai (via Admin DM)", target_user, "ban")

    elif action == "unmute":
        await context.bot.restrict_chat_member(ALLOWED_GROUP_ID, target_id, FULL_USER_PERMISSIONS)
        await query.edit_message_text(f"{query.message.text}\n\n🔊 <b>Action Taken:</b> User Unmuted.", parse_mode="HTML")
        await notify_admins(context, "User UNMUTE hua hai (via Admin DM)", target_user, "unmute")

    elif action == "mute":
        await context.bot.restrict_chat_member(ALLOWED_GROUP_ID, target_id, RESTRICTED_PERMISSIONS)
        await query.edit_message_text(f"{query.message.text}\n\n🔇 <b>Action Taken:</b> User Muted.", parse_mode="HTML")
        await notify_admins(context, "User MUTE hua hai (via Admin DM)", target_user, "mute")


# --- AUTOMATION LOGIC ---

async def add_warn(user, chat, context: ContextTypes.DEFAULT_TYPE, reason: str):
    uid = str(user.id)
    warns_db[uid] = warns_db.get(uid, 0) + 1
    save_data(WARNS_FILE, warns_db)
    
    current_warns = warns_db[uid]
    
    if current_warns >= 4:
        await context.bot.ban_chat_member(ALLOWED_GROUP_ID, user.id)
        warns_db[uid] = 0
        save_data(WARNS_FILE, warns_db)
        
        await context.bot.send_message(chat.id, f"🚫 {user.mention_html()} ko 4 warn milne par AUTO BAN kar diya gaya hai.", parse_mode="HTML")
        await notify_banned_user(context, user.id)
        await notify_admins(context, "User AUTO-BAN hua hai (4 Warns)", user, "ban")
    else:
        await context.bot.send_message(
            chat.id, 
            f"⚠️ {user.mention_html()} Warning ({current_warns}/4)!\n<b>Reason:</b> {reason}",
            parse_mode="HTML"
        )

async def auto_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not update.message: return
    
    user = update.effective_user
    chat = update.effective_chat

    if user and user.is_bot: return
    if await is_admin(update, context): return
    if not user: return

    uid = str(user.id)
    users_db[uid] = user.full_name
    save_data(USERS_FILE, users_db)

    # Anti-Spam Check (10 msg in 15 sec)
    now = datetime.now()
    if chat.id not in spam_tracker: spam_tracker[chat.id] = {}
    if user.id not in spam_tracker[chat.id]: spam_tracker[chat.id][user.id] = []
    
    timestamps = [t for t in spam_tracker[chat.id][user.id] if now - t < timedelta(seconds=15)]
    timestamps.append(now)
    spam_tracker[chat.id][user.id] = timestamps
    
    if len(timestamps) >= 10:
        spam_tracker[chat.id][user.id] = []
        await add_warn(user, chat, context, "Spamming (10+ msg in 15 sec)")
        return

    # Anti-Night Media (1 AM to 5 AM)
    current_hour = datetime.now().hour
    if 1 <= current_hour < 5:
        if update.message.photo or update.message.video or update.message.document or update.message.audio:
            await update.message.delete()
            return

    # Banned Word Filter
    if update.message.text:
        msg_text = update.message.text.lower()
        for word in banned_words:
            if word in msg_text:
                await update.message.delete()
                await add_warn(user, chat, context, f"Banned word used: '{word}'")
                break

async def welcome_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    
    for member in update.message.new_chat_members:
        if not member.is_bot:
            await update.message.reply_text(f"👋 Welcome {member.mention_html()} group me!", parse_mode="HTML")
            
    if update.message.left_chat_member:
        member = update.message.left_chat_member
        if not member.is_bot:
            await update.message.reply_text(f"👋 Goodbye {member.full_name}!")


# --- MAIN RUNNER ---

def main():
    # Extended timeouts to prevent disconnects
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("adm", cmd_adm))
    app.add_handler(CommandHandler("bye", cmd_bye))
    app.add_handler(CommandHandler(["unban", "reinvite"], cmd_unban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("free", cmd_free))
    app.add_handler(CommandHandler("give", cmd_give))
    app.add_handler(CommandHandler(["take", "demote"], cmd_take))
    app.add_handler(CommandHandler("pin", cmd_pin))
    app.add_handler(CommandHandler("unpin", cmd_unpin))
    app.add_handler(CommandHandler("restrict", cmd_restrict_word))
    app.add_handler(CommandHandler("remove", cmd_remove_word))
    app.add_handler(CommandHandler(["words", "list"], cmd_list_words))
    app.add_handler(CommandHandler("call", cmd_call))
    app.add_handler(CommandHandler("status", cmd_status))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER, welcome_goodbye))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, auto_moderator))

    print("Bot is running successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
