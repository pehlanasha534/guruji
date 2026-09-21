import logging
import json
import os
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

CODE_TOKEN = "8667960061:AAFbHng3Z8hmWOE0C2r6MS-YtMnv4B8VFIw"
TOKEN = os.getenv("TOKEN", CODE_TOKEN)
if not TOKEN:
    raise ValueError("TOKEN nahi mila!")

ALLOWED_GROUP_ID = -1004413547137
IST = timezone(timedelta(hours=5, minutes=30))

USERS_FILE = "users.json"
BANNED_WORDS_FILE = "banned_words.json"
WARNS_FILE = "warns.json"

def load_data(filename, default):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump(default, f)
        return default
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except:
        return default

def save_data(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

users_db = load_data(USERS_FILE, {})
banned_words = load_data(BANNED_WORDS_FILE, [])
warns_db = load_data(WARNS_FILE, {})
spam_tracker = {}

FULL_USER_PERMISSIONS = ChatPermissions(
    can_send_messages=True, can_send_audios=True, can_send_documents=True,
    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
    can_add_web_page_previews=True
)
RESTRICTED_PERMISSIONS = ChatPermissions(can_send_messages=False)

def is_allowed_group(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == ALLOWED_GROUP_ID)

async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    elif context.args:
        try:
            user_id = int(context.args[0].replace("@", ""))
            member = await context.bot.get_chat_member(ALLOWED_GROUP_ID, user_id)
            return member.user
        except:
            pass
    return None

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    if update.effective_message and update.effective_message.sender_chat:
        if update.effective_message.sender_chat.id == ALLOWED_GROUP_ID:
            return True
    uid = user_id or (update.effective_user.id if update.effective_user else None)
    if not uid:
        return False
    try:
        m = await context.bot.get_chat_member(ALLOWED_GROUP_ID, uid)
        return m.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"is_admin error: {e}")
        return False

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, action_text: str, target_user, buttons_type: str = "ban"):
    try:
        admins = await context.bot.get_chat_administrators(ALLOWED_GROUP_ID)
    except Exception as e:
        logger.error(f"get_admins failed: {e}")
        return
    tid = target_user.id
    kb = []
    if buttons_type == "ban":
        kb = [[InlineKeyboardButton("Unban", callback_data=f"adm_unban_{tid}"), InlineKeyboardButton("Ignore", callback_data="adm_ignore")]]
    elif buttons_type == "mute":
        kb = [[InlineKeyboardButton("Unmute", callback_data=f"adm_unmute_{tid}"), InlineKeyboardButton("Ignore", callback_data="adm_ignore")]]
    elif buttons_type == "unban":
        kb = [[InlineKeyboardButton("Ban Again", callback_data=f"adm_ban_{tid}"), InlineKeyboardButton("Ignore", callback_data="adm_ignore")]]
    elif buttons_type == "unmute":
        kb = [[InlineKeyboardButton("Mute Again", callback_data=f"adm_mute_{tid}"), InlineKeyboardButton("Ignore", callback_data="adm_ignore")]]
    markup = InlineKeyboardMarkup(kb) if kb else None
    msg = f"🔔 <b>Admin Update</b>\n\n👤 {target_user.mention_html()} (<code>{tid}</code>)\n⚡ <b>{action_text}</b>"
    for a in admins:
        if a.user.is_bot:
            continue
        try:
            await context.bot.send_message(a.user.id, msg, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            logger.warning(f"DM failed to {a.user.id}: {e}")

async def notify_banned_user(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        await context.bot.send_message(user_id, "AAP HAMARE GROUP SE BAN HUE HAI AGAR GALATFEHMI HAI TO CONTACT - @epic_ind\nTHANK YOU 🌸")
    except:
        pass

async def cmd_adm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    msg_text = " ".join(context.args) if context.args else "Attention Admins!"
    admins = await update.effective_chat.get_administrators()
    mentions = [a.user.mention_html() for a in admins if not a.user.is_bot]
    await update.message.reply_text(f"🚨 <b>Admin Call:</b> {msg_text}\n\n" + " ".join(mentions), parse_mode="HTML")

async def cmd_bye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text("Reply karke /bye use karo.")
        return
    await context.bot.ban_chat_member(ALLOWED_GROUP_ID, target.id)
    kb = [[InlineKeyboardButton("Unban User", callback_data=f"adm_unban_{target.id}")]]
    await update.message.reply_text(f"🚫 {target.mention_html()} ban.", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    await notify_banned_user(context, target.id)
    await notify_admins(context, "User BAN hua hai", target, "ban")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    target = await get_target_user(update, context)
    if not target: return
    await context.bot.unban_chat_member(ALLOWED_GROUP_ID, target.id, only_if_banned=True)
    await update.message.reply_text(f"✅ {target.mention_html()} unban.", parse_mode="HTML")
    await notify_admins(context, "User UNBAN hua hai", target, "unban")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    target = await get_target_user(update, context)
    if not target: return
    await context.bot.restrict_chat_member(ALLOWED_GROUP_ID, target.id, RESTRICTED_PERMISSIONS)
    await update.message.reply_text(f"🔇 {target.mention_html()} mute.", parse_mode="HTML")
    await notify_admins(context, "User MUTE hua hai", target, "mute")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    target = await get_target_user(update, context)
    if not target: return
    await context.bot.restrict_chat_member(ALLOWED_GROUP_ID, target.id, FULL_USER_PERMISSIONS)
    await update.message.reply_text(f"🔊 {target.mention_html()} unmute.", parse_mode="HTML")
    await notify_admins(context, "User UNMUTE hua hai", target, "unmute")

async def cmd_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text("Reply karke /free use karo.")
        return
    warns_db[str(target.id)] = 0
    save_data(WARNS_FILE, warns_db)
    await update.message.reply_text(f"🕊️ {target.mention_html()} warns reset (0/4)!", parse_mode="HTML")

async def cmd_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    target = await get_target_user(update, context)
    if not target: return
    await context.bot.promote_chat_member(ALLOWED_GROUP_ID, target.id, can_delete_messages=True, can_restrict_members=True, can_pin_messages=True)
    await update.message.reply_text(f"👑 {target.mention_html()} ab Admin!", parse_mode="HTML")

async def cmd_take(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    target = await get_target_user(update, context)
    if not target: return
    await context.bot.promote_chat_member(ALLOWED_GROUP_ID, target.id, can_delete_messages=False, can_restrict_members=False, can_pin_messages=False)
    await update.message.reply_text(f"📉 {target.mention_html()} se admin liya.", parse_mode="HTML")

async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    if update.message.reply_to_message:
        await context.bot.pin_chat_message(ALLOWED_GROUP_ID, update.message.reply_to_message.message_id)
        await update.message.reply_text("📌 Pin done.")

async def cmd_unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    await context.bot.unpin_chat_message(ALLOWED_GROUP_ID)
    await update.message.reply_text("📌 Unpin done.")

async def cmd_restrict_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    if not context.args: return
    w = context.args[0].lower()
    if w not in banned_words:
        banned_words.append(w); save_data(BANNED_WORDS_FILE, banned_words)
        await update.message.reply_text(f"🚫 '{w}' banned.")

async def cmd_remove_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    if not context.args: return
    w = context.args[0].lower()
    if w in banned_words:
        banned_words.remove(w); save_data(BANNED_WORDS_FILE, banned_words)
        await update.message.reply_text(f"✅ '{w}' removed.")

async def cmd_list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    if not banned_words:
        await update.message.reply_text("📝 Koi banned word nahi.")
        return
    text = "📝 <b>Banned Words:</b>\n" + "\n".join([f"• <code>{w}</code>" for w in banned_words])
    kb = [[InlineKeyboardButton(f"❌ Remove '{w}'", callback_data=f"delword_{w}")] for w in banned_words]
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def cmd_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    if not await is_admin(update, context): return
    msg_text = " ".join(context.args) if context.args else "Announcement!"
    uids = list(users_db.keys())[:100]
    mentions = [f'<a href="tg://user?id={uid}">{users_db[uid]}</a>' for uid in uids]
    for i in range(0, len(mentions), 50):
        await update.message.reply_text(f"📢 <b>{msg_text}</b>\n\n" + " ".join(mentions[i:i+50]), parse_mode="HTML")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    target = await get_target_user(update, context) or update.effective_user
    wc = warns_db.get(str(target.id), 0)
    await update.message.reply_text(f"👤 <b>User:</b> {target.mention_html()}\nID: <code>{target.id}</code>\nWarns: <b>{wc}/4</b>", parse_mode="HTML")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    admin_id = query.from_user.id
    if not await is_admin(update, context, admin_id):
        await query.answer("Aap admin nahi ho!", show_alert=True)
        return
    await query.answer()
    if data == "adm_ignore":
        await query.edit_message_text(f"{query.message.text}\n\n✅ Ignored.", parse_mode="HTML")
        return
    if data.startswith("delword_"):
        word = data[len("delword_"):]
        if word in banned_words:
            banned_words.remove(word); save_data(BANNED_WORDS_FILE, banned_words)
            await query.edit_message_text("✅ Word removed.")
        return
    try:
        _, action, tid_str = data.split("_", 2)
        tid = int(tid_str)
        target_user = (await context.bot.get_chat_member(ALLOWED_GROUP_ID, tid)).user
    except:
        return
    if action == "unban":
        await context.bot.unban_chat_member(ALLOWED_GROUP_ID, tid, only_if_banned=True)
        await query.edit_message_text("✅ User Unbanned.", parse_mode="HTML")
        await notify_admins(context, "User UNBAN (via DM)", target_user, "unban")
    elif action == "ban":
        await context.bot.ban_chat_member(ALLOWED_GROUP_ID, tid)
        await query.edit_message_text("🚫 User Banned.", parse_mode="HTML")
        await notify_banned_user(context, tid)
        await notify_admins(context, "User BAN (via DM)", target_user, "ban")
    elif action == "unmute":
        await context.bot.restrict_chat_member(ALLOWED_GROUP_ID, tid, FULL_USER_PERMISSIONS)
        await query.edit_message_text("🔊 User Unmuted.", parse_mode="HTML")
        await notify_admins(context, "User UNMUTE (via DM)", target_user, "unmute")
    elif action == "mute":
        await context.bot.restrict_chat_member(ALLOWED_GROUP_ID, tid, RESTRICTED_PERMISSIONS)
        await query.edit_message_text("🔇 User Muted.", parse_mode="HTML")
        await notify_admins(context, "User MUTE (via DM)", target_user, "mute")

async def add_warn(user, chat, context: ContextTypes.DEFAULT_TYPE, reason: str):
    uid = str(user.id)
    warns_db[uid] = warns_db.get(uid, 0) + 1
    save_data(WARNS_FILE, warns_db)
    c = warns_db[uid]
    if c >= 4:
        await context.bot.ban_chat_member(ALLOWED_GROUP_ID, user.id)
        warns_db[uid] = 0; save_data(WARNS_FILE, warns_db)
        await context.bot.send_message(chat.id, f"🚫 {user.mention_html()} AUTO BAN (4/4).", parse_mode="HTML")
        await notify_banned_user(context, user.id)
        await notify_admins(context, "AUTO-BAN (4 Warns)", user, "ban")
    else:
        await context.bot.send_message(chat.id, f"⚠️ {user.mention_html()} Warning ({c}/4)!\n<b>Reason:</b> {reason}", parse_mode="HTML")

async def auto_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update) or not update.message: return
    user = update.effective_user; chat = update.effective_chat
    if not user or user.is_bot: return
    if await is_admin(update, context): return
    users_db[str(user.id)] = user.full_name; save_data(USERS_FILE, users_db)
    now = datetime.now(IST)
    lst = spam_tracker.get(user.id, [])
    lst = [t for t in lst if now - t < timedelta(seconds=15)]
    lst.append(now); spam_tracker[user.id] = lst
    if len(lst) >= 10:
        spam_tracker[user.id] = []
        await add_warn(user, chat, context, "Spamming (10+ msg in 15 sec)")
        return
    h = now.hour
    if 1 <= h < 5:
        if update.message.photo or update.message.video or update.message.document or update.message.audio or update.message.voice or update.message.video_note:
            try: await update.message.delete()
            except: pass
            return
    if update.message.text:
        txt = update.message.text.lower()
        for w in banned_words:
            if w in txt:
                try: await update.message.delete()
                except: pass
                await add_warn(user, chat, context, f"Banned word: '{w}'")
                break

async def welcome_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update): return
    for m in update.message.new_chat_members:
        if not m.is_bot:
            await update.message.reply_text(f"👋 Welcome {m.mention_html()}!", parse_mode="HTML")
    if update.message.left_chat_member and not update.message.left_chat_member.is_bot:
        await update.message.reply_text(f"👋 Goodbye {update.message.left_chat_member.full_name}!")

def main():
    app = ApplicationBuilder().token(TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).pool_timeout(30).build()
    app.add_handler(CommandHandler("adm", cmd_adm))
    app.add_handler(CommandHandler("bye", cmd_bye))
    app.add_handler(CommandHandler(["unban","reinvite"], cmd_unban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("free", cmd_free))
    app.add_handler(CommandHandler("give", cmd_give))
    app.add_handler(CommandHandler(["take","demote"], cmd_take))
    app.add_handler(CommandHandler("pin", cmd_pin))
    app.add_handler(CommandHandler("unpin", cmd_unpin))
    app.add_handler(CommandHandler("restrict", cmd_restrict_word))
    app.add_handler(CommandHandler("remove", cmd_remove_word))
    app.add_handler(CommandHandler(["words","list"], cmd_list_words))
    app.add_handler(CommandHandler("call", cmd_call))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER, welcome_goodbye))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, auto_moderator))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
