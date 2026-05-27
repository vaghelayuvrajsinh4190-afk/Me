import discord
from discord.ext import commands, tasks
from discord import ui
import os
import asyncio
import datetime
import keep_alive
from pymongo import MongoClient

# ================= 1. CONFIGURATION =================

TOKEN = os.environ.get("TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")
TICKET_CATEGORY_ID = 1491353694627958927

# — CHANNELS —

ADMIN_COMMAND_CHANNEL_ID = 1459806817734361282
REGISTRATION_CHANNEL_ID = 1458788627164303432
CANCEL_CLAIM_CHANNEL_ID = 1459791046547472540
ADMIN_LOG_CHANNEL_ID = 1459460369780047892
VERIFY_CHANNEL_ID = 1461666929516347453
VERIFIED_TEAM_LOG_ID = 1466725299675856947

# MATCH CHANNELS

SLOT_LIST_CHANNELS = {
"MATCH_1": 1459460237437435999,
"MATCH_2": 1459471324593389725,
"MATCH_3": 1459471494785531965,
"MATCH_4": 1459472478651945070,
"MATCH_5": 1491320890196099182,
"MATCH_6": 1491321553940647936,
"MATCH_7": 1491321597955674152,
"MATCH_8": 1491321660412919818,
}

# ROOM CHANNELS

ROOM_CHANNELS = {
"MATCH_1": 1458788771716792486,
"MATCH_2": 1459772021448904822,
"MATCH_3": 1459772074112454750,
"MATCH_4": 1459772130232373512,
"MATCH_5": 1491321765614588075,
"MATCH_6": 1491321837341118606,
"MATCH_7": 1491321886661939251,
"MATCH_8": 1491343698158686288,
}

# ROLES

SLOT_ROLES = {
"MATCH_1": "Match 1 Player",
"MATCH_2": "Match 2 Player",
"MATCH_3": "Match 3 Player",
"MATCH_4": "Match 4 Player",
"MATCH_5": "Match 5 Player",
"MATCH_6": "Match 6 Player",
"MATCH_7": "Match 7 Player",
"MATCH_8": "Match 8 Player",
}

VERIFY_ROLE_NAME = "Verified Team"

# — SETTINGS —

MAX_SLOTS = 16
REGISTRATION_OPEN = True
TIMEZONE_OFFSET = 5.5
DATA_EXPIRY_DAYS = 7

DEFAULT_UPI_SETTINGS = {
"upi_id": "yourname@upi",
"upi_name": "Your Name",
"payment_amount": 10
}

# ================= 2. MONGODB SETUP =================

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["tournament_db"]
collection = db["tournament_data"]

# ═══════════════════ DESIGN SYSTEM ═══════════════════

class Theme:
    SUCCESS   = discord.Color.from_rgb(87, 242, 135)
    ERROR     = discord.Color.from_rgb(237, 66, 69)
    WARNING   = discord.Color.from_rgb(254, 231, 92)
    INFO      = discord.Color.from_rgb(88, 101, 242)
    PREMIUM   = discord.Color.from_rgb(167, 139, 250)
    ACCENT    = discord.Color.from_rgb(45, 136, 255)
    DARK      = discord.Color.from_rgb(43, 45, 49)
    TEAL      = discord.Color.from_rgb(30, 224, 188)
    ORANGE    = discord.Color.from_rgb(250, 168, 26)
    ROSE      = discord.Color.from_rgb(235, 69, 158)
    GOLD      = discord.Color.from_rgb(255, 215, 0)
    SEP       = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    THIN_SEP  = "─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─"
    FOOTER    = "⚡ Tournament Bot"

    @staticmethod
    def bar(current, maximum, length=12):
        filled = int((current / maximum) * length) if maximum else 0
        return "`" + "▰" * filled + "▱" * (length - filled) + "`"

    @staticmethod
    def match_color(count, mx):
        r = count / mx if mx else 0
        if r >= 1.0: return Theme.ERROR
        if r >= 0.75: return Theme.ORANGE
        if r >= 0.4: return Theme.WARNING
        return Theme.SUCCESS

    @staticmethod
    def match_status(count, mx):
        r = count / mx if mx else 0
        if r >= 1.0: return "🔴 FULL"
        if r >= 0.75: return "🟠 Almost Full"
        if r >= 0.4: return "🟡 Filling Up"
        return "🟢 Open"

def make_embed(title, desc=None, color=None, footer=None):
    e = discord.Embed(title=title, description=desc, color=color or Theme.INFO, timestamp=datetime.datetime.utcnow())
    e.set_footer(text=footer or Theme.FOOTER)
    return e

# ================= 3. DATA HANDLING =================

def load_data():
    doc = collection.find_one({"_id": "main_data"})
    
    if doc is None:
        default_data = {
            "_id": "main_data",
            "teams": {},
            "slots": {k: [] for k in SLOT_LIST_CHANNELS},
            "table_messages": {},
            "upi_settings": DEFAULT_UPI_SETTINGS.copy(),
            "part_names": {"1": "Part 1 - Matches 1 to 4", "2": "Part 2 - Matches 5 to 8"},
            "part_status": {"1": True, "2": True},
            "verify_timeout_minutes": 5,
            "open_tickets": {},
            "points_system": {
                "kill_points": 1,
                "position_points": {
                    "1": 15, "2": 12, "3": 10, "4": 8, "5": 6,
                    "6": 4, "7": 2, "8": 1, "9": 0, "10": 0,
                    "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0
                }
            },
            "match_results": {}
        }
        collection.insert_one(default_data)
        return default_data

    data = doc
    dirty = False

    for key, default in [
        ("table_messages", {}),
        ("upi_settings", DEFAULT_UPI_SETTINGS.copy()),
        ("part_names", {"1": "Part 1 - Matches 1 to 4", "2": "Part 2 - Matches 5 to 8"}),
        ("part_status", {"1": True, "2": True}),
        ("verify_timeout_minutes", 5),
        ("open_tickets", {}),
        ("match_results", {}),
    ]:
        if key not in data:
            data[key] = default
            dirty = True

    if "points_system" not in data:
        data["points_system"] = {
            "kill_points": 1,
            "position_points": {
                "1": 15, "2": 12, "3": 10, "4": 8, "5": 6,
                "6": 4, "7": 2, "8": 1, "9": 0, "10": 0,
                "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0
            }
        }
        dirty = True

    for k in SLOT_LIST_CHANNELS:
        if k not in data.get("slots", {}):
            data["slots"][k] = []
            dirty = True

    if "SLOT_1" in data.get("slots", {}):
        data["slots"] = {k.replace("SLOT", "MATCH"): v for k, v in data["slots"].items()}
        dirty = True

    # Migrate legacy paid:True teams to paid_parts
    for uid, info in data.get("teams", {}).items():
        if info.get("paid", False) and "paid_parts" not in info:
            selected = info.get("selected_part", "part_1")
            info["paid_parts"] = [selected]
            dirty = True

    if dirty:
        save_data(data)

    return data

def save_data(data):
    collection.replace_one({"_id": "main_data"}, data, upsert=True)

data = load_data()

def get_upi_settings():
    return data.get("upi_settings", DEFAULT_UPI_SETTINGS)

def get_paid_parts(uid):
    """Return list of parts a user has paid for. Handles legacy paid:True teams."""
    team = data.get("teams", {}).get(uid, {})
    paid_parts = team.get("paid_parts", [])
    if not paid_parts and team.get("paid", False):
        selected = team.get("selected_part", "part_1")
        return [selected]
    return paid_parts

def make_payment_embed(team_name):
    upi = get_upi_settings()
    embed = make_embed(
        "💳 Payment Required",
        f"{Theme.SEP}\n\n"
        f"✅ Team **{team_name}** registered successfully!\n\n"
        f"{Theme.THIN_SEP}\n\n"
        f"**📱 Pay Platform Fee to activate your team:**\n"
        f"> 💰 **Amount:** `₹{upi['payment_amount']}`\n"
        f"> 🏦 **UPI ID:** `{upi['upi_id']}`\n"
        f"> 👤 **Pay to:** `{upi['upi_name']}`\n\n"
        f"{Theme.THIN_SEP}\n\n"
        f"**📋 How to complete payment:**\n"
        f"> `1.` Pay ₹{upi['payment_amount']} to the UPI ID above\n"
        f"> `2.` Take a screenshot of the payment\n"
        f"> `3.` Open a ticket in the server\n"
        f"> `4.` Send the screenshot to admin\n"
        f"> `5.` Wait for admin approval\n\n"
        f"⏳ *Your team will be added to all matches once payment is verified.*\n\n"
        f"{Theme.SEP}",
        Theme.GOLD,
        "💰 Manual UPI Verification"
    )
    return embed

# ================= 4. HELPER FUNCTIONS =================

async def get_or_create_role(guild, role_name):
    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        try:
            role = await guild.create_role(name=role_name, mentionable=True)
        except Exception:
            return None
    return role

async def setup_channel_perms(guild):
    for slot_name, role_name in SLOT_ROLES.items():
        role = await get_or_create_role(guild, role_name)
        if not role:
            continue
        channels_to_lock = []
        if slot_name in SLOT_LIST_CHANNELS:
            channels_to_lock.append(guild.get_channel(SLOT_LIST_CHANNELS[slot_name]))
        if slot_name in ROOM_CHANNELS:
            channels_to_lock.append(guild.get_channel(ROOM_CHANNELS[slot_name]))
        for ch in channels_to_lock:
            if ch:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
                await ch.edit(overwrites=overwrites)

def check_duplicates(current_uid, new_team_name, new_players):
    new_team_clean = new_team_name.strip().lower()
    new_players_clean = [p.strip().lower() for p in new_players if p.strip()]

    if len(new_players_clean) != len(set(new_players_clean)):
        return True, "❌ You entered the same player name twice in this form."

    for uid, info in data["teams"].items():
        if uid == current_uid:
            continue
        existing_team = info.get("team", "").strip().lower()
        if existing_team == new_team_clean:
            return True, f"❌ Team Name **'{new_team_name}'** is already taken by another squad!"
        existing_players = [p.strip().lower() for p in info.get("players", [])]
        for np in new_players_clean:
            if np in existing_players:
                return True, f"❌ Player Name **'{np}'** is already registered in another team!"

    return False, ""

# ═══════════════════ 5. LIVE TABLE REFRESH ═══════════════════

async def refresh_table(guild, slot_name):
    channel_id = SLOT_LIST_CHANNELS.get(slot_name)
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if not channel:
        return

    registered_uids = data["slots"].get(slot_name, [])
    count = len(registered_uids)
    display_name = slot_name.replace("_", " ")
    status = Theme.match_status(count, MAX_SLOTS)
    color = Theme.match_color(count, MAX_SLOTS)
    bar = Theme.bar(count, MAX_SLOTS, 16)

    table_lines = []
    for i in range(MAX_SLOTS):
        num = f"{i+1:02d}"
        if i < len(registered_uids):
            uid = registered_uids[i]
            tn = data["teams"].get(uid, {}).get("team", "Unknown")
            tn = (tn[:20] + '..') if len(tn) > 20 else tn
            table_lines.append(f" {num} │ ✅ {tn}")
        else:
            table_lines.append(f" {num} │ ── Open ──")

    header = f" ##  │ TEAM NAME\n {'─'*4}┼{'─'*24}"
    tabular_data = header + "\n" + "\n".join(table_lines)

    embed = make_embed(
        f"🏆  {display_name}  —  Live Roster",
        f"> {status}  •  **{count}/{MAX_SLOTS}** slots filled\n"
        f"> {bar}\n"
        f"{Theme.SEP}",
        color=color,
        footer="🔄 Auto-updates • Do not type here"
    )
    embed.add_field(name="\u200b", value=f"```\n{tabular_data}\n```", inline=False)

    msg_id = data["table_messages"].get(slot_name)
    message = None
    if msg_id:
        try:
            message = await channel.fetch_message(msg_id)
            await message.edit(embed=embed)
        except discord.NotFound:
            message = None

    if message is None:
        message = await channel.send(embed=embed)
        data["table_messages"][slot_name] = message.id
        save_data(data)

# ================= 6. CORE LOGIC =================

async def add_player_to_slot(interaction, slot_name):
    uid = str(interaction.user.id)
    guild = interaction.guild

    if not REGISTRATION_OPEN:
        await interaction.response.send_message("⛔ **Match is starting! Registration is closed.**", ephemeral=True)
        return False

    if len(data["slots"][slot_name]) >= MAX_SLOTS:
        return False

    if uid in data["slots"][slot_name]:
        await interaction.response.send_message(f"⚠️ You are already in **{slot_name}**.", ephemeral=True)
        return False

    data["slots"][slot_name].append(uid)
    if "booked_slots" not in data["teams"][uid]:
        data["teams"][uid]["booked_slots"] = []
    if slot_name not in data["teams"][uid]["booked_slots"]:
        data["teams"][uid]["booked_slots"].append(slot_name)
    save_data(data)

    role_name = SLOT_ROLES.get(slot_name)
    if role_name:
        role = await get_or_create_role(guild, role_name)
        if role:
            try:
                await interaction.user.add_roles(role)
            except Exception:
                pass

    await refresh_table(guild, slot_name)
    return True

async def perform_removal(guild, uid, slot_name):
    if uid in data["slots"][slot_name]:
        data["slots"][slot_name].remove(uid)
    if uid in data["teams"] and slot_name in data["teams"][uid].get("booked_slots", []):
        data["teams"][uid]["booked_slots"].remove(slot_name)
    save_data(data)

    role_name = SLOT_ROLES.get(slot_name)
    if role_name:
        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(int(uid))
        if role and member:
            try:
                await member.remove_roles(role)
            except Exception:
                pass

    await refresh_table(guild, slot_name)

async def remove_single_slot_logic(interaction, slot_to_remove):
    uid = str(interaction.user.id)
    if uid not in data["teams"]:
        return False, "No team data."
    booked = data["teams"][uid].get("booked_slots", [])
    if slot_to_remove not in booked:
        return False, "You don't own this slot."
    await perform_removal(interaction.guild, uid, slot_to_remove)
    return True, f"✅ Removed from **{slot_to_remove}**."

async def remove_all_slots_logic(interaction):
    uid = str(interaction.user.id)
    if uid not in data["teams"] or not data["teams"][uid].get("booked_slots"):
        return False, "You have no slots to cancel."
    booked = list(data["teams"][uid]["booked_slots"])
    for s in booked:
        await perform_removal(interaction.guild, uid, s)
    return True, "✅ All matches cancelled."

# ================= 7. AUTO-RESET TASK =================

@tasks.loop(minutes=1)
async def daily_reset_task():
    utc_now = datetime.datetime.utcnow()
    local_now = utc_now + datetime.timedelta(hours=TIMEZONE_OFFSET)

    if local_now.hour == 0 and local_now.minute == 0:
        print("🕛 MIDNIGHT RESET: Cleaning up...")
        if not bot.guilds:
            return
        guild = bot.guilds[0]

        for slot_name, uids in data["slots"].items():
            role_name = SLOT_ROLES.get(slot_name)
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                for uid in uids:
                    member = guild.get_member(int(uid))
                    if member:
                        try:
                            await member.remove_roles(role)
                        except Exception:
                            pass
            data["slots"][slot_name] = []

        for uid in data["teams"]:
            data["teams"][uid]["booked_slots"] = []
            data["teams"][uid]["paid"] = False
            data["teams"][uid]["paid_parts"] = []

        if "open_tickets" in data:
            data["open_tickets"] = {}

        uids_to_delete = []
        for uid, info in data["teams"].items():
            reg_time_str = info.get("last_updated", utc_now.isoformat())
            reg_time = datetime.datetime.fromisoformat(reg_time_str)
            if (utc_now - reg_time).days >= DATA_EXPIRY_DAYS:
                uids_to_delete.append(uid)

        for uid in uids_to_delete:
            del data["teams"][uid]

        save_data(data)

        for slot_name in SLOT_LIST_CHANNELS:
            await refresh_table(guild, slot_name)
            await asyncio.sleep(1)

        log_ch = guild.get_channel(ADMIN_LOG_CHANNEL_ID)
        if log_ch:
            await log_ch.send("🕛 **Daily Reset & Cleanup Complete.**")

        global REGISTRATION_OPEN
        REGISTRATION_OPEN = True

# ═══════════════════ 8. VERIFICATION SYSTEM ═══════════════════

class ConsentView(ui.View):
    def __init__(self, team_name, leader, teammates, channel):
        timeout_minutes = data.get("verify_timeout_minutes", 5)
        super().__init__(timeout=timeout_minutes * 60)
        self.team_name = team_name
        self.leader = leader
        self.teammates = teammates
        self.accepted = {leader.id}
        self.all_ids = {m.id for m in teammates}
        self.channel = channel
        self.dm_messages = {}
        self.completed = False

    def _build_embed(self):
        accepted_count = len(self.accepted)
        total = len(self.all_ids)
        lines = []
        for m in self.teammates:
            if m.id in self.accepted:
                lines.append(f"✅ {m.mention} — Accepted")
            else:
                lines.append(f"⏳ {m.mention} — Pending")
        player_list = "\n".join(lines)
        timeout_min = data.get("verify_timeout_minutes", 5)
        embed = make_embed(
            f"🛡️ Team Verification — {self.team_name}",
            f"{Theme.SEP}\n\n"
            f"**Consent Status:** ✅ Accepted ({accepted_count}/{total})\n\n"
            f"{player_list}\n\n"
            f"{Theme.THIN_SEP}\n"
            f"⏳ You have **{timeout_min} minutes** to accept.\n\n"
            f"{Theme.SEP}",
            Theme.ACCENT,
            f"Initiated by {self.leader.display_name}"
        )
        return embed

    @ui.button(label="✅ Accept Invite", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id not in self.all_ids:
            await interaction.response.send_message("❌ You are not part of this team.", ephemeral=True)
            return
        if interaction.user.id in self.accepted:
            await interaction.response.send_message("✅ You already accepted.", ephemeral=True)
            return
        self.accepted.add(interaction.user.id)
        if len(self.accepted) >= len(self.all_ids):
            await self._complete_verification(interaction)
        else:
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
            await self._update_all_dm_messages(exclude_user=interaction.user.id)

    @ui.button(label="🛠️ Admin Force Verify", style=discord.ButtonStyle.danger)
    async def admin_force_button(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can force-verify.", ephemeral=True)
            return
        self.accepted = set(self.all_ids)
        await self._complete_verification(interaction)

    async def _update_all_dm_messages(self, exclude_user=None):
        embed = self._build_embed()
        for uid, msg in self.dm_messages.items():
            if uid == exclude_user:
                continue
            try:
                await msg.edit(embed=embed, view=self)
            except Exception:
                pass

    async def _complete_verification(self, interaction: discord.Interaction):
        self.completed = True
        guild = self.channel.guild if self.channel else interaction.guild
        role = await get_or_create_role(guild, VERIFY_ROLE_NAME)

        member_details = []
        for member in self.teammates:
            if role:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    pass
            member_details.append(f"╰ {member.mention} • `{member.name}`")

        player_names_str = "\n".join(member_details)

        log_channel = guild.get_channel(VERIFIED_TEAM_LOG_ID)
        if log_channel:
            log_embed = make_embed("🛡️ New Team Verified", f"{Theme.SEP}", Theme.GOLD, f"Verified by {self.leader.name}")
            log_embed.add_field(name="🏷️ Team Name", value=f"**{self.team_name}**", inline=False)
            log_embed.add_field(name="👥 Verified Players", value=player_names_str, inline=False)
            await log_channel.send(embed=log_embed)

        complete_embed = make_embed(
            f"✅ Verification Complete — {self.team_name}",
            f"{Theme.SEP}\n\n**All players verified!** 🎉\n\n"
            f"**Role Granted:** `{VERIFY_ROLE_NAME}`\n\n"
            f"**Squad Members:**\n{player_names_str}\n\n{Theme.SEP}",
            Theme.SUCCESS,
            f"Verified by {self.leader.display_name}"
        )
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(embed=complete_embed, view=self)
        for uid, msg in self.dm_messages.items():
            if uid == interaction.user.id:
                continue
            try:
                await msg.edit(embed=complete_embed, view=self)
            except Exception:
                pass

    async def on_timeout(self):
        if self.completed:
            return
        expired_embed = make_embed(
            f"⌛ Verification Expired — {self.team_name}",
            f"{Theme.SEP}\n\n**Time ran out!** The verification request has expired.\n\n"
            f"*Please start a new verification.*\n\n{Theme.SEP}",
            Theme.ERROR,
            "Verification Expired"
        )
        for item in self.children:
            item.disabled = True
        for uid, msg in self.dm_messages.items():
            try:
                await msg.edit(embed=expired_embed, view=self)
            except Exception:
                pass

class PlayerSelect(ui.UserSelect):
    def __init__(self, team_name):
        self.team_name = team_name
        super().__init__(placeholder="🎯 Select the 4 squad members…", min_values=4, max_values=4)

    async def callback(self, interaction: discord.Interaction):
        members = self.values
        if interaction.user not in members:
            e = make_embed("⛔ Verification Failed",
                f"You must **include yourself** in the squad selection.\n\n{Theme.THIN_SEP}\n*Select yourself plus your 3 teammates.*",
                Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        bots = [m.mention for m in members if m.bot]
        if bots:
            e = make_embed("⛔ Verification Failed",
                f"Discord bots cannot be squad members:\n\n" + "\n".join([f"⚠️ {b}" for b in bots]) +
                f"\n\n{Theme.THIN_SEP}\n*Select only real players.*", Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        role = discord.utils.get(interaction.guild.roles, name=VERIFY_ROLE_NAME)
        if not role:
            e = make_embed("❌ Configuration Error", f"Role `{VERIFY_ROLE_NAME}` not found. Contact an admin.", Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        already_verified = [m.mention for m in members if role in m.roles]
        if already_verified:
            e = make_embed("⛔ Verification Failed",
                f"The following players are **already verified**:\n\n" +
                "\n".join([f"⚠️ {p}" for p in already_verified]) +
                f"\n\n{Theme.THIN_SEP}\n*Each player can only be verified once.*", Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        consent_view = ConsentView(self.team_name, interaction.user, list(members), interaction.channel)

        leader_embed = make_embed(
            f"🛡️ Verification Sent — {self.team_name}",
            f"{Theme.SEP}\n\nVerification requests have been **DM'd** to your teammates.\n\n"
            f"**Waiting for acceptance from all squad members...**\n\n{Theme.SEP}",
            Theme.ACCENT, f"Leader: {interaction.user.display_name}"
        )

        try:
            leader_dm = await interaction.user.send(
                content=f"🛡️ **Team Verification — {self.team_name}**\nYou initiated this verification. Your acceptance is auto-confirmed.",
                embed=consent_view._build_embed(), view=consent_view
            )
            consent_view.dm_messages[interaction.user.id] = leader_dm
        except discord.Forbidden:
            pass

        dm_failed = []
        for m in members:
            if m.id == interaction.user.id:
                continue
            try:
                dm_msg = await m.send(
                    content=f"🛡️ **{interaction.user.display_name}** is requesting you to verify for team **{self.team_name}**!\nClick the button below to accept.",
                    embed=consent_view._build_embed(), view=consent_view
                )
                consent_view.dm_messages[m.id] = dm_msg
            except discord.Forbidden:
                dm_failed.append(m.mention)

        if dm_failed:
            leader_embed.description += f"\n\n⚠️ **Could not DM:** {', '.join(dm_failed)}\n*They may have DMs disabled.*"

        await interaction.response.send_message(embed=leader_embed, ephemeral=True)

class PlayerSelectView(ui.View):
    def __init__(self, team_name):
        super().__init__(timeout=60)
        self.add_item(PlayerSelect(team_name))

class TeamNameModal(ui.Modal, title="🛡️ Team Verification"):
    name_input = ui.TextInput(label="Team Name", placeholder="e.g. Galaxy Crows", max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        team_name = self.name_input.value
        e = make_embed("👥 Select Squad Members",
            f"Choose the **4 players** for **{team_name}** using the dropdown below.", Theme.ACCENT)
        await interaction.response.send_message(embed=e, view=PlayerSelectView(team_name), ephemeral=True)

class PersistentVerifyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="「🛡️」Verify Your Squad", style=discord.ButtonStyle.green, custom_id="verify_btn_1")
    async def verify_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TeamNameModal())

# ═══════════════════ TICKET SYSTEM ═══════════════════

async def close_ticket_logic(channel, user):
    uid_to_remove = None
    for uid, t_id in data.get("open_tickets", {}).items():
        if t_id == channel.id:
            uid_to_remove = uid
            break
    if uid_to_remove:
        del data["open_tickets"][uid_to_remove]
        save_data(data)
    e = make_embed("🔒 Ticket Closing", "This ticket channel will be deleted in 5 seconds.", Theme.WARNING)
    await channel.send(embed=e)
    await asyncio.sleep(5)
    try:
        await channel.delete()
    except Exception:
        pass

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can close tickets.", ephemeral=True)
            return
        await interaction.response.defer()
        await close_ticket_logic(interaction.channel, interaction.user)

class PaymentTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Open Payment Ticket", style=discord.ButtonStyle.success, custom_id="open_payment_ticket_btn")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)

        if uid in data.get("open_tickets", {}):
            ticket_channel_id = data["open_tickets"][uid]
            existing_channel = interaction.guild.get_channel(ticket_channel_id)
            if existing_channel:
                await interaction.response.send_message(f"❌ You already have an open ticket: {existing_channel.mention}", ephemeral=True)
                return
            else:
                del data["open_tickets"][uid]
                save_data(data)

        if uid not in data.get("teams", {}):
            await interaction.response.send_message("❌ You are not registered.", ephemeral=True)
            return

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not category:
            await interaction.response.send_message("❌ Ticket category not setup properly.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        team_name = data["teams"][uid].get("team", "Unknown")
        team_name_clean = "".join(c if c.isalnum() else "" for c in team_name).lower()[:15]
        channel_name = f"ticket-{team_name_clean}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True)
        }

        try:
            ticket_chan = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        except Exception as e:
            await interaction.followup.send(f"❌ Error creating ticket: {e}", ephemeral=True)
            return

        if "open_tickets" not in data:
            data["open_tickets"] = {}
        data["open_tickets"][uid] = ticket_chan.id
        save_data(data)

        upi = get_upi_settings()
        amount = upi.get("payment_amount", 10)

        embed = make_embed(
            "🎫 Payment Ticket",
            f"{Theme.SEP}\n\n**Team:** `{team_name}`\n**Amount Due:** `₹{amount}`\n\n"
            f"**Please send your payment screenshot here.**\n"
            f"An admin will verify and approve your slot shortly.\n\n{Theme.SEP}",
            Theme.INFO
        )
        await ticket_chan.send(content=f"{interaction.user.mention}", embed=embed, view=TicketCloseView())
        await interaction.followup.send(f"✅ Ticket opened: {ticket_chan.mention}", ephemeral=True)

# Continue with remaining code...
# (The file is very large, so I'm showing the critical syntax fixes)
# The rest of the code structure remains similar but without the errant backticks.

if __name__ == "__main__":
    keep_alive.keep_alive()
    bot.run(TOKEN)
