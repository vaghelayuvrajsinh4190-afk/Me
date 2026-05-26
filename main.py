import discord
from discord.ext import commands, tasks
from discord import ui
import json
import os
import asyncio
import datetime
import keep_alive

# ================= 1. CONFIGURATION =================
TOKEN = os.environ.get("TOKEN")
TICKET_CATEGORY_ID = 1491353694627958927

# --- CHANNELS ---
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

# --- SETTINGS ---
MAX_SLOTS = 16
DATA_FILE = "data.json"
REGISTRATION_OPEN = True
TIMEZONE_OFFSET = 5.5 # India Standard Time
DATA_EXPIRY_DAYS = 7  # Delete team data after 7 days

# --- DEFAULT UPI SETTINGS (update via !setupi command in Discord) ---
DEFAULT_UPI_SETTINGS = {
    "upi_id": "yourname@upi",
    "upi_name": "Your Name",
    "payment_amount": 10
}

# ═══════════════════ DESIGN SYSTEM ═══════════════════
class Theme:
    # Core palette
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
    # Decorative
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

# ================= 2. DATA HANDLING =================
def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {
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
        with open(DATA_FILE, "w") as f:
            json.dump(default_data, f, indent=4)
        return default_data
    
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
        dirty = False
        if "table_messages" not in data:
            data["table_messages"] = {}
            dirty = True
        if "upi_settings" not in data:
            data["upi_settings"] = DEFAULT_UPI_SETTINGS.copy()
            dirty = True
        if "part_names" not in data:
            data["part_names"] = {"1": "Part 1 - Matches 1 to 4", "2": "Part 2 - Matches 5 to 8"}
            dirty = True
        if "part_status" not in data:
            data["part_status"] = {"1": True, "2": True}
            dirty = True
        if "verify_timeout_minutes" not in data:
            data["verify_timeout_minutes"] = 5
            dirty = True
        if "open_tickets" not in data:
            data["open_tickets"] = {}
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
        if "match_results" not in data:
            data["match_results"] = {}
            dirty = True
        for k in SLOT_LIST_CHANNELS:
            if k not in data.get("slots", {}):
                data["slots"][k] = []
                dirty = True
        if "SLOT_1" in data.get("slots", {}):
            new_slots = {k.replace("SLOT", "MATCH"): v for k, v in data["slots"].items()}
            data["slots"] = new_slots
            dirty = True
        if dirty:
            save_data(data)
        return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

def get_upi_settings():
    return data.get("upi_settings", DEFAULT_UPI_SETTINGS)

def make_payment_embed(team_name):
    """Create the payment instructions embed shown after registration."""
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

def is_paid(uid):
    """Check if a user has paid the platform fee."""
    return data.get("teams", {}).get(uid, {}).get("paid", False)

# ================= 3. HELPER FUNCTIONS =================
async def get_or_create_role(guild, role_name):
    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        try:
            role = await guild.create_role(name=role_name, mentionable=True)
        except Exception: return None
    return role

async def setup_channel_perms(guild):
    for slot_name, role_name in SLOT_ROLES.items():
        role = await get_or_create_role(guild, role_name)
        if not role: continue

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
                print(f"🔒 Locked channel {ch.name} to role {role.name}")

def check_duplicates(current_uid, new_team_name, new_players):
    """
    Checks if team name or player names already exist in database (Registration).
    """
    new_team_clean = new_team_name.strip().lower()
    new_players_clean = [p.strip().lower() for p in new_players if p.strip()]

    # 1. Check for duplicates within the current submission
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

# ═══════════════════ 4. LIVE TABLE REFRESH ═══════════════════
async def refresh_table(guild, slot_name):
    channel_id = SLOT_LIST_CHANNELS.get(slot_name)
    if not channel_id: return
    channel = guild.get_channel(channel_id)
    if not channel: return

    registered_uids = data["slots"].get(slot_name, [])
    count = len(registered_uids)
    display_name = slot_name.replace("_", " ")
    status = Theme.match_status(count, MAX_SLOTS)
    color = Theme.match_color(count, MAX_SLOTS)
    bar = Theme.bar(count, MAX_SLOTS, 16)

    # Build table
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

# ================= 5. CORE LOGIC (SLOTS ADD/REMOVE) =================
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
            try: await interaction.user.add_roles(role)
            except Exception: pass

    await refresh_table(guild, slot_name)
    return True

async def perform_removal(guild, uid, slot_name):
    if uid in data["slots"][slot_name]:
        data["slots"][slot_name].remove(uid)
    
    if uid in data["teams"] and slot_name in data["teams"][uid]["booked_slots"]:
        data["teams"][uid]["booked_slots"].remove(slot_name)
    
    save_data(data)

    role_name = SLOT_ROLES.get(slot_name)
    if role_name:
        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(int(uid))
        if role and member:
            try: await member.remove_roles(role)
            except Exception: pass

    await refresh_table(guild, slot_name)

async def remove_single_slot_logic(interaction, slot_to_remove):
    uid = str(interaction.user.id)
    if uid not in data["teams"]: return False, "No team data."
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

# ================= 6. AUTO-RESET TASK =================
@tasks.loop(minutes=1)
async def daily_reset_task():
    utc_now = datetime.datetime.utcnow()
    local_now = utc_now + datetime.timedelta(hours=TIMEZONE_OFFSET)
    
    if local_now.hour == 0 and local_now.minute == 0:
        print("🕛 MIDNIGHT RESET: Cleaning up...")
        if not bot.guilds: return
        guild = bot.guilds[0]

        for slot_name, uids in data["slots"].items():
            role_name = SLOT_ROLES.get(slot_name)
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                for uid in uids:
                    member = guild.get_member(int(uid))
                    if member:
                        try: await member.remove_roles(role)
                        except Exception: pass
            data["slots"][slot_name] = [] 

        # Reset paid flag and booked slots for all teams
        for uid in data["teams"]:
            data["teams"][uid]["booked_slots"] = []
            data["teams"][uid]["paid"] = False

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
            print(f"🗑️ Deleted expired data for User ID: {uid}")

        save_data(data)

        for slot_name in SLOT_LIST_CHANNELS:
            await refresh_table(guild, slot_name)
            await asyncio.sleep(1)

        log_ch = guild.get_channel(ADMIN_LOG_CHANNEL_ID)
        if log_ch: await log_ch.send("🕛 **Daily Reset & Cleanup Complete.**")
        
        global REGISTRATION_OPEN
        REGISTRATION_OPEN = True

# ═══════════════════ 7. VERIFICATION SYSTEM (CONSENT) ═══════════════════
class ConsentView(ui.View):
    """Ephemeral consent view — only tagged players can see it. Teammates must click Accept before roles are granted."""
    def __init__(self, team_name, leader, teammates, channel):
        timeout_minutes = data.get("verify_timeout_minutes", 5)
        super().__init__(timeout=timeout_minutes * 60)
        self.team_name = team_name
        self.leader = leader
        self.teammates = teammates
        self.accepted = {leader.id}
        self.all_ids = {m.id for m in teammates}
        self.channel = channel  # The channel where verification was initiated
        self.dm_messages = {}   # Track DM messages sent to each teammate {user_id: message}
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
            # Update the DM message the user clicked on
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
            # Also update all other DM messages for other teammates
            await self._update_all_dm_messages(exclude_user=interaction.user.id)

    @ui.button(label="🛠️ Admin Force Verify", style=discord.ButtonStyle.danger)
    async def admin_force_button(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can force-verify.", ephemeral=True)
            return
        self.accepted = set(self.all_ids)
        await self._complete_verification(interaction)

    async def _update_all_dm_messages(self, exclude_user=None):
        """Update all DM messages to reflect current consent status."""
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
            log_embed = make_embed(
                "🛡️ New Team Verified",
                f"{Theme.SEP}",
                Theme.GOLD,
                f"Verified by {self.leader.name}"
            )
            log_embed.add_field(name="🏷️ Team Name", value=f"**{self.team_name}**", inline=False)
            log_embed.add_field(name="👥 Verified Players", value=player_names_str, inline=False)
            await log_channel.send(embed=log_embed)

        complete_embed = make_embed(
            f"✅ Verification Complete — {self.team_name}",
            f"{Theme.SEP}\n\n"
            f"**All players verified!** 🎉\n\n"
            f"**Role Granted:** `{VERIFY_ROLE_NAME}`\n\n"
            f"**Squad Members:**\n{player_names_str}\n\n"
            f"{Theme.SEP}",
            Theme.SUCCESS,
            f"Verified by {self.leader.display_name}"
        )
        for item in self.children:
            item.disabled = True
        self.stop()
        
        # Update the message the interaction came from
        await interaction.response.edit_message(embed=complete_embed, view=self)
        
        # Update all other DM messages
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
            f"{Theme.SEP}\n\n"
            f"**Time ran out!** The verification request has expired.\n\n"
            f"*Please start a new verification.*\n\n"
            f"{Theme.SEP}",
            Theme.ERROR,
            "Verification Expired"
        )
        for item in self.children:
            item.disabled = True
        # Update all DM messages on timeout
        for uid, msg in self.dm_messages.items():
            try:
                await msg.edit(embed=expired_embed, view=self)
            except Exception:
                pass

class PlayerSelect(ui.UserSelect):
    def __init__(self, team_name):
        self.team_name = team_name
        super().__init__(placeholder="🎯 Select the 4 squad members...", min_values=4, max_values=4)

    async def callback(self, interaction: discord.Interaction):
        members = self.values

        # Security Check 1: Leader must include themselves
        if interaction.user not in members:
            e = make_embed(
                "⛔ Verification Failed",
                f"You must **include yourself** in the squad selection.\n\n{Theme.THIN_SEP}\n*Select yourself plus your 3 teammates.*",
                Theme.ERROR
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        # Security Check 2: No bots allowed
        bots = [m.mention for m in members if m.bot]
        if bots:
            bot_list = "\n".join([f"⚠️ {b}" for b in bots])
            e = make_embed(
                "⛔ Verification Failed",
                f"Discord bots cannot be squad members:\n\n{bot_list}\n\n{Theme.THIN_SEP}\n*Select only real players.*",
                Theme.ERROR
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        # Security Check 3: No already-verified members
        role = discord.utils.get(interaction.guild.roles, name=VERIFY_ROLE_NAME)
        if not role:
            e = make_embed("❌ Configuration Error", f"Role `{VERIFY_ROLE_NAME}` not found. Contact an admin.", Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        already_verified = [m.mention for m in members if role in m.roles]
        if already_verified:
            player_list = "\n".join([f"⚠️ {p}" for p in already_verified])
            e = make_embed(
                "⛔ Verification Failed",
                f"The following players are **already verified**:\n\n{player_list}\n\n{Theme.THIN_SEP}\n*Each player can only be verified once.*",
                Theme.ERROR
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        # All checks passed — send ephemeral DMs to each tagged player
        consent_view = ConsentView(self.team_name, interaction.user, list(members), interaction.channel)

        # Acknowledge the interaction — leader sees confirmation
        leader_embed = make_embed(
            f"🛡️ Verification Sent — {self.team_name}",
            f"{Theme.SEP}\n\n"
            f"Verification requests have been **DM'd** to your teammates.\n\n"
            f"**Waiting for acceptance from all squad members...**\n\n"
            f"{Theme.SEP}",
            Theme.ACCENT,
            f"Leader: {interaction.user.display_name}"
        )
        # Send the leader their own DM with the consent view
        try:
            leader_dm = await interaction.user.send(
                content=f"🛡️ **Team Verification — {self.team_name}**\nYou initiated this verification. Your acceptance is auto-confirmed.",
                embed=consent_view._build_embed(),
                view=consent_view
            )
            consent_view.dm_messages[interaction.user.id] = leader_dm
        except discord.Forbidden:
            pass

        # DM each teammate (excluding leader) with the shared consent view
        dm_failed = []
        for m in members:
            if m.id == interaction.user.id:
                continue
            try:
                dm_msg = await m.send(
                    content=f"🛡️ **{interaction.user.display_name}** is requesting you to verify for team **{self.team_name}**!\nClick the button below to accept.",
                    embed=consent_view._build_embed(),
                    view=consent_view
                )
                consent_view.dm_messages[m.id] = dm_msg
            except discord.Forbidden:
                dm_failed.append(m.mention)

        # Show leader a summary in-channel (ephemeral)
        if dm_failed:
            failed_list = ", ".join(dm_failed)
            leader_embed.description += f"\n\n⚠️ **Could not DM:** {failed_list}\n*They may have DMs disabled.*"

        await interaction.response.send_message(embed=leader_embed, ephemeral=True)

class PlayerSelectView(ui.View):
    def __init__(self, team_name):
        super().__init__(timeout=60)
        self.add_item(PlayerSelect(team_name))

class TeamNameModal(ui.Modal, title="🛡️ Team Verification"):
    name_input = ui.TextInput(label="Team Name", placeholder="e.g. Galaxy Crows", max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        team_name = self.name_input.value
        e = make_embed(
            "👥 Select Squad Members",
            f"Choose the **4 players** for **{team_name}** using the dropdown below.",
            Theme.ACCENT
        )
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
    except:
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
                # Ticket was manually deleted, so we clean the database
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
            ticket_chan = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites
            )
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
            f"{Theme.SEP}\n\n"
            f"**Team:** `{team_name}`\n"
            f"**Amount Due:** `₹{amount}`\n\n"
            f"**Please send your payment screenshot here.**\n"
            f"An admin will verify and approve your slot shortly.\n\n"
            f"{Theme.SEP}",
            Theme.INFO
        )
        await ticket_chan.send(content=f"{interaction.user.mention}", embed=embed, view=TicketCloseView())
        await interaction.followup.send(f"✅ Ticket opened: {ticket_chan.mention}", ephemeral=True)

# ═══════════════════ 8. SLOT VIEWS ═══════════════════
class TeamModal(discord.ui.Modal, title="📋 Squad Registration"):
    team = discord.ui.TextInput(label="Team Name", placeholder="Enter a unique team name...")
    p1 = discord.ui.TextInput(label="Player 1 — IGL (In-Game Leader)", placeholder="In-game name or Discord ID")
    p2 = discord.ui.TextInput(label="Player 2", placeholder="In-game name", required=False)
    p3 = discord.ui.TextInput(label="Player 3", placeholder="In-game name", required=False)
    p4 = discord.ui.TextInput(label="Player 4", placeholder="In-game name", required=False)
    
    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        
        players_input = [self.p1.value, self.p2.value, self.p3.value, self.p4.value]
        is_duplicate, error_msg = check_duplicates(uid, self.team.value, players_input)
        
        if is_duplicate:
            e = make_embed("⛔ Registration Error", error_msg, Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        data["teams"][uid] = {
            "team": self.team.value,
            "players": [p for p in players_input if p], 
            "booked_slots": [],
            "paid": False,
            "last_updated": datetime.datetime.utcnow().isoformat()
        }
        save_data(data)
        
        log_channel = interaction.guild.get_channel(ADMIN_LOG_CHANNEL_ID)
        if log_channel:
            log_e = make_embed("🆕 Team Registered", f"{Theme.SEP}", Theme.ACCENT, f"User ID: {uid}")
            log_e.add_field(name="🏷️ Team", value=f"**{self.team.value}**", inline=True)
            log_e.add_field(name="👤 Leader", value=f"<@{uid}>", inline=True)
            players_str = ", ".join([p for p in players_input if p]) or "Solo"
            log_e.add_field(name="👥 Roster", value=players_str, inline=False)
            log_e.add_field(name="💰 Payment", value="❌ Pending", inline=True)
            await log_channel.send(embed=log_e)

        # Show Part Selection instead of payment embed directly
        part1_name = data.get("part_names", {}).get("1", "Part 1 - Matches 1 to 4")
        part2_name = data.get("part_names", {}).get("2", "Part 2 - Matches 5 to 8")
        e = make_embed(
            "🎮 Select Your Part",
            f"{Theme.SEP}\n\n"
            f"✅ Team **{self.team.value}** registered successfully!\n\n"
            f"{Theme.THIN_SEP}\n\n"
            f"**Choose which part you want to play:**\n\n"
            f"> 🅰️ **{part1_name}**\n"
            f"> Matches 1, 2, 3, 4\n\n"
            f"> 🅱️ **{part2_name}**\n"
            f"> Matches 5, 6, 7, 8\n\n"
            f"{Theme.SEP}",
            Theme.PREMIUM,
            "Select a part to continue"
        )
        await interaction.response.send_message(embed=e, view=PartSelectionView(uid, self.team.value), ephemeral=True)

class PartSelectionView(discord.ui.View):
    """View with Part 1 and Part 2 buttons for match selection."""
    def __init__(self, uid, team_name):
        super().__init__(timeout=120)
        self.uid = uid
        self.team_name = team_name

        part1_name = data.get("part_names", {}).get("1", "Part 1 - Matches 1 to 4")
        part2_name = data.get("part_names", {}).get("2", "Part 2 - Matches 5 to 8")
        part1_open = data.get("part_status", {}).get("1", True)
        part2_open = data.get("part_status", {}).get("2", True)

        # Part 1 Button
        if part1_open:
            p1_btn = discord.ui.Button(label=f"🅰️ {part1_name}", style=discord.ButtonStyle.primary)
        else:
            p1_btn = discord.ui.Button(label=f"⛔ {part1_name} (CLOSED)", style=discord.ButtonStyle.secondary, disabled=True)
        p1_btn.callback = self.part1_callback
        self.add_item(p1_btn)

        # Part 2 Button
        if part2_open:
            p2_btn = discord.ui.Button(label=f"🅱️ {part2_name}", style=discord.ButtonStyle.primary)
        else:
            p2_btn = discord.ui.Button(label=f"⛔ {part2_name} (CLOSED)", style=discord.ButtonStyle.secondary, disabled=True)
        p2_btn.callback = self.part2_callback
        self.add_item(p2_btn)

    async def part1_callback(self, interaction: discord.Interaction):
        if self.uid in data.get("teams", {}):
            data["teams"][self.uid]["selected_part"] = "part_1"
            save_data(data)
        await interaction.response.edit_message(embed=make_payment_embed(self.team_name), view=PaymentTicketView())

    async def part2_callback(self, interaction: discord.Interaction):
        if self.uid in data.get("teams", {}):
            data["teams"][self.uid]["selected_part"] = "part_2"
            save_data(data)
        await interaction.response.edit_message(embed=make_payment_embed(self.team_name), view=PaymentTicketView())

class SlotButton(discord.ui.Button):
    def __init__(self, slot):
        count = len(data["slots"][slot])
        display_name = slot.replace("_", " ") 
        status = "FULL" if count >= MAX_SLOTS else f"{count}/{MAX_SLOTS}"
        label = f"{display_name}  •  {status}"
        if count >= MAX_SLOTS:
            style = discord.ButtonStyle.red
        elif count >= MAX_SLOTS * 0.75:
            style = discord.ButtonStyle.grey
        else:
            style = discord.ButtonStyle.green
        super().__init__(label=label, style=style, disabled=(count >= MAX_SLOTS))
        self.slot = slot

    async def callback(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if not is_paid(uid):
            team_name = data.get("teams", {}).get(uid, {}).get("team", "your team")
            await interaction.response.send_message(embed=make_payment_embed(team_name), view=PaymentTicketView(), ephemeral=True)
            return
            
        selected_part = data.get("teams", {}).get(uid, {}).get("selected_part", "part_1")
        if selected_part == "part_2" and self.slot not in ["MATCH_5", "MATCH_6", "MATCH_7", "MATCH_8"]:
            e = make_embed("⛔ Access Denied", "You only paid for Part 2. You cannot join Part 1 matches.", Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        if selected_part == "part_1" and self.slot not in ["MATCH_1", "MATCH_2", "MATCH_3", "MATCH_4"]:
            e = make_embed("⛔ Access Denied", "You only paid for Part 1. You cannot join Part 2 matches.", Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        success = await add_player_to_slot(interaction, self.slot)
        if success:
            display = self.slot.replace('_', ' ')
            count = len(data["slots"][self.slot])
            e = make_embed(
                f"✅ Slot Claimed — {display}",
                f"You are **#{count}** in the roster!\n{Theme.bar(count, MAX_SLOTS)}",
                Theme.SUCCESS
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
        else:
             if not interaction.response.is_done():
                 e = make_embed("❌ Claim Failed", "This match is full or you're already registered.", Theme.ERROR)
                 await interaction.response.send_message(embed=e, ephemeral=True)

class SlotSelectView(discord.ui.View):
    def __init__(self, uid):
        super().__init__(timeout=60)
        selected_part = data.get("teams", {}).get(uid, {}).get("selected_part", "part_1")
        
        if selected_part == "part_2":
            allowed_matches = ["MATCH_5", "MATCH_6", "MATCH_7", "MATCH_8"]
        else:
            allowed_matches = ["MATCH_1", "MATCH_2", "MATCH_3", "MATCH_4"]
            
        for s in allowed_matches:
            if s in SLOT_LIST_CHANNELS:
                self.add_item(SlotButton(s))

class AutoClaimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="「⚡」Auto-Assign to Open Match", style=discord.ButtonStyle.blurple, custom_id="auto_claim_btn")
    async def auto_claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not REGISTRATION_OPEN:
            e = make_embed("⛔ Claims Closed", "Registration is currently locked. Please wait for the next round.", Theme.WARNING)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid not in data["teams"]:
            e = make_embed("❌ Not Registered", "You must register your team first before claiming a slot.", Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        if not is_paid(uid):
            team_name = data["teams"][uid].get("team", "your team")
            await interaction.response.send_message(embed=make_payment_embed(team_name), view=PaymentTicketView(), ephemeral=True)
            return
            
        selected_part = data["teams"][uid].get("selected_part", "part_1")
        if selected_part == "part_2":
            allowed_matches = ["MATCH_5", "MATCH_6", "MATCH_7", "MATCH_8"]
        else:
            allowed_matches = ["MATCH_1", "MATCH_2", "MATCH_3", "MATCH_4"]

        assigned = None
        for slot_name in allowed_matches:
            if len(data["slots"][slot_name]) < MAX_SLOTS and uid not in data["slots"][slot_name]:
                assigned = slot_name
                break
                
        if assigned:
            success = await add_player_to_slot(interaction, assigned)
            if success:
                display = assigned.replace('_', ' ')
                e = make_embed("⚡ Auto-Assigned!", f"You've been placed in **{display}**!", Theme.SUCCESS)
                await interaction.response.send_message(embed=e, ephemeral=True)
        else:
            e = make_embed("❌ All Full", "Every match slot in your selected part is currently taken.", Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)

class TeamChoiceView(discord.ui.View):
    def __init__(self, team_name):
        super().__init__(timeout=60)
        self.team_name = team_name

    @discord.ui.button(label="✅ Continue with this team", style=discord.ButtonStyle.success)
    async def continue_old(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        # If no part selected yet, show part selection
        if not data["teams"].get(uid, {}).get("selected_part"):
            part1_name = data.get("part_names", {}).get("1", "Part 1 - Matches 1 to 4")
            part2_name = data.get("part_names", {}).get("2", "Part 2 - Matches 5 to 8")
            e = make_embed(
                "🎮 Select Your Part",
                f"{Theme.SEP}\n\n"
                f"**Choose which part you want to play:**\n\n"
                f"> 🅰️ **{part1_name}**\n"
                f"> Matches 1, 2, 3, 4\n\n"
                f"> 🅱️ **{part2_name}**\n"
                f"> Matches 5, 6, 7, 8\n\n"
                f"{Theme.SEP}",
                Theme.PREMIUM,
                "Select a part to continue"
            )
            await interaction.response.send_message(embed=e, view=PartSelectionView(uid, self.team_name), ephemeral=True)
            return
        if not is_paid(uid):
            await interaction.response.send_message(embed=make_payment_embed(self.team_name), view=PaymentTicketView(), ephemeral=True)
            return
        e = make_embed(
            f"🏷️ Using Team — {self.team_name}",
            f"Select a match below to claim your slot.",
            Theme.SUCCESS
        )
        await interaction.response.send_message(embed=e, view=SlotSelectView(uid), ephemeral=True)

    @discord.ui.button(label="📝 Register New Team", style=discord.ButtonStyle.primary)
    async def update_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TeamModal())

class MainRegisterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="「📝」Register Your Squad", style=discord.ButtonStyle.green, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not REGISTRATION_OPEN:
            e = make_embed("⛔ Registration Closed", "Registration is currently locked. Please wait for the next round.", Theme.WARNING)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        uid = str(interaction.user.id)
        if uid in data["teams"]:
            last_updated = data["teams"][uid].get("last_updated")
            if last_updated:
                reg_time = datetime.datetime.fromisoformat(last_updated)
                if (datetime.datetime.utcnow() - reg_time).days >= DATA_EXPIRY_DAYS:
                    del data["teams"][uid]
                    save_data(data)
                    await interaction.response.send_modal(TeamModal())
                    return
            team_name = data["teams"][uid]["team"]
            info = data["teams"][uid]
            players = info.get("players", [])
            booked = info.get("booked_slots", [])
            paid_status = "✅ Approved" if info.get("paid", False) else "❌ Pending Payment"
            roster = "\n".join([f"` {i+1} ` {p}" for i, p in enumerate(players)]) or "No players"
            matches = ", ".join([s.replace('_', ' ') for s in booked]) if booked else "None"
            e = make_embed(
                f"⚠️ Already Registered — {team_name}",
                f"{Theme.SEP}\n\n**Squad Roster:**\n{roster}\n\n**Active Matches:** {matches}\n**Payment:** {paid_status}\n\n{Theme.THIN_SEP}\n*Choose an option below:*",
                Theme.WARNING
            )
            await interaction.response.send_message(embed=e, view=TeamChoiceView(team_name), ephemeral=True)
        else:
            await interaction.response.send_modal(TeamModal())

class CancelDropdown(discord.ui.Select):
    def __init__(self, booked_slots):
        options = []
        for slot in booked_slots:
            display_name = slot.replace("_", " ")
            count = len(data["slots"].get(slot, []))
            options.append(discord.SelectOption(label=f"Leave {display_name}", description=f"{count}/{MAX_SLOTS} teams", value=slot, emoji="🗑️"))
        options.append(discord.SelectOption(label="Leave ALL Matches", description="Cancel everything", value="ALL", emoji="💥"))
        super().__init__(placeholder="🔽 Select match to leave...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "ALL":
            success, msg = await remove_all_slots_logic(interaction)
        else:
            success, msg = await remove_single_slot_logic(interaction, self.values[0])
        color = Theme.SUCCESS if success else Theme.ERROR
        e = make_embed("🗑️ Match Update", msg, color)
        await interaction.response.send_message(embed=e, ephemeral=True)

class CancelAndClaimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="「🗑️」Leave a Match", style=discord.ButtonStyle.danger, custom_id="cancel_slot_btn")
    async def cancel_slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid not in data["teams"] or not data["teams"][uid].get("booked_slots"):
             e = make_embed("⚠️ No Active Matches", "You don't have any match slots to cancel.", Theme.WARNING)
             await interaction.response.send_message(embed=e, ephemeral=True)
             return
        booked = data["teams"][uid]["booked_slots"]
        e = make_embed("🗑️ Leave a Match", "Select the match you want to leave from the dropdown below.", Theme.ORANGE)
        await interaction.response.send_message(embed=e, view=discord.ui.View().add_item(CancelDropdown(booked)), ephemeral=True)

    @discord.ui.button(label="「♻️」Join Open Match", style=discord.ButtonStyle.primary, custom_id="claim_open_btn")
    async def claim_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not REGISTRATION_OPEN:
            e = make_embed("⛔ Claims Closed", "Registration is currently locked.", Theme.WARNING)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid not in data["teams"]:
            e = make_embed("❌ Not Registered", "Register your team first before joining a match.", Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        if not is_paid(uid):
            team_name = data["teams"][uid].get("team", "your team")
            await interaction.response.send_message(embed=make_payment_embed(team_name), view=PaymentTicketView(), ephemeral=True)
            return
        e = make_embed("🎮 Available Matches", "Select a match below to claim your slot.", Theme.ACCENT)
        await interaction.response.send_message(embed=e, view=SlotSelectView(uid), ephemeral=True)

# ================= 9. BOT CLASS & ADMIN COMMANDS =================
class SlotBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    
    async def setup_hook(self):
        self.add_view(MainRegisterView())
        self.add_view(AutoClaimView())
        self.add_view(CancelAndClaimView())
        self.add_view(PersistentVerifyView())
        self.add_view(PaymentTicketView())
        self.add_view(TicketCloseView())

bot = SlotBot()

def is_admin_channel():
    async def predicate(ctx):
        if ctx.channel.id != ADMIN_COMMAND_CHANNEL_ID:
            e = make_embed("🔒 Wrong Channel", f"Admin commands only work in <#{ADMIN_COMMAND_CHANNEL_ID}>", Theme.ERROR)
            await ctx.send(embed=e, delete_after=5)
            return False
        return True
    return commands.check(predicate)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    if not daily_reset_task.is_running():
        daily_reset_task.start()

@bot.command(aliases=["c", "purge"])
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int = 100):
    """Clear messages from the current channel."""
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        e = make_embed("🧹 Channel Cleared", f"Removed **{len(deleted)-1}** messages.", Theme.SUCCESS)
        msg = await ctx.send(embed=e)
        await asyncio.sleep(3)
        await msg.delete()
    except Exception as err:
        e = make_embed("❌ Clear Failed", f"`{err}`", Theme.ERROR)
        await ctx.send(embed=e, delete_after=5)

@bot.command(aliases=["sv"])
@commands.has_permissions(administrator=True)
async def setup_verify(ctx):
    """Setup the verification panel."""
    if ctx.channel.id != VERIFY_CHANNEL_ID:
        e = make_embed("⚠️ Channel Mismatch", f"Expected <#{VERIFY_CHANNEL_ID}>, posting here anyway.", Theme.WARNING)
        await ctx.send(embed=e, delete_after=5)
    
    embed = make_embed(
        "🛡️ Squad Verification Portal",
        f"{Theme.SEP}\n\n"
        "**Welcome, warriors!** ⚔️\n\n"
        "To participate in the tournament, your squad must be verified first.\n\n"
        f"{Theme.THIN_SEP}\n\n"
        "**📋 How to verify:**\n"
        "> `1.` Click the button below\n"
        "> `2.` Enter your team name\n"
        "> `3.` Select your 4 squad members\n"
        "> `4.` Done! You'll receive the Verified role\n\n"
        f"{Theme.SEP}",
        Theme.ACCENT,
        "🔐 One-time verification per squad"
    )
    await ctx.send(embed=embed, view=PersistentVerifyView())
    await ctx.message.delete()

@bot.command(aliases=["fr", "rm"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def force_remove(ctx, match_name: str, slot_number: int):
    """Force remove a team from a match slot."""
    match_key = match_name.upper()
    if match_key not in SLOT_LIST_CHANNELS:
        e = make_embed("❌ Invalid Match", "Use: `MATCH_1`, `MATCH_2`, `MATCH_3`, `MATCH_4`", Theme.ERROR)
        await ctx.send(embed=e)
        return
    registered_uids = data["slots"].get(match_key, [])
    index = slot_number - 1 
    if index < 0 or index >= len(registered_uids):
        e = make_embed("❌ Empty Slot", f"Slot **#{slot_number}** has no team.", Theme.ERROR)
        await ctx.send(embed=e)
        return
    target_uid = registered_uids[index]
    team_name = data["teams"].get(target_uid, {}).get("team", "Unknown")
    await perform_removal(ctx.guild, target_uid, match_key)
    display = match_key.replace('_', ' ')
    e = make_embed(
        "🔨 Team Removed",
        f"{Theme.SEP}\n\n"
        f"**Team:** {team_name}\n"
        f"**Match:** {display}\n"
        f"**Slot:** #{slot_number}\n"
        f"**By:** {ctx.author.mention}",
        Theme.ORANGE
    )
    await ctx.send(embed=e)

@bot.command(aliases=["set"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def setup(ctx):
    """Initialize all bot panels."""
    await ctx.message.delete()
    status_e = make_embed("⚙️ Setting Up...", "`▰▱▱▱▱` Configuring permissions...", Theme.PREMIUM)
    msg = await ctx.send(embed=status_e)
    await setup_channel_perms(ctx.guild)
    
    reg_ch = ctx.guild.get_channel(REGISTRATION_CHANNEL_ID)
    if reg_ch:
        await msg.edit(embed=make_embed("⚙️ Setting Up...", "`▰▰▰▱▱` Creating registration panel...", Theme.PREMIUM))
        await reg_ch.purge(limit=5)
        reg_embed = make_embed(
            "🏆 Tournament Registration",
            f"{Theme.SEP}\n\n"
            "**Welcome to the battlefield!** ⚔️\n\n"
            "Register your squad and claim a match slot to compete.\n\n"
            f"{Theme.THIN_SEP}\n\n"
            "**📋 Steps:**\n"
            "> `1.` Click **Register** below\n"
            "> `2.` Fill in your team details\n"
            "> `3.` Select your preferred match\n\n"
            f"{Theme.SEP}",
            Theme.ACCENT,
            "📝 Registration"
        )
        await reg_ch.send(embed=reg_embed, view=MainRegisterView())
        quick_e = make_embed(
            "⚡ Quick Actions",
            "Don't want to choose? Let the bot pick an open match for you!",
            Theme.PREMIUM
        )
        await reg_ch.send(embed=quick_e, view=AutoClaimView())
    
    can_ch = ctx.guild.get_channel(CANCEL_CLAIM_CHANNEL_ID)
    if can_ch:
        await msg.edit(embed=make_embed("⚙️ Setting Up...", "`▰▰▰▰▱` Creating management panel...", Theme.PREMIUM))
        await can_ch.purge(limit=5)
        cancel_embed = make_embed(
            "🎮 Match Management",
            f"{Theme.SEP}\n\n"
            "Need to leave a match or join a different one?\n"
            "Use the buttons below to manage your slots.\n\n"
            f"{Theme.SEP}",
            Theme.ORANGE,
            "🔧 Slot Management"
        )
        await can_ch.send(embed=cancel_embed, view=CancelAndClaimView())

    await msg.edit(embed=make_embed("✅ Setup Complete!", "`▰▰▰▰▰` All panels are live.", Theme.SUCCESS))

@bot.command(aliases=["it"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def init_tables(ctx):
    """Refresh all live match tables."""
    e = make_embed("🔄 Initializing...", "Refreshing all live tables...", Theme.PREMIUM)
    msg = await ctx.send(embed=e)
    for slot_name in SLOT_LIST_CHANNELS:
        await refresh_table(ctx.guild, slot_name)
        await asyncio.sleep(1) 
    await msg.edit(embed=make_embed("✅ Tables Live", "All match tables have been refreshed.", Theme.SUCCESS))

@bot.command(aliases=["ns", "alert"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def notify_start(ctx, minutes: int, slot_name: str = None):
    """Notify players about match start."""
    await ctx.message.delete()
    target_slot = slot_name.upper() if slot_name else None
    count = 0
    for s_name, channel_id in SLOT_LIST_CHANNELS.items():
        if target_slot and s_name != target_slot: continue
        role_name = SLOT_ROLES.get(s_name)
        if not role_name: continue
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        channel = ctx.guild.get_channel(channel_id)
        room_channel_id = ROOM_CHANNELS.get(s_name)
        room_channel = ctx.guild.get_channel(room_channel_id) if room_channel_id else None
        if role and channel:
            display = s_name.replace('_', ' ')
            room_link = room_channel.mention if room_channel else "the room channel"
            notify_e = make_embed(
                f"🚨 {display} — Starting Soon!",
                f"{Theme.SEP}\n\n"
                f"⏱️ **Match begins in `{minutes}` minutes!**\n\n"
                f"📍 Check {room_link} for **Room ID & Password**\n\n"
                f"{Theme.THIN_SEP}\n"
                "*Be ready and in the lobby on time!*",
                Theme.ERROR,
                "⚔️ Good luck, warriors!"
            )
            await channel.send(content=role.mention, embed=notify_e)
            count += 1
    e = make_embed("✅ Notifications Sent", f"Alerted **{count}** match channel(s).", Theme.SUCCESS)
    await ctx.send(embed=e, delete_after=5)

@bot.command(aliases=["l"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def lock(ctx):
    """Lock registration system."""
    global REGISTRATION_OPEN
    REGISTRATION_OPEN = False
    e = make_embed(
        "🔒 System Locked",
        f"{Theme.SEP}\n\nRegistration and slot claims are now **disabled**.\nUse `!unlock` to re-open.",
        Theme.ERROR
    )
    await ctx.send(embed=e)
    reg_ch = ctx.guild.get_channel(REGISTRATION_CHANNEL_ID)
    if reg_ch:
        lock_e = make_embed("⛔ Registration Closed", "Slot claims are temporarily disabled. Stay tuned!", Theme.ERROR)
        await reg_ch.send(embed=lock_e)

@bot.command(aliases=["ul"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def unlock(ctx):
    """Unlock registration system."""
    global REGISTRATION_OPEN
    REGISTRATION_OPEN = True
    e = make_embed(
        "🔓 System Unlocked",
        f"{Theme.SEP}\n\nRegistration is now **open**! Players can claim slots again.",
        Theme.SUCCESS
    )
    await ctx.send(embed=e)

# ═══════════════════ 9B. PAYMENT ADMIN COMMANDS ═══════════════════

@bot.command(aliases=["ct"])
@commands.has_permissions(administrator=True)
async def close(ctx):
    """Close and delete current ticket channel."""
    if str(ctx.channel.name).startswith("ticket-") or ctx.channel.id in data.get("open_tickets", {}).values():
        await close_ticket_logic(ctx.channel, ctx.author)
    else:
        await ctx.send(embed=make_embed("❌ Error", "This does not appear to be a ticket channel.", Theme.ERROR))

@bot.command(aliases=["at", "add"])
@commands.has_permissions(administrator=True)
async def add_to_ticket(ctx, member: discord.Member):
    """Add users to ticket channel."""
    if not (str(ctx.channel.name).startswith("ticket-") or ctx.channel.id in data.get("open_tickets", {}).values()):
        await ctx.send(embed=make_embed("❌ Error", "This does not appear to be a ticket channel.", Theme.ERROR))
        return
    
    try:
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
        await ctx.send(embed=make_embed("✅ Added", f"Added {member.mention} to the ticket.", Theme.SUCCESS))
    except Exception as e:
        await ctx.send(embed=make_embed("❌ Error", f"Failed to add user: `{e}`", Theme.ERROR))

@bot.command(aliases=["ap"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def approve(ctx, member: discord.Member):
    """Approve a player's payment — auto-adds to 4 matches based on selected part."""
    uid = str(member.id)
    if uid not in data["teams"]:
        await ctx.send(embed=make_embed("❌ Not Found", f"{member.mention} has no registered team.", Theme.ERROR))
        return
    
    if data["teams"][uid].get("paid", False):
        await ctx.send(embed=make_embed("⚠️ Already Approved", f"{member.mention}'s payment is already approved.", Theme.WARNING))
        return
    
    # Set paid
    data["teams"][uid]["paid"] = True
    data["teams"][uid]["last_updated"] = datetime.datetime.utcnow().isoformat()
    
    # Determine which matches based on selected part
    selected_part = data["teams"][uid].get("selected_part", "part_1")
    if selected_part == "part_2":
        target_matches = ["MATCH_5", "MATCH_6", "MATCH_7", "MATCH_8"]
        part_label = data.get("part_names", {}).get("2", "Part 2")
    else:
        target_matches = ["MATCH_1", "MATCH_2", "MATCH_3", "MATCH_4"]
        part_label = data.get("part_names", {}).get("1", "Part 1")
    
    # Auto-add to target matches
    added = []
    skipped = []
    already_in = []
    for slot_name in target_matches:
        if uid in data["slots"][slot_name]:
            already_in.append(slot_name)
        elif len(data["slots"][slot_name]) >= MAX_SLOTS:
            skipped.append(slot_name)
        else:
            data["slots"][slot_name].append(uid)
            if "booked_slots" not in data["teams"][uid]:
                data["teams"][uid]["booked_slots"] = []
            if slot_name not in data["teams"][uid]["booked_slots"]:
                data["teams"][uid]["booked_slots"].append(slot_name)
            added.append(slot_name)
    
    save_data(data)
    
    # Assign roles for added matches
    for slot_name in added:
        role_name = SLOT_ROLES.get(slot_name)
        if role_name:
            role = await get_or_create_role(ctx.guild, role_name)
            if role:
                try: await member.add_roles(role)
                except Exception: pass
    
    # Refresh affected tables
    for slot_name in target_matches:
        await refresh_table(ctx.guild, slot_name)
        await asyncio.sleep(0.5)
    
    # Build status strings
    team_name = data["teams"][uid]["team"]
    added_str = ", ".join([s.replace("_", " ") for s in added]) or "None"
    skipped_str = ", ".join([s.replace("_", " ") for s in skipped]) or "None"
    
    # Admin confirmation
    admin_embed = make_embed(
        "✅ Payment Approved",
        f"{Theme.SEP}\n\n"
        f"**Team:** {team_name}\n"
        f"**Leader:** {member.mention}\n"
        f"**Selected:** {part_label}\n\n"
        f"**✅ Added to:** {added_str}\n"
        f"**🔴 Skipped (Full):** {skipped_str}\n\n"
        f"**Approved by:** {ctx.author.mention}",
        Theme.SUCCESS
    )
    await ctx.send(embed=admin_embed)
    
    # Log to admin log channel
    log_ch = ctx.guild.get_channel(ADMIN_LOG_CHANNEL_ID)
    if log_ch:
        await log_ch.send(embed=admin_embed)
    
    # DM to player
    try:
        dm_desc = (
            f"{Theme.SEP}\n\n"
            f"Your payment for team **{team_name}** has been verified! ✅\n\n"
            f"**Part:** {part_label}\n"
            f"**Matches Joined:** {added_str}\n"
        )
        if skipped:
            dm_desc += f"⚠️ **Full Matches (skipped):** {skipped_str}\n"
        dm_desc += f"\n{Theme.THIN_SEP}\n*Check the match channels for room details before the match starts.*"
        
        dm_embed = make_embed("✅ Payment Approved!", dm_desc, Theme.SUCCESS, "💰 Payment Verified")
        await member.send(embed=dm_embed)
    except Exception:
        await ctx.send(embed=make_embed("⚠️ DM Failed", f"Could not DM {member.mention}. They may have DMs disabled.", Theme.WARNING))

@bot.command(aliases=["uap"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def unapprove(ctx, member: discord.Member):
    """Reverse a payment approval — removes from all matches, removes roles."""
    uid = str(member.id)
    if uid not in data["teams"]:
        await ctx.send(embed=make_embed("❌ Not Found", f"{member.mention} has no registered team.", Theme.ERROR))
        return
    
    if not data["teams"][uid].get("paid", False):
        await ctx.send(embed=make_embed("⚠️ Not Approved", f"{member.mention}'s payment was not approved.", Theme.WARNING))
        return
    
    # Set unpaid
    data["teams"][uid]["paid"] = False
    team_name = data["teams"][uid]["team"]
    
    # Remove from all matches
    booked = list(data["teams"][uid].get("booked_slots", []))
    for slot_name in booked:
        await perform_removal(ctx.guild, uid, slot_name)
    
    save_data(data)
    
    removed_str = ", ".join([s.replace("_", " ") for s in booked]) or "None"
    
    e = make_embed(
        "🔄 Payment Unapproved",
        f"{Theme.SEP}\n\n"
        f"**Team:** {team_name}\n"
        f"**Leader:** {member.mention}\n"
        f"**Removed from:** {removed_str}\n\n"
        f"**By:** {ctx.author.mention}",
        Theme.ORANGE
    )
    await ctx.send(embed=e)
    
    log_ch = ctx.guild.get_channel(ADMIN_LOG_CHANNEL_ID)
    if log_ch:
        await log_ch.send(embed=e)
    
    # DM to player
    try:
        dm_e = make_embed(
            "⚠️ Payment Reversed",
            f"Your payment approval for team **{team_name}** has been reversed.\n"
            f"You have been removed from all matches.\n\n"
            f"*Contact admin if this is a mistake.*",
            Theme.ORANGE
        )
        await member.send(embed=dm_e)
    except Exception:
        pass

@bot.command(aliases=["pd"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def pending(ctx):
    """Show all teams with pending (unpaid) payments."""
    pending_teams = []
    for uid, info in data["teams"].items():
        if not info.get("paid", False):
            team_name = info.get("team", "Unknown")
            reg_time = info.get("last_updated", "Unknown")[:16]
            pending_teams.append(f"• **{team_name}** — <@{uid}> (Registered: `{reg_time}`)")
    
    if not pending_teams:
        await ctx.send(embed=make_embed("✅ No Pending Payments", "All registered teams have been approved!", Theme.SUCCESS))
        return
    
    desc = f"{Theme.SEP}\n\n" + "\n".join(pending_teams) + f"\n\n{Theme.THIN_SEP}\n**Total:** `{len(pending_teams)}` pending\n\nUse `!approve @user` to approve."
    
    # Handle long messages
    if len(desc) > 4000:
        chunks = [pending_teams[i:i+15] for i in range(0, len(pending_teams), 15)]
        for i, chunk in enumerate(chunks):
            chunk_desc = f"{Theme.SEP}\n\n" + "\n".join(chunk)
            title = f"💰 Pending Payments ({i+1}/{len(chunks)})"
            await ctx.send(embed=make_embed(title, chunk_desc, Theme.GOLD))
    else:
        await ctx.send(embed=make_embed("💰 Pending Payments", desc, Theme.GOLD))

@bot.command(aliases=["supi"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def setupi(ctx, upi_id: str, amount: int, *, name: str):
    """Set UPI payment details. Usage: !setupi <upi_id> <amount> <name>"""
    data["upi_settings"] = {
        "upi_id": upi_id,
        "upi_name": name,
        "payment_amount": amount
    }
    save_data(data)
    
    e = make_embed(
        "✅ UPI Settings Updated",
        f"{Theme.SEP}\n\n"
        f"**UPI ID:** `{upi_id}`\n"
        f"**Name:** `{name}`\n"
        f"**Amount:** `₹{amount}`\n\n"
        f"{Theme.THIN_SEP}\n"
        f"*These details will be shown to players during registration.*",
        Theme.SUCCESS
    )
    await ctx.send(embed=e)

@bot.command(aliases=["vupi"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def viewupi(ctx):
    """View current UPI payment settings."""
    upi = get_upi_settings()
    e = make_embed(
        "💳 Current UPI Settings",
        f"{Theme.SEP}\n\n"
        f"**UPI ID:** `{upi['upi_id']}`\n"
        f"**Name:** `{upi['upi_name']}`\n"
        f"**Amount:** `₹{upi['payment_amount']}`\n\n"
        f"{Theme.THIN_SEP}\n"
        f"*Use `!setupi <upi_id> <amount> <name>` to change.*",
        Theme.GOLD
    )
    await ctx.send(embed=e)

@bot.command(aliases=["stt"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def set_timeout(ctx, minutes: int):
    """Set the verification consent timeout in minutes."""
    if minutes < 1 or minutes > 60:
        await ctx.send(embed=make_embed("❌ Invalid Range", "Timeout must be between 1 and 60 minutes.", Theme.ERROR))
        return
    data["verify_timeout_minutes"] = minutes
    save_data(data)
    e = make_embed(
        "✅ Timeout Updated",
        f"{Theme.SEP}\n\n"
        f"Verification consent timeout set to **{minutes} minutes**.\n\n"
        f"{Theme.THIN_SEP}\n"
        f"*New verifications will use this timeout.*",
        Theme.SUCCESS
    )
    await ctx.send(embed=e)

@bot.command(aliases=["rp"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def rename_part(ctx, part_num: str, *, new_name: str):
    """Rename Part 1 or Part 2. Usage: !rename_part 1 New Part Name"""
    if part_num not in ("1", "2"):
        await ctx.send(embed=make_embed("❌ Invalid Part", "Use `1` or `2`. Example: `!rename_part 1 Day 1 Matches`", Theme.ERROR))
        return
    old_name = data.get("part_names", {}).get(part_num, f"Part {part_num}")
    data["part_names"][part_num] = new_name
    save_data(data)
    e = make_embed(
        "✅ Part Renamed",
        f"{Theme.SEP}\n\n"
        f"**Part {part_num}** renamed:\n"
        f"~~{old_name}~~ → **{new_name}**\n\n"
        f"{Theme.THIN_SEP}\n"
        f"*New registrations will see this name.*",
        Theme.SUCCESS
    )
    await ctx.send(embed=e)

@bot.command(aliases=["tp"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def toggle_part(ctx, part_num: str):
    """Toggle Part 1 or Part 2 open/closed. Usage: !toggle_part 1"""
    if part_num not in ("1", "2"):
        await ctx.send(embed=make_embed("❌ Invalid Part", "Use `1` or `2`. Example: `!toggle_part 1`", Theme.ERROR))
        return
    current = data.get("part_status", {}).get(part_num, True)
    new_status = not current
    data["part_status"][part_num] = new_status
    save_data(data)
    part_name = data.get("part_names", {}).get(part_num, f"Part {part_num}")
    status_str = "🟢 **OPEN**" if new_status else "🔴 **CLOSED**"
    color = Theme.SUCCESS if new_status else Theme.ERROR
    e = make_embed(
        "🔄 Part Status Updated",
        f"{Theme.SEP}\n\n"
        f"**{part_name}** is now {status_str}\n\n"
        f"{Theme.THIN_SEP}\n"
        f"*Players {'can' if new_status else 'cannot'} select this part during registration.*",
        color
    )
    await ctx.send(embed=e)

# ═══════════════════ 10. ANNOUNCEMENT SYSTEM ═══════════════════
@bot.command(aliases=["ann"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def announce(ctx, channel: discord.TextChannel, *, message: str):
    """Send a rich announcement to any channel."""
    embed = make_embed(
        "📣 Announcement",
        f"{Theme.SEP}\n\n{message}\n\n{Theme.SEP}",
        Theme.GOLD,
        f"Posted by {ctx.author.display_name}"
    )
    await channel.send(embed=embed)
    e = make_embed("✅ Sent", f"Announcement delivered to {channel.mention}", Theme.SUCCESS)
    await ctx.send(embed=e, delete_after=5)
    await ctx.message.delete()

@bot.command(aliases=["am"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def announce_match(ctx, match_name: str, *, message: str):
    """Announce to a specific match channel with role ping."""
    match_key = match_name.upper()
    if match_key not in SLOT_LIST_CHANNELS:
        e = make_embed("❌ Invalid Match", "Use: `MATCH_1`, `MATCH_2`, `MATCH_3`, `MATCH_4`", Theme.ERROR)
        await ctx.send(embed=e)
        return
    channel = ctx.guild.get_channel(SLOT_LIST_CHANNELS[match_key])
    role = discord.utils.get(ctx.guild.roles, name=SLOT_ROLES.get(match_key))
    if not channel:
        await ctx.send(embed=make_embed("❌ Error", "Match channel not found.", Theme.ERROR))
        return
    display = match_key.replace("_", " ")
    embed = make_embed(
        f"📢 {display} — Announcement",
        f"{Theme.SEP}\n\n{message}\n\n{Theme.SEP}",
        Theme.ORANGE,
        f"By {ctx.author.display_name}"
    )
    ping = role.mention if role else ""
    await channel.send(content=ping, embed=embed)
    await ctx.send(embed=make_embed("✅ Sent", f"Delivered to {channel.mention}", Theme.SUCCESS), delete_after=5)
    await ctx.message.delete()

@bot.command(aliases=["aa"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def announce_all(ctx, *, message: str):
    """Broadcast an announcement to ALL match channels with role pings."""
    count = 0
    for slot_name, channel_id in SLOT_LIST_CHANNELS.items():
        channel = ctx.guild.get_channel(channel_id)
        role = discord.utils.get(ctx.guild.roles, name=SLOT_ROLES.get(slot_name))
        if not channel: continue
        display = slot_name.replace("_", " ")
        embed = make_embed(
            f"📣 {display} — Announcement",
            f"{Theme.SEP}\n\n{message}\n\n{Theme.SEP}",
            Theme.GOLD,
            f"By {ctx.author.display_name}"
        )
        ping = role.mention if role else ""
        await channel.send(content=ping, embed=embed)
        count += 1
        await asyncio.sleep(0.5)
    await ctx.send(embed=make_embed("✅ Broadcast Sent", f"Delivered to **{count}** match channels.", Theme.SUCCESS), delete_after=5)
    await ctx.message.delete()

@bot.command(aliases=["sch"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def schedule(ctx, match_name: str, time: str, map_name: str = "TBD", mode: str = "TBD"):
    """Post a match schedule card."""
    match_key = match_name.upper()
    if match_key not in SLOT_LIST_CHANNELS:
        await ctx.send(embed=make_embed("❌ Invalid Match", "Use: `MATCH_1` to `MATCH_4`", Theme.ERROR))
        return
    channel = ctx.guild.get_channel(SLOT_LIST_CHANNELS[match_key])
    role = discord.utils.get(ctx.guild.roles, name=SLOT_ROLES.get(match_key))
    if not channel: return
    display = match_key.replace("_", " ")
    count = len(data["slots"].get(match_key, []))
    embed = make_embed(
        f"📅 {display} — Match Schedule",
        f"{Theme.SEP}",
        Theme.PREMIUM,
        "⏰ Be ready 10 mins before match time!"
    )
    embed.add_field(name="⏰ Time", value=f"```{time}```", inline=True)
    embed.add_field(name="🗺️ Map", value=f"```{map_name}```", inline=True)
    embed.add_field(name="🎮 Mode", value=f"```{mode}```", inline=True)
    embed.add_field(name="👥 Teams", value=f"{Theme.bar(count, MAX_SLOTS)}", inline=False)
    ping = role.mention if role else ""
    await channel.send(content=ping, embed=embed)
    await ctx.send(embed=make_embed("✅ Schedule Posted", f"Sent to {channel.mention}", Theme.SUCCESS), delete_after=5)
    await ctx.message.delete()

@bot.command(aliases=["r"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def room(ctx, match_name: str, room_id: str, password: str):
    """Post Room ID & Password."""
    match_key = match_name.upper()
    if match_key not in ROOM_CHANNELS:
        await ctx.send(embed=make_embed("❌ Invalid Match", "Use: `MATCH_1` to `MATCH_4`", Theme.ERROR))
        return
    channel = ctx.guild.get_channel(ROOM_CHANNELS[match_key])
    role = discord.utils.get(ctx.guild.roles, name=SLOT_ROLES.get(match_key))
    if not channel: return
    display = match_key.replace("_", " ")
    embed = make_embed(
        f"🔐 {display} — Room Credentials",
        f"{Theme.SEP}\n\n"
        f"⚠️ **CONFIDENTIAL** — Do NOT share outside this channel!",
        Theme.SUCCESS,
        f"Posted by {ctx.author.display_name}"
    )
    embed.add_field(name="🆔 Room ID", value=f"```fix\n{room_id}\n```", inline=True)
    embed.add_field(name="🔒 Password", value=f"```fix\n{password}\n```", inline=True)
    ping = role.mention if role else ""
    await channel.send(content=ping, embed=embed)
    await ctx.send(embed=make_embed("✅ Room Details Sent", f"Delivered to {channel.mention}", Theme.SUCCESS), delete_after=5)
    await ctx.message.delete()

# ═══════════════════ 11. SMART COMMANDS ═══════════════════
@bot.command(name="status", aliases=["st"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def bot_status(ctx):
    """Show a live dashboard of all matches."""
    reg_status = "🟢 OPEN" if REGISTRATION_OPEN else "🔴 CLOSED"
    total_teams = len(data["teams"])
    total_booked = sum(len(v) for v in data["slots"].values())
    total_cap = MAX_SLOTS * len(SLOT_LIST_CHANNELS)
    embed = make_embed(
        "📊 Tournament Dashboard",
        f"{Theme.SEP}\n\n"
        f"**Registration:** {reg_status}\n"
        f"**Registered Teams:** `{total_teams}`\n"
        f"**Overall Fill:** {Theme.bar(total_booked, total_cap)}\n\n"
        f"{Theme.THIN_SEP}",
        Theme.PREMIUM
    )
    for slot_name in SLOT_LIST_CHANNELS:
        count = len(data["slots"].get(slot_name, []))
        status = Theme.match_status(count, MAX_SLOTS)
        bar = Theme.bar(count, MAX_SLOTS)
        display = slot_name.replace("_", " ")
        embed.add_field(
            name=f"{display}",
            value=f"{status}\n{bar}",
            inline=True
        )
    await ctx.send(embed=embed)

@bot.command(name="myteam", aliases=["mt"])
async def my_team(ctx):
    """View your own team info and booked matches."""
    uid = str(ctx.author.id)
    if uid not in data["teams"]:
        e = make_embed("❌ No Team Found", "You haven't registered a team yet.\nHead to the registration channel to get started!", Theme.ERROR)
        await ctx.send(embed=e, delete_after=10)
        return
    info = data["teams"][uid]
    booked = info.get("booked_slots", [])
    players = info.get("players", [])
    paid_status = "✅ Approved" if info.get("paid", False) else "❌ Pending Payment"
    roster = "\n".join([f"` {i+1} ` {p}" for i, p in enumerate(players)]) or "No players added"
    match_list = "\n".join([f"• {s.replace('_', ' ')}" for s in booked]) if booked else "*No matches booked*"
    embed = make_embed(
        f"🏷️ {info['team']}",
        f"{Theme.SEP}\n\n"
        f"**👥 Squad Roster:**\n{roster}\n\n"
        f"**💰 Payment:** {paid_status}\n\n"
        f"{Theme.THIN_SEP}\n\n"
        f"**🎮 Active Matches:**\n{match_list}",
        Theme.TEAL
    )
    last = info.get("last_updated", "Unknown")
    if last != "Unknown":
        embed.set_footer(text=f"Registered: {last[:10]} • {Theme.FOOTER}")
    await ctx.send(embed=embed, delete_after=30)

@bot.command(aliases=["ti", "info"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def teaminfo(ctx, *, team_name: str):
    """Admin lookup of a team by name."""
    search = team_name.strip().lower()
    for uid, info in data["teams"].items():
        if info.get("team", "").strip().lower() == search:
            players = info.get("players", [])
            booked = info.get("booked_slots", [])
            paid_status = "✅ Approved" if info.get("paid", False) else "❌ Pending"
            roster = "\n".join([f"` {i+1} ` {p}" for i, p in enumerate(players)]) or "None"
            matches = "\n".join([f"• {s.replace('_', ' ')}" for s in booked]) if booked else "None"
            embed = make_embed(
                f"🔍 Team — {info['team']}",
                f"{Theme.SEP}\n\n"
                f"**👤 Leader:** <@{uid}>\n"
                f"**🆔 User ID:** `{uid}`\n"
                f"**💰 Payment:** {paid_status}\n\n"
                f"**👥 Players:**\n{roster}\n\n"
                f"{Theme.THIN_SEP}\n\n"
                f"**🎮 Matches:**\n{matches}",
                Theme.TEAL
            )
            await ctx.send(embed=embed)
            return
    await ctx.send(embed=make_embed("❌ Not Found", f"No team found with name **{team_name}**.", Theme.ERROR))

@bot.command(aliases=["wi"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def whois(ctx, member: discord.Member):
    """Look up which team a player belongs to."""
    uid = str(member.id)
    if uid in data["teams"]:
        info = data["teams"][uid]
        e = make_embed(
            "🔍 Player Found",
            f"**{member.display_name}** is the **leader** of team **{info['team']}**.",
            Theme.SUCCESS
        )
        await ctx.send(embed=e)
        return
    for owner_uid, info in data["teams"].items():
        players = [p.strip().lower() for p in info.get("players", [])]
        if member.display_name.strip().lower() in players or member.name.strip().lower() in players:
            e = make_embed(
                "🔍 Player Found",
                f"**{member.display_name}** is a member of team **{info['team']}**\n└ Leader: <@{owner_uid}>",
                Theme.SUCCESS
            )
            await ctx.send(embed=e)
            return
    await ctx.send(embed=make_embed("❌ Not Found", f"**{member.display_name}** is not registered in any team.", Theme.ERROR))

# ═══════════════════ 12. DATA MANAGEMENT ═══════════════════
@bot.command(aliases=["ut", "rename"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def update_team(ctx, member: discord.Member, *, new_name: str):
    """Change a team's name."""
    uid = str(member.id)
    if uid not in data["teams"]:
        await ctx.send(embed=make_embed("❌ Error", f"{member.mention} has no registered team.", Theme.ERROR))
        return
    old_name = data["teams"][uid]["team"]
    data["teams"][uid]["team"] = new_name
    data["teams"][uid]["last_updated"] = datetime.datetime.utcnow().isoformat()
    save_data(data)
    for slot_name in data["teams"][uid].get("booked_slots", []):
        await refresh_table(ctx.guild, slot_name)
    log_ch = ctx.guild.get_channel(ADMIN_LOG_CHANNEL_ID)
    if log_ch:
        log_e = make_embed("📝 Team Renamed", f"{Theme.SEP}", Theme.WARNING)
        log_e.add_field(name="Before", value=f"~~{old_name}~~", inline=True)
        log_e.add_field(name="After", value=f"**{new_name}**", inline=True)
        log_e.add_field(name="By", value=ctx.author.mention, inline=True)
        await log_ch.send(embed=log_e)
    e = make_embed("✅ Team Renamed", f"**{old_name}** → **{new_name}**", Theme.SUCCESS)
    await ctx.send(embed=e)

@bot.command(aliases=["ss", "swap"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def swap_slot(ctx, match_name: str, slot1: int, slot2: int):
    """Swap two teams in a match."""
    match_key = match_name.upper()
    if match_key not in SLOT_LIST_CHANNELS:
        await ctx.send(embed=make_embed("❌ Invalid Match", "Use valid match names.", Theme.ERROR))
        return
    slots = data["slots"].get(match_key, [])
    i1, i2 = slot1 - 1, slot2 - 1
    if i1 < 0 or i2 < 0 or i1 >= len(slots) or i2 >= len(slots):
        await ctx.send(embed=make_embed("❌ Invalid Slots", "Check slot numbers and try again.", Theme.ERROR))
        return
    slots[i1], slots[i2] = slots[i2], slots[i1]
    save_data(data)
    await refresh_table(ctx.guild, match_key)
    t1 = data["teams"].get(slots[i1], {}).get("team", "?")
    t2 = data["teams"].get(slots[i2], {}).get("team", "?")
    display = match_key.replace('_', ' ')
    e = make_embed(
        "🔀 Slots Swapped",
        f"{Theme.SEP}\n\n**{t1}** `#{slot1}` ↔ `#{slot2}` **{t2}**\n\nIn **{display}**",
        Theme.ACCENT
    )
    await ctx.send(embed=e)

@bot.command(aliases=["mtm", "move"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def move_team(ctx, member: discord.Member, from_match: str, to_match: str):
    """Move a team between matches."""
    uid = str(member.id)
    fk, tk = from_match.upper(), to_match.upper()
    if fk not in SLOT_LIST_CHANNELS or tk not in SLOT_LIST_CHANNELS:
        await ctx.send(embed=make_embed("❌ Invalid Match", "Check match names.", Theme.ERROR))
        return
    if uid not in data["slots"].get(fk, []):
        await ctx.send(embed=make_embed("❌ Not Found", f"{member.mention} is not in {fk.replace('_',' ')}.", Theme.ERROR))
        return
    if len(data["slots"].get(tk, [])) >= MAX_SLOTS:
        await ctx.send(embed=make_embed("❌ Full", f"{tk.replace('_',' ')} is full!", Theme.ERROR))
        return
    await perform_removal(ctx.guild, uid, fk)
    data["slots"][tk].append(uid)
    if tk not in data["teams"].get(uid, {}).get("booked_slots", []):
        data["teams"][uid]["booked_slots"].append(tk)
    save_data(data)
    new_role = await get_or_create_role(ctx.guild, SLOT_ROLES.get(tk))
    if new_role:
        try: await member.add_roles(new_role)
        except Exception: pass
    await refresh_table(ctx.guild, tk)
    team = data["teams"].get(uid, {}).get("team", "?")
    e = make_embed(
        "➡️ Team Moved",
        f"**{team}**\n{fk.replace('_',' ')} → {tk.replace('_',' ')}",
        Theme.ACCENT
    )
    await ctx.send(embed=e)

@bot.command(aliases=["rsm"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def reset_match(ctx, match_name: str):
    """Clear all slots in a match."""
    match_key = match_name.upper()
    if match_key not in SLOT_LIST_CHANNELS:
        await ctx.send(embed=make_embed("❌ Invalid Match", "Check match name.", Theme.ERROR))
        return
    uids = list(data["slots"].get(match_key, []))
    for uid in uids:
        await perform_removal(ctx.guild, uid, match_key)
    display = match_key.replace('_', ' ')
    e = make_embed("🔄 Match Reset", f"**{display}** cleared. **{len(uids)}** teams removed.", Theme.ORANGE)
    await ctx.send(embed=e)

@bot.command(aliases=["ar"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def add_role(ctx, member: discord.Member, *, role: discord.Role):
    """Add a specific role to a player."""
    if role in member.roles:
        await ctx.send(embed=make_embed("⚠️ Info", f"{member.mention} already has the `{role.name}` role.", Theme.WARNING))
        return
    try:
        await member.add_roles(role)
        e = make_embed("✅ Role Added", f"Successfully added `{role.name}` to {member.mention}.", Theme.SUCCESS)
        await ctx.send(embed=e)
    except discord.Forbidden:
        await ctx.send(embed=make_embed("❌ Error", "Missing permissions. Check role hierarchy.", Theme.ERROR))

@bot.command(aliases=["rr"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def remove_role(ctx, member: discord.Member, *, role: discord.Role):
    """Remove a specific role from a player."""
    if role not in member.roles:
        await ctx.send(embed=make_embed("⚠️ Info", f"{member.mention} does not have the `{role.name}` role.", Theme.WARNING))
        return
    try:
        await member.remove_roles(role)
        e = make_embed("✅ Role Removed", f"Successfully removed `{role.name}` from {member.mention}.", Theme.SUCCESS)
        await ctx.send(embed=e)
    except discord.Forbidden:
        await ctx.send(embed=make_embed("❌ Error", "Missing permissions. Check role hierarchy.", Theme.ERROR))

@bot.command(aliases=["uv"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def unverify(ctx, member: discord.Member):
    """Remove the Verified Team role from a player."""
    role = discord.utils.get(ctx.guild.roles, name=VERIFY_ROLE_NAME)
    if not role:
        await ctx.send(embed=make_embed("❌ Error", f"Role `{VERIFY_ROLE_NAME}` not found.", Theme.ERROR))
        return
    if role not in member.roles:
        await ctx.send(embed=make_embed("⚠️ Info", f"{member.mention} is not verified.", Theme.WARNING))
        return
    try:
        await member.remove_roles(role)
        e = make_embed("✅ Unverified", f"Removed the **{VERIFY_ROLE_NAME}** role from {member.mention}.", Theme.SUCCESS)
        await ctx.send(embed=e)
    except discord.Forbidden:
        await ctx.send(embed=make_embed("❌ Error", "Missing permissions to remove the verified role.", Theme.ERROR))

@bot.command(aliases=["s"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def stats(ctx):
    """Show tournament statistics."""
    total_teams = len(data["teams"])
    total_booked = sum(len(v) for v in data["slots"].values())
    total_capacity = MAX_SLOTS * len(SLOT_LIST_CHANNELS)
    fill_pct = int((total_booked / total_capacity) * 100) if total_capacity else 0
    reg_icon = "🟢 Open" if REGISTRATION_OPEN else "🔴 Closed"
    embed = make_embed(
        "📈 Tournament Statistics",
        f"{Theme.SEP}\n\n"
        f"**📋 Registered Teams:** `{total_teams}`\n"
        f"**🎮 Total Slots Filled:** `{total_booked}/{total_capacity}` ({fill_pct}%)\n"
        f"**📊 Registration:** {reg_icon}\n\n"
        f"**Overall:** {Theme.bar(total_booked, total_capacity)}\n\n"
        f"{Theme.THIN_SEP}",
        Theme.PREMIUM
    )
    for sn in SLOT_LIST_CHANNELS:
        c = len(data["slots"].get(sn, []))
        display = sn.replace("_", " ")
        status = Theme.match_status(c, MAX_SLOTS)
        embed.add_field(name=display, value=f"{status}\n{Theme.bar(c, MAX_SLOTS)}", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="export", aliases=["ex"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def export_data(ctx):
    """Export all team data as a formatted message."""
    if not data["teams"]:
        await ctx.send(embed=make_embed("❌ Empty", "No team data to export.", Theme.ERROR))
        return
    header_e = make_embed("📋 Data Export", f"Exporting **{len(data['teams'])}** teams...", Theme.ACCENT)
    await ctx.send(embed=header_e)
    lines = []
    for uid, info in data["teams"].items():
        team = info.get("team", "?")
        players = ", ".join(info.get("players", [])) or "None"
        booked = ", ".join([s.replace('_',' ') for s in info.get("booked_slots", [])]) or "None"
        paid = "✅" if info.get("paid", False) else "❌"
        lines.append(f"• **{team}** │ <@{uid}> │ {players} │ {booked} │ {paid}")
    output = "\n".join(lines)
    if len(output) > 1900:
        chunks = [output[i:i+1900] for i in range(0, len(output), 1900)]
        for chunk in chunks:
            await ctx.send(chunk)
    else:
        await ctx.send(output)

# ═══════════════════ 12B. ADMIN DM BROADCAST ═══════════════════
@bot.command(name="dm")
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def dm_broadcast(ctx, members: commands.Greedy[discord.Member], *, message: str):
    """DM a message to one or more members. Usage: !dm @user1 @user2 message: your text here"""
    if not members:
        e = make_embed(
            "⚠️ No Members Specified",
            f"**Usage:** `!dm @member1 @member2 message: your text`\n\n"
            f"You must mention at least one member before the message.",
            Theme.WARNING
        )
        await ctx.send(embed=e)
        return

    # Strip leading "message:" prefix if present (optional convenience)
    actual_message = message
    if actual_message.lower().startswith("message:"):
        actual_message = actual_message[len("message:"):].strip()

    if not actual_message:
        await ctx.send(embed=make_embed("⚠️ Empty Message", "You must provide a message to send.", Theme.WARNING))
        return

    # Send DMs
    success = []
    failed = []
    for member in members:
        try:
            dm_embed = make_embed(
                "📩 Message from Admin",
                f"{Theme.SEP}\n\n"
                f"{actual_message}\n\n"
                f"{Theme.SEP}",
                Theme.PREMIUM,
                f"Sent by {ctx.author.display_name}"
            )
            await member.send(embed=dm_embed)
            success.append(member.mention)
        except discord.Forbidden:
            failed.append(member.mention)
        except Exception:
            failed.append(member.mention)

    # Build confirmation embed
    desc = f"{Theme.SEP}\n\n"
    desc += f"**📝 Message:**\n> {actual_message}\n\n"
    desc += f"{Theme.THIN_SEP}\n\n"
    if success:
        desc += f"**✅ Delivered ({len(success)}):**\n" + ", ".join(success) + "\n\n"
    if failed:
        desc += f"**❌ Failed ({len(failed)}):**\n" + ", ".join(failed) + "\n*These members may have DMs disabled.*\n\n"
    desc += f"{Theme.SEP}"

    color = Theme.SUCCESS if not failed else (Theme.WARNING if success else Theme.ERROR)
    confirm_embed = make_embed(
        f"📨 DM Broadcast — {len(success)}/{len(members)} Delivered",
        desc,
        color
    )
    await ctx.send(embed=confirm_embed)

@bot.command(name="dmall", aliases=["dma"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def dm_all(ctx, *, message: str):
    """DM a message to ALL server members. Usage: !dmall your message here"""
    # Strip leading "message:" prefix if present (optional convenience)
    actual_message = message
    if actual_message.lower().startswith("message:"):
        actual_message = actual_message[len("message:"):].strip()

    if not actual_message:
        await ctx.send(embed=make_embed("⚠️ Empty Message", "You must provide a message to send.", Theme.WARNING))
        return

    # Filter out bots
    members = [m for m in ctx.guild.members if not m.bot]
    total = len(members)

    if total == 0:
        await ctx.send(embed=make_embed("⚠️ No Members", "No human members found in this server.", Theme.WARNING))
        return

    # Show progress embed
    progress_embed = make_embed(
        "📨 DM Broadcast — Sending...",
        f"{Theme.SEP}\n\n"
        f"**📝 Message:**\n> {actual_message}\n\n"
        f"{Theme.THIN_SEP}\n\n"
        f"⏳ Sending to **{total}** members...\n"
        f"{Theme.bar(0, total, 16)}\n\n"
        f"{Theme.SEP}",
        Theme.PREMIUM
    )
    progress_msg = await ctx.send(embed=progress_embed)

    success = 0
    failed = 0
    for i, member in enumerate(members, 1):
        try:
            dm_embed = make_embed(
                "📩 Message from Admin",
                f"{Theme.SEP}\n\n"
                f"{actual_message}\n\n"
                f"{Theme.SEP}",
                Theme.PREMIUM,
                f"Sent by {ctx.author.display_name}"
            )
            await member.send(embed=dm_embed)
            success += 1
        except Exception:
            failed += 1

        # Update progress every 10 members or on last member
        if i % 10 == 0 or i == total:
            pct = int((i / total) * 100)
            try:
                update_embed = make_embed(
                    "📨 DM Broadcast — Sending...",
                    f"{Theme.SEP}\n\n"
                    f"**📝 Message:**\n> {actual_message}\n\n"
                    f"{Theme.THIN_SEP}\n\n"
                    f"⏳ Progress: **{i}/{total}** ({pct}%)\n"
                    f"{Theme.bar(i, total, 16)}\n"
                    f"✅ {success} delivered  •  ❌ {failed} failed\n\n"
                    f"{Theme.SEP}",
                    Theme.PREMIUM
                )
                await progress_msg.edit(embed=update_embed)
            except Exception:
                pass

    # Final confirmation
    desc = f"{Theme.SEP}\n\n"
    desc += f"**📝 Message:**\n> {actual_message}\n\n"
    desc += f"{Theme.THIN_SEP}\n\n"
    desc += f"**✅ Delivered:** `{success}`\n"
    desc += f"**❌ Failed:** `{failed}`\n"
    desc += f"**👥 Total Members:** `{total}`\n\n"
    desc += f"{Theme.SEP}"

    color = Theme.SUCCESS if failed == 0 else (Theme.WARNING if success > 0 else Theme.ERROR)
    final_embed = make_embed(
        f"📨 DM Broadcast Complete — {success}/{total} Delivered",
        desc,
        color
    )
    await progress_msg.edit(embed=final_embed)

# ═══════════════════ 12C. POINTS & LEADERBOARD ═══════════════════

DEFAULT_POSITION_POINTS = {
    "1": 15, "2": 12, "3": 10, "4": 8, "5": 6,
    "6": 4, "7": 2, "8": 1, "9": 0, "10": 0,
    "11": 0, "12": 0, "13": 0, "14": 0, "15": 0, "16": 0
}

RANK_EMOJIS = {
    1: "🥇", 2: "🥈", 3: "🥉",
    4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣",
    9: "9️⃣", 10: "🔟"
}

def get_rank_emoji(rank):
    return RANK_EMOJIS.get(rank, f"`{rank}.`")

@bot.command(name="setpoints", aliases=["sp"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def set_points(ctx, kill_points: int = None):
    """View or set the kill points value. Usage: !setpoints 1"""
    ps = data.get("points_system", {})

    if kill_points is None:
        # Show current settings
        kp = ps.get("kill_points", 1)
        pp = ps.get("position_points", DEFAULT_POSITION_POINTS)
        pos_lines = []
        for pos in sorted(pp.keys(), key=lambda x: int(x)):
            pts = pp[pos]
            if pts > 0:
                medal = get_rank_emoji(int(pos))
                pos_lines.append(f"> {medal} Position **#{pos}** → `{pts}` pts")
        pos_str = "\n".join(pos_lines) if pos_lines else "> No position points set"

        embed = make_embed(
            "🏅 Current Points System",
            f"{Theme.SEP}\n\n"
            f"**💀 Kill Points:** `{kp}` per kill\n\n"
            f"**🏆 Position Points:**\n{pos_str}\n\n"
            f"{Theme.THIN_SEP}\n"
            f"*Use `!setpoints <kill_pts>` to change kill points.*\n"
            f"*Use `!setposition <pos> <pts>` to change position points.*",
            Theme.GOLD
        )
        await ctx.send(embed=embed)
        return

    if kill_points < 0:
        await ctx.send(embed=make_embed("❌ Invalid", "Kill points must be 0 or positive.", Theme.ERROR))
        return

    ps["kill_points"] = kill_points
    data["points_system"] = ps
    save_data(data)

    embed = make_embed(
        "✅ Kill Points Updated",
        f"{Theme.SEP}\n\n"
        f"**💀 Kill Points:** `{kill_points}` per kill\n\n"
        f"{Theme.SEP}",
        Theme.SUCCESS
    )
    await ctx.send(embed=embed)

@bot.command(name="setposition", aliases=["spos"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def set_position(ctx, position: int, points: int):
    """Set points for a specific position. Usage: !setposition 1 15"""
    if position < 1 or position > 16:
        await ctx.send(embed=make_embed("❌ Invalid", "Position must be between 1 and 16.", Theme.ERROR))
        return
    if points < 0:
        await ctx.send(embed=make_embed("❌ Invalid", "Points must be 0 or positive.", Theme.ERROR))
        return

    ps = data.get("points_system", {})
    if "position_points" not in ps:
        ps["position_points"] = DEFAULT_POSITION_POINTS.copy()
    ps["position_points"][str(position)] = points
    data["points_system"] = ps
    save_data(data)

    medal = get_rank_emoji(position)
    embed = make_embed(
        "✅ Position Points Updated",
        f"{Theme.SEP}\n\n"
        f"{medal} Position **#{position}** → `{points}` pts\n\n"
        f"{Theme.SEP}",
        Theme.SUCCESS
    )
    await ctx.send(embed=embed)

@bot.command(name="addresult", aliases=["ar2"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def add_result(ctx, match_name: str, team_name: str, kills: int, position: int):
    """Add a team's match result. Usage: !addresult MATCH_1 TeamName 5 1"""
    match_key = match_name.upper()
    if match_key not in SLOT_LIST_CHANNELS:
        await ctx.send(embed=make_embed("❌ Invalid Match", "Use: `MATCH_1` to `MATCH_8`", Theme.ERROR))
        return

    if position < 1 or position > 16:
        await ctx.send(embed=make_embed("❌ Invalid Position", "Position must be between 1 and 16.", Theme.ERROR))
        return

    if kills < 0:
        await ctx.send(embed=make_embed("❌ Invalid Kills", "Kills must be 0 or positive.", Theme.ERROR))
        return

    # Calculate points
    ps = data.get("points_system", {})
    kill_pts = ps.get("kill_points", 1) * kills
    pos_pts = ps.get("position_points", DEFAULT_POSITION_POINTS).get(str(position), 0)
    total_pts = kill_pts + pos_pts

    # Store result
    if "match_results" not in data:
        data["match_results"] = {}
    if match_key not in data["match_results"]:
        data["match_results"][match_key] = {}

    # Use team_name as key (lowercase for consistency)
    team_key = team_name.strip().lower()
    data["match_results"][match_key][team_key] = {
        "team_name": team_name.strip(),
        "kills": kills,
        "position": position,
        "position_points": pos_pts,
        "kill_points": kill_pts,
        "total_points": total_pts
    }
    save_data(data)

    medal = get_rank_emoji(position)
    display = match_key.replace("_", " ")
    embed = make_embed(
        f"✅ Result Added — {display}",
        f"{Theme.SEP}\n\n"
        f"**🏷️ Team:** {team_name}\n"
        f"{medal} **Position:** #{position} → `{pos_pts}` pts\n"
        f"💀 **Kills:** {kills} → `{kill_pts}` pts\n\n"
        f"**🏆 Total:** `{total_pts}` points\n\n"
        f"{Theme.SEP}",
        Theme.SUCCESS
    )
    await ctx.send(embed=embed)

@bot.command(name="matchresults", aliases=["mr"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def match_results(ctx, match_name: str):
    """Show results for a specific match. Usage: !matchresults MATCH_1"""
    match_key = match_name.upper()
    if match_key not in SLOT_LIST_CHANNELS:
        await ctx.send(embed=make_embed("❌ Invalid Match", "Use: `MATCH_1` to `MATCH_8`", Theme.ERROR))
        return

    results = data.get("match_results", {}).get(match_key, {})
    if not results:
        await ctx.send(embed=make_embed("❌ No Results", f"No results recorded for **{match_key.replace('_', ' ')}**.", Theme.ERROR))
        return

    # Sort by position
    sorted_results = sorted(results.values(), key=lambda x: x.get("position", 99))
    display = match_key.replace("_", " ")

    lines = []
    for r in sorted_results:
        pos = r.get("position", "?")
        medal = get_rank_emoji(pos) if isinstance(pos, int) else f"`{pos}.`"
        team = r.get("team_name", "?")
        kills = r.get("kills", 0)
        total = r.get("total_points", 0)
        lines.append(f"{medal} **{team}** — 💀 `{kills}` kills — 🏆 `{total}` pts")

    result_text = "\n".join(lines)
    total_kills = sum(r.get("kills", 0) for r in sorted_results)

    embed = make_embed(
        f"📊 {display} — Match Results",
        f"{Theme.SEP}\n\n"
        f"{result_text}\n\n"
        f"{Theme.THIN_SEP}\n"
        f"**Teams Recorded:** `{len(sorted_results)}`  •  **Total Kills:** `{total_kills}`\n\n"
        f"{Theme.SEP}",
        Theme.GOLD,
        f"Results for {display}"
    )
    await ctx.send(embed=embed)

@bot.command(name="leaderboard", aliases=["lb"])
async def leaderboard(ctx):
    """Show the overall tournament leaderboard."""
    all_results = data.get("match_results", {})
    if not all_results:
        await ctx.send(embed=make_embed("❌ No Results", "No match results have been recorded yet.", Theme.ERROR))
        return

    # Aggregate all teams across all matches
    team_totals = {}  # team_key -> {team_name, total_kills, total_points, matches_played, best_position}
    for match_key, results in all_results.items():
        for team_key, r in results.items():
            if team_key not in team_totals:
                team_totals[team_key] = {
                    "team_name": r.get("team_name", "?"),
                    "total_kills": 0,
                    "total_points": 0,
                    "matches_played": 0,
                    "best_position": 99,
                    "total_position_pts": 0,
                    "total_kill_pts": 0
                }
            team_totals[team_key]["total_kills"] += r.get("kills", 0)
            team_totals[team_key]["total_points"] += r.get("total_points", 0)
            team_totals[team_key]["total_position_pts"] += r.get("position_points", 0)
            team_totals[team_key]["total_kill_pts"] += r.get("kill_points", 0)
            team_totals[team_key]["matches_played"] += 1
            pos = r.get("position", 99)
            if pos < team_totals[team_key]["best_position"]:
                team_totals[team_key]["best_position"] = pos

    # Sort by total points (descending), then by kills as tiebreaker
    sorted_teams = sorted(
        team_totals.values(),
        key=lambda x: (x["total_points"], x["total_kills"]),
        reverse=True
    )

    # Build leaderboard
    lines = []
    for rank, t in enumerate(sorted_teams[:20], 1):
        medal = get_rank_emoji(rank)
        name = t["team_name"]
        if len(name) > 18:
            name = name[:16] + ".."
        pts = t["total_points"]
        kills = t["total_kills"]
        matches = t["matches_played"]
        best = t["best_position"]
        lines.append(
            f"{medal} **{name}** — `{pts}` pts  •  💀 `{kills}`  •  🎮 `{matches}` matches  •  Best: `#{best}`"
        )

    lb_text = "\n".join(lines)
    total_matches_recorded = len(all_results)
    total_teams = len(sorted_teams)

    # Highlight top 3
    podium = ""
    if len(sorted_teams) >= 3:
        podium = (
            f"\n🥇 **{sorted_teams[0]['team_name']}** — `{sorted_teams[0]['total_points']}` pts\n"
            f"🥈 **{sorted_teams[1]['team_name']}** — `{sorted_teams[1]['total_points']}` pts\n"
            f"🥉 **{sorted_teams[2]['team_name']}** — `{sorted_teams[2]['total_points']}` pts\n"
        )
    elif len(sorted_teams) >= 1:
        podium = f"\n🥇 **{sorted_teams[0]['team_name']}** — `{sorted_teams[0]['total_points']}` pts\n"

    embed = make_embed(
        "🏆 Tournament Leaderboard",
        f"{Theme.SEP}\n"
        f"{podium}\n"
        f"{Theme.THIN_SEP}\n\n"
        f"{lb_text}\n\n"
        f"{Theme.THIN_SEP}\n"
        f"**📊 Stats:** `{total_teams}` teams  •  `{total_matches_recorded}` matches recorded\n\n"
        f"{Theme.SEP}",
        Theme.GOLD,
        "🏆 Overall Tournament Standings"
    )
    await ctx.send(embed=embed)

@bot.command(name="mvp", aliases=["topper"])
async def mvp(ctx, match_name: str = None):
    """Show the MVP (top killer) of a match or overall. Usage: !mvp [MATCH_X]"""
    if match_name:
        match_key = match_name.upper()
        if match_key not in SLOT_LIST_CHANNELS:
            await ctx.send(embed=make_embed("❌ Invalid Match", "Use: `MATCH_1` to `MATCH_8`", Theme.ERROR))
            return
        results = data.get("match_results", {}).get(match_key, {})
        if not results:
            await ctx.send(embed=make_embed("❌ No Results", f"No results for **{match_key.replace('_', ' ')}**.", Theme.ERROR))
            return
        # Find top killer in this match
        top = max(results.values(), key=lambda x: x.get("kills", 0))
        display = match_key.replace("_", " ")
        embed = make_embed(
            f"⭐ MVP — {display}",
            f"{Theme.SEP}\n\n"
            f"**🏷️ Team:** {top['team_name']}\n"
            f"💀 **Kills:** `{top.get('kills', 0)}`\n"
            f"{get_rank_emoji(top.get('position', 1))} **Position:** #{top.get('position', '?')}\n"
            f"🏆 **Points:** `{top.get('total_points', 0)}`\n\n"
            f"{Theme.SEP}",
            Theme.GOLD,
            f"Match MVP — {display}"
        )
        await ctx.send(embed=embed)
    else:
        # Overall MVP — team with most total kills
        all_results = data.get("match_results", {})
        if not all_results:
            await ctx.send(embed=make_embed("❌ No Results", "No match results recorded yet.", Theme.ERROR))
            return
        team_kills = {}
        for match_key, results in all_results.items():
            for team_key, r in results.items():
                if team_key not in team_kills:
                    team_kills[team_key] = {"team_name": r.get("team_name", "?"), "total_kills": 0, "matches": 0}
                team_kills[team_key]["total_kills"] += r.get("kills", 0)
                team_kills[team_key]["matches"] += 1
        top = max(team_kills.values(), key=lambda x: x["total_kills"])
        embed = make_embed(
            "⭐ Tournament MVP",
            f"{Theme.SEP}\n\n"
            f"**🏷️ Team:** {top['team_name']}\n"
            f"💀 **Total Kills:** `{top['total_kills']}`\n"
            f"🎮 **Matches Played:** `{top['matches']}`\n"
            f"📊 **Avg Kills/Match:** `{top['total_kills'] / top['matches']:.1f}`\n\n"
            f"{Theme.SEP}",
            Theme.GOLD,
            "Overall Tournament MVP"
        )
        await ctx.send(embed=embed)

@bot.command(name="resetresults", aliases=["rr2"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def reset_results(ctx, match_name: str):
    """Clear results for a specific match. Usage: !resetresults MATCH_1"""
    match_key = match_name.upper()
    if match_key not in SLOT_LIST_CHANNELS:
        await ctx.send(embed=make_embed("❌ Invalid Match", "Use: `MATCH_1` to `MATCH_8`", Theme.ERROR))
        return

    count = len(data.get("match_results", {}).get(match_key, {}))
    if match_key in data.get("match_results", {}):
        del data["match_results"][match_key]
        save_data(data)

    display = match_key.replace("_", " ")
    embed = make_embed(
        "🔄 Results Reset",
        f"{Theme.SEP}\n\n"
        f"Cleared **{count}** team results from **{display}**.\n\n"
        f"{Theme.SEP}",
        Theme.ORANGE
    )
    await ctx.send(embed=embed)

@bot.command(name="resetallresults", aliases=["rar"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def reset_all_results(ctx):
    """Clear ALL match results and leaderboard data."""
    total_matches = len(data.get("match_results", {}))
    total_entries = sum(len(v) for v in data.get("match_results", {}).values())
    data["match_results"] = {}
    save_data(data)

    embed = make_embed(
        "🔄 All Results Reset",
        f"{Theme.SEP}\n\n"
        f"Cleared **{total_entries}** results across **{total_matches}** matches.\n"
        f"Leaderboard has been reset to zero.\n\n"
        f"{Theme.SEP}",
        Theme.ORANGE
    )
    await ctx.send(embed=embed)

@bot.command(name="postleaderboard", aliases=["plb"])
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def post_leaderboard(ctx, channel: discord.TextChannel):
    """Post the leaderboard to a specific channel. Usage: !postleaderboard #channel"""
    # Reuse leaderboard logic
    all_results = data.get("match_results", {})
    if not all_results:
        await ctx.send(embed=make_embed("❌ No Results", "No match results have been recorded yet.", Theme.ERROR))
        return

    team_totals = {}
    for match_key, results in all_results.items():
        for team_key, r in results.items():
            if team_key not in team_totals:
                team_totals[team_key] = {
                    "team_name": r.get("team_name", "?"),
                    "total_kills": 0,
                    "total_points": 0,
                    "matches_played": 0,
                    "best_position": 99
                }
            team_totals[team_key]["total_kills"] += r.get("kills", 0)
            team_totals[team_key]["total_points"] += r.get("total_points", 0)
            team_totals[team_key]["matches_played"] += 1
            pos = r.get("position", 99)
            if pos < team_totals[team_key]["best_position"]:
                team_totals[team_key]["best_position"] = pos

    sorted_teams = sorted(
        team_totals.values(),
        key=lambda x: (x["total_points"], x["total_kills"]),
        reverse=True
    )

    lines = []
    for rank, t in enumerate(sorted_teams[:20], 1):
        medal = get_rank_emoji(rank)
        name = t["team_name"]
        if len(name) > 18:
            name = name[:16] + ".."
        pts = t["total_points"]
        kills = t["total_kills"]
        lines.append(f"{medal} **{name}** — `{pts}` pts  •  💀 `{kills}` kills")

    lb_text = "\n".join(lines)

    podium = ""
    if len(sorted_teams) >= 3:
        podium = (
            f"\n🥇 **{sorted_teams[0]['team_name']}** — `{sorted_teams[0]['total_points']}` pts\n"
            f"🥈 **{sorted_teams[1]['team_name']}** — `{sorted_teams[1]['total_points']}` pts\n"
            f"🥉 **{sorted_teams[2]['team_name']}** — `{sorted_teams[2]['total_points']}` pts\n"
        )

    embed = make_embed(
        "🏆 Tournament Leaderboard",
        f"{Theme.SEP}\n"
        f"{podium}\n"
        f"{Theme.THIN_SEP}\n\n"
        f"{lb_text}\n\n"
        f"{Theme.SEP}",
        Theme.GOLD,
        "🏆 Overall Tournament Standings"
    )
    await channel.send(embed=embed)
    await ctx.send(embed=make_embed("✅ Posted", f"Leaderboard posted to {channel.mention}", Theme.SUCCESS), delete_after=5)
    await ctx.message.delete()

# ═══════════════════ 13. INTERACTIVE HELP MENU ═══════════════════
bot.remove_command("help")

class HelpDropdown(discord.ui.Select):
    def __init__(self, is_admin):
        options = [
            discord.SelectOption(label="Overview", description="Bot info & quick start guide", emoji="🏠", value="overview", default=True),
            discord.SelectOption(label="Player Commands (3)", description="Commands available to everyone", emoji="👤", value="player"),
        ]
        if is_admin:
            options.extend([
                discord.SelectOption(label="Payment Management (5)", description="Approve, pending, UPI settings", emoji="💰", value="payment"),
                discord.SelectOption(label="Announcements (5)", description="Announce, schedule & room details", emoji="📢", value="announce"),
                discord.SelectOption(label="Match Management (12)", description="Setup, lock, notify, roles", emoji="🔧", value="match"),
                discord.SelectOption(label="Leaderboard (9)", description="Points, results, MVP, rankings", emoji="🏆", value="leaderboard"),
                discord.SelectOption(label="DM Broadcast (2)", description="DM specific or all members", emoji="📩", value="dm"),
                discord.SelectOption(label="Data & Lookup (8)", description="Stats, search, export data", emoji="📊", value="data"),
            ])
        super().__init__(placeholder="📖 Select a category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        pages = {
            "overview": self._overview,
            "player": self._player,
            "payment": self._payment,
            "announce": self._announce,
            "match": self._match,
            "leaderboard": self._leaderboard,
            "dm": self._dm,
            "data": self._data,
        }
        embed = pages.get(self.values[0], self._overview)()
        await interaction.response.edit_message(embed=embed)

    def _overview(self):
        # Live stats
        total_teams = len(data.get("teams", {}))
        total_booked = sum(len(v) for v in data.get("slots", {}).values())
        total_cap = MAX_SLOTS * len(SLOT_LIST_CHANNELS)
        fill_pct = int((total_booked / total_cap) * 100) if total_cap else 0
        reg_icon = "🟢 Open" if REGISTRATION_OPEN else "🔴 Closed"
        paid_count = sum(1 for t in data.get("teams", {}).values() if t.get("paid"))
        pending_count = total_teams - paid_count

        embed = make_embed(
            "⚡ Tournament Bot — Command Center",
            f"{Theme.SEP}\n\n"
            "Welcome to the **Tournament Bot**! This bot manages team registration, "
            "match slot booking, and tournament operations.\n\n"
            f"{Theme.THIN_SEP}\n\n"
            "**📊 Live Stats:**\n"
            f"> 📋 Registered Teams: **{total_teams}**\n"
            f"> 🎮 Slots Filled: **{total_booked}/{total_cap}** ({fill_pct}%) {Theme.bar(total_booked, total_cap, 10)}\n"
            f"> 💰 Paid: **{paid_count}** • Pending: **{pending_count}**\n"
            f"> 📝 Registration: {reg_icon}\n\n"
            f"{Theme.THIN_SEP}\n\n"
            "**🚀 Quick Start:**\n"
            "> `1.` Get verified in the verification channel\n"
            "> `2.` Register your team\n"
            "> `3.` Select Part 1 or Part 2\n"
            "> `4.` Pay ₹ platform fee via UPI\n"
            "> `5.` Open a ticket & send payment screenshot\n"
            "> `6.` Admin approves → auto-added to your part's matches\n"
            "> `7.` Wait for room details before match\n\n"
            "*Use the dropdown below to explore all commands.*\n\n"
            f"{Theme.SEP}",
            Theme.PREMIUM,
            "📖 Page 1/7 • Overview"
        )
        return embed

    def _player(self):
        embed = make_embed(
            "👤 Player Commands  ·  `3 commands`",
            f"{Theme.SEP}\n\n"
            "**`!myteam`** · aliases: `!mt`\n"
            "╰ View your team info, players, payment status & active matches\n\n"
            "**`!leaderboard`** · aliases: `!lb`\n"
            "╰ View the overall tournament leaderboard & rankings\n\n"
            "**`!help`**\n"
            "╰ Show this interactive help menu\n\n"
            f"{Theme.THIN_SEP}\n\n"
            "**🎮 Interactive Features:**\n"
            "> 📝 Register button → Team form → Part selection → Payment\n"
            "> ⚡ Auto-assign button → Instantly join an open match\n"
            "> 🗑️ Leave match dropdown → Cancel specific or all matches\n"
            "> 🛡️ Verify button → Squad consent via DMs\n"
            "> 🎫 Ticket button → Open payment ticket\n\n"
            "💡 *All interactive features use buttons & dropdowns in their channels.*",
            Theme.TEAL,
            "📖 Page 2/8 • Player Commands"
        )
        return embed

    def _payment(self):
        embed = make_embed(
            "💰 Payment Management  ·  `5 commands`",
            f"{Theme.SEP}\n\n"
            "**`!approve @user`** · aliases: `!ap`\n"
            "╰ Approve payment → auto-add to selected part's 4 matches + DM notification\n\n"
            "**`!unapprove @user`** · aliases: `!uap`\n"
            "╰ Reverse approval → remove from all matches + revoke roles\n\n"
            "**`!pending`** · aliases: `!pd`\n"
            "╰ Show all teams with unpaid/pending payments\n\n"
            "**`!setupi <upi_id> <amount> <name>`** · aliases: `!supi`\n"
            "╰ Configure UPI payment details shown to players\n\n"
            "**`!viewupi`** · aliases: `!vupi`\n"
            "╰ View current UPI settings\n\n"
            f"{Theme.THIN_SEP}\n\n"
            "**💡 Payment Flow:**\n"
            "> Register → Select Part → Pay UPI → Open Ticket → Screenshot → Admin Approves",
            Theme.GOLD,
            "📖 Page 3/8 • Payment Management"
        )
        return embed

    def _announce(self):
        embed = make_embed(
            "📢 Announcements  ·  `5 commands`",
            f"{Theme.SEP}\n\n"
            "**`!announce #channel message`** · aliases: `!ann`\n"
            "╰ Send a rich announcement embed to any channel\n\n"
            "**`!announce_match MATCH_X message`** · aliases: `!am`\n"
            "╰ Announce to a specific match channel with role ping\n\n"
            "**`!announce_all message`** · aliases: `!aa`\n"
            "╰ Broadcast to ALL match channels simultaneously\n\n"
            "**`!schedule MATCH_X time map mode`** · aliases: `!sch`\n"
            "╰ Post a detailed match schedule card\n\n"
            "**`!room MATCH_X id password`** · aliases: `!r`\n"
            "╰ Send confidential room credentials to players\n\n"
            f"{Theme.THIN_SEP}\n\n"
            "**📝 Examples:**\n"
            "> `!announce #general Tournament starts at 8 PM!`\n"
            "> `!room MATCH_1 12345678 abc123`",
            Theme.ORANGE,
            "📖 Page 4/8 • Announcements"
        )
        return embed

    def _match(self):
        embed = make_embed(
            "🔧 Match Management  ·  `12 commands`",
            f"{Theme.SEP}\n\n"
            "**⚙️ Setup & Panels**\n"
            "> `!setup` (`!set`) — Initialize all bot panels\n"
            "> `!setup_verify` (`!sv`) — Setup verification panel\n"
            "> `!init_tables` (`!it`) — Refresh all live tables\n\n"
            "**🔒 Registration Control**\n"
            "> `!lock` (`!l`) — Lock registration & claims\n"
            "> `!unlock` (`!ul`) — Unlock registration\n"
            "> `!notify_start <mins> [MATCH_X]` (`!ns`) — Alert players\n\n"
            "**🗑️ Slot Management**\n"
            "> `!force_remove MATCH_X <slot#>` (`!fr`) — Remove a team\n"
            "> `!reset_match MATCH_X` (`!rsm`) — Clear all slots\n\n"
            "**🎮 Part Configuration**\n"
            "> `!rename_part <1|2> <name>` (`!rp`) — Rename Part 1/2\n"
            "> `!toggle_part <1|2>` (`!tp`) — Open/Close Part 1/2\n\n"
            "**🛡️ Verification**\n"
            "> `!set_timeout <min>` (`!stt`) — Set verify timeout\n"
            "> `!unverify @user` (`!uv`) — Remove verified role\n\n"
            "**🧹 Utility**\n"
            "> `!clear [count]` (`!c`) — Purge messages",
            Theme.ROSE,
            "📖 Page 5/8 • Match Management"
        )
        return embed

    def _leaderboard(self):
        embed = make_embed(
            "🏆 Leaderboard & Results  ·  `9 commands`",
            f"{Theme.SEP}\n\n"
            "**⚙️ Points Configuration**\n"
            "> `!setpoints [kill_pts]` (`!sp`) — View/set kill points\n"
            "> `!setposition <pos> <pts>` (`!spos`) — Set position points\n\n"
            "**📝 Match Results**\n"
            "> `!addresult MATCH_X <team> <kills> <pos>` (`!ar2`) — Add result\n"
            "> `!matchresults MATCH_X` (`!mr`) — View match results\n\n"
            "**🏆 Rankings**\n"
            "> `!leaderboard` (`!lb`) — Overall standings (public)\n"
            "> `!mvp [MATCH_X]` — Match or overall MVP\n"
            "> `!postleaderboard #channel` (`!plb`) — Post to channel\n\n"
            "**🔄 Reset**\n"
            "> `!resetresults MATCH_X` (`!rr2`) — Clear match results\n"
            "> `!resetallresults` (`!rar`) — Clear all results\n\n"
            f"{Theme.THIN_SEP}\n\n"
            "**📝 Example Workflow:**\n"
            "> `!addresult MATCH_1 TeamAlpha 8 1`\n"
            "> `!addresult MATCH_1 TeamBeta 5 2`\n"
            "> `!matchresults MATCH_1` → View results\n"
            "> `!leaderboard` → See overall rankings",
            Theme.GOLD,
            "📖 Page 6/8 • Leaderboard"
        )
        return embed

    def _dm(self):
        embed = make_embed(
            "📩 DM Broadcast  ·  `2 commands`",
            f"{Theme.SEP}\n\n"
            "**`!dm @user1 @user2 message`**\n"
            "╰ Send a DM to specific mentioned members\n"
            "╰ Works with 1 or multiple members\n\n"
            "**`!dmall message`** · aliases: `!dma`\n"
            "╰ Broadcast a DM to **all** server members\n"
            "╰ Live progress bar while sending\n"
            "╰ Skips bots automatically\n\n"
            f"{Theme.THIN_SEP}\n\n"
            "**📝 Examples:**\n"
            "> `!dm @Player1 @Player2 Your match starts in 10 mins!`\n"
            "> `!dmall Tournament starts tomorrow at 8 PM IST!`\n\n"
            "💡 *The `message:` prefix is optional.*\n"
            "💡 *Bot reports delivery failures if a member has DMs disabled.*",
            Theme.PREMIUM,
            "📖 Page 7/8 • DM Broadcast"
        )
        return embed

    def _data(self):
        embed = make_embed(
            "📊 Data & Lookup  ·  `8 commands`",
            f"{Theme.SEP}\n\n"
            "**📈 Dashboards**\n"
            "> `!status` (`!st`) — Live tournament dashboard\n"
            "> `!stats` (`!s`) — Detailed statistics overview\n\n"
            "**🔍 Lookup**\n"
            "> `!teaminfo <name>` (`!ti`) — Search team by name\n"
            "> `!whois @user` (`!wi`) — Find a player's team\n\n"
            "**✏️ Edit**\n"
            "> `!update_team @user <NewName>` (`!ut`) — Rename team\n"
            "> `!swap_slot MATCH_X <s1> <s2>` (`!ss`) — Swap two slots\n"
            "> `!move_team @user <FROM> <TO>` (`!mtm`) — Transfer team\n\n"
            "**📋 Export**\n"
            "> `!export` (`!ex`) — Export all team data\n\n"
            f"{Theme.THIN_SEP}\n\n"
            "💡 *All lookup commands support team names and @mentions.*",
            Theme.ACCENT,
            "📖 Page 8/8 • Data & Lookup"
        )
        return embed

class HelpQuickButtons(discord.ui.View):
    """Quick action buttons shown below the help menu."""
    def __init__(self, is_admin):
        super().__init__(timeout=120)
        self.is_admin = is_admin
        self.add_item(HelpDropdown(is_admin))

    @discord.ui.button(label="📊 Status", style=discord.ButtonStyle.secondary, row=2)
    async def quick_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        reg_status = "🟢 OPEN" if REGISTRATION_OPEN else "🔴 CLOSED"
        total_teams = len(data["teams"])
        total_booked = sum(len(v) for v in data["slots"].values())
        total_cap = MAX_SLOTS * len(SLOT_LIST_CHANNELS)
        paid = sum(1 for t in data["teams"].values() if t.get("paid"))
        embed = make_embed(
            "📊 Quick Status",
            f"{Theme.SEP}\n\n"
            f"**Registration:** {reg_status}\n"
            f"**Teams:** `{total_teams}` ({paid} paid)\n"
            f"**Slots:** `{total_booked}/{total_cap}` {Theme.bar(total_booked, total_cap)}\n\n"
            f"{Theme.SEP}",
            Theme.PREMIUM
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🏷️ My Team", style=discord.ButtonStyle.secondary, row=2)
    async def quick_myteam(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid not in data["teams"]:
            await interaction.response.send_message(
                embed=make_embed("❌ No Team", "You haven't registered yet.", Theme.ERROR),
                ephemeral=True
            )
            return
        info = data["teams"][uid]
        players = info.get("players", [])
        booked = info.get("booked_slots", [])
        paid_status = "✅ Paid" if info.get("paid") else "❌ Pending"
        roster = ", ".join(players) or "None"
        matches = ", ".join([s.replace('_', ' ') for s in booked]) if booked else "None"
        embed = make_embed(
            f"🏷️ {info['team']}",
            f"**Players:** {roster}\n**Payment:** {paid_status}\n**Matches:** {matches}",
            Theme.TEAL
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="💰 Pending", style=discord.ButtonStyle.secondary, row=2)
    async def quick_pending(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return
        pending_teams = [(uid, info) for uid, info in data["teams"].items() if not info.get("paid")]
        if not pending_teams:
            await interaction.response.send_message(
                embed=make_embed("✅ All Clear", "No pending payments!", Theme.SUCCESS),
                ephemeral=True
            )
            return
        lines = [f"• **{info.get('team', '?')}** — <@{uid}>" for uid, info in pending_teams[:15]]
        desc = "\n".join(lines)
        if len(pending_teams) > 15:
            desc += f"\n*...and {len(pending_teams) - 15} more. Use `!pending` for full list.*"
        embed = make_embed(f"💰 Pending Payments ({len(pending_teams)})", desc, Theme.GOLD)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command()
async def help(ctx):
    """Interactive help menu with dropdown categories and quick actions."""
    is_admin = ctx.author.guild_permissions.administrator
    dropdown = HelpDropdown(is_admin)
    embed = dropdown._overview()
    await ctx.send(embed=embed, view=HelpQuickButtons(is_admin), delete_after=180)

# ═══════════════════ 14. ERROR HANDLER ═══════════════════
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        e = make_embed("🔒 Access Denied", "You don't have permission to use this command.", Theme.ERROR)
        await ctx.send(embed=e, delete_after=10)
    elif isinstance(error, commands.MissingRequiredArgument):
        e = make_embed("⚠️ Missing Argument", f"Required: `{error.param.name}`\nUse `!help` for command syntax.", Theme.WARNING)
        await ctx.send(embed=e, delete_after=10)
    elif isinstance(error, commands.CheckFailure):
        pass
    elif isinstance(error, commands.BadArgument):
        e = make_embed("⚠️ Invalid Argument", "Check your command syntax and try again.\nUse `!help` for reference.", Theme.WARNING)
        await ctx.send(embed=e, delete_after=10)
    elif isinstance(error, commands.CommandNotFound):
        e = make_embed("❓ Unknown Command", "That command doesn't exist.\nUse `!help` to see available commands.", Theme.DARK)
        await ctx.send(embed=e, delete_after=10)
    else:
        e = make_embed("❌ Error", f"```{str(error)[:200]}```", Theme.ERROR)
        await ctx.send(embed=e, delete_after=15)
        print(f"[ERROR] {error}")

if __name__ == "__main__":
    keep_alive.keep_alive()  
    bot.run(TOKEN)
