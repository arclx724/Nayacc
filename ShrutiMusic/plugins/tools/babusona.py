import time
from pyrogram import Client, filters
from pyrogram.types import ChatMemberUpdated, ChatPrivileges
from pyrogram.enums import ChatMemberStatus
from config import OWNER_ID
import db

# ==================================================
# 🔐 ANTI NUKE CONFIG
# ==================================================

LIMIT = 3          # Max destructive actions allowed
TIME_FRAME = 300   # 5 minutes window

# In-RAM cache
TRAFFIC = {}


async def punish_nuker(client: Client, chat_id: int, user, count: int):
    """
    Mass action karne wale admin ko DEMOTE karta hai
    """
    try:
        await client.promote_chat_member(
            chat_id=chat_id,
            user_id=user.id,
            privileges=ChatPrivileges(
                can_manage_chat=False,
                can_delete_messages=False,
                can_manage_video_chats=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            )
        )

        await client.send_message(
            chat_id,
            (
                "🚨 **ANTI-NUKE ACTIVATED**\n\n"
                f"👤 **Admin:** {user.mention}\n"
                f"📊 **Actions:** {count}/{LIMIT}\n"
                "❌ **Result:** Admin DEMOTED\n\n"
                "🛡️ Group secured successfully."
            )
        )

    except Exception:
        await client.send_message(
            chat_id,
            (
                "⚠️ **SECURITY ALERT**\n\n"
                f"{user.mention} triggered anti-nuke,\n"
                "but I can't demote them (rank issue)."
            )
        )


# ==================================================
# 🛡️ MAIN ANTI-NUKE WATCHER
# ==================================================

@app.on_chat_member_updated(filters.group, group=5)
async def anti_nuke_watcher(client: Client, update: ChatMemberUpdated):

    chat = update.chat

    # Safety: actor missing
    if not update.from_user:
        return
    actor = update.from_user

    # Safely get target
    if update.new_chat_member:
        target = update.new_chat_member.user
    elif update.old_chat_member:
        target = update.old_chat_member.user
    else:
        return

    # Ignore bot & owner
    if actor.id in (client.me.id, OWNER_ID):
        return

    # Whitelist check
    if await db.is_user_whitelisted(chat.id, actor.id):
        return

    old_status = (
        update.old_chat_member.status
        if update.old_chat_member
        else ChatMemberStatus.LEFT
    )
    new_status = (
        update.new_chat_member.status
        if update.new_chat_member
        else ChatMemberStatus.LEFT
    )

    action_detected = False

    # 🚫 Kick / Ban detection
    if new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
        if actor.id != target.id:
            action_detected = True

    # 🚫 Mass promotion detection
    elif (
        old_status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
        and new_status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    ):
        action_detected = True

    if not action_detected:
        return

    # ==================================================
    # ⏱️ RATE LIMIT CHECK
    # ==================================================

    now = time.time()

    TRAFFIC.setdefault(chat.id, {})
    TRAFFIC[chat.id].setdefault(actor.id, [])

    TRAFFIC[chat.id][actor.id].append(now)

    # Remove old actions
    TRAFFIC[chat.id][actor.id] = [
        t for t in TRAFFIC[chat.id][actor.id]
        if now - t < TIME_FRAME
    ]

    count = len(TRAFFIC[chat.id][actor.id])

    # 🚨 Threshold crossed
    if count >= LIMIT:
        await punish_nuker(client, chat.id, actor, count)
        TRAFFIC[chat.id][actor.id].clear()
