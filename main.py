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
    "MATCH_4": 1459472478651945070
}

# ROOM CHANNELS
ROOM_CHANNELS = {
    "MATCH_1": 1458788771716792486,
    "MATCH_2": 1459772021448904822,
    "MATCH_3": 1459772074112454750,
    "MATCH_4": 1459772130232373512
}

# ROLES
SLOT_ROLES = {
    "MATCH_1": "Match 1 Player",
    "MATCH_2": "Match 2 Player",
    "MATCH_3": "Match 3 Player",
    "MATCH_4": "Match 4 Player"
}

VERIFY_ROLE_NAME = "Verified Team"

# --- SETTINGS ---
MAX_SLOTS = 16
DATA_FILE = "data.json"
REGISTRATION_OPEN = True
TIMEZONE_OFFSET = 5.5 # India Standard Time
DATA_EXPIRY_DAYS = 7  # Delete team data after 7 days

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
            "table_messages": {} 
        }
        with open(DATA_FILE, "w") as f:
            json.dump(default_data, f, indent=4)
        return default_data
    
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
        if "table_messages" not in data:
            data["table_messages"] = {}
        if "SLOT_1" in data["slots"]:
            new_slots = {k.replace("SLOT", "MATCH"): v for k, v in data["slots"].items()}
            data["slots"] = new_slots
            save_data(data)
        return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# ================= 3. HELPER FUNCTIONS =================
async def get_or_create_role(guild, role_name):
    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        try:
            role = await guild.create_role(name=role_name, mentionable=True)
        except: return None
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
            except: pass

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
            except: pass

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
                        except: pass
            data["slots"][slot_name] = [] 

        for uid in data["teams"]:
            data["teams"][uid]["booked_slots"] = []

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

# ═══════════════════ 7. VERIFICATION SYSTEM ═══════════════════
class PlayerSelect(ui.UserSelect):
    def __init__(self, team_name):
        self.team_name = team_name
        super().__init__(placeholder="🎯 Select the 4 squad members...", min_values=4, max_values=4)

    async def callback(self, interaction: discord.Interaction):
        role = discord.utils.get(interaction.guild.roles, name=VERIFY_ROLE_NAME)
        if not role:
            e = make_embed("❌ Configuration Error", f"Role `{VERIFY_ROLE_NAME}` not found. Contact an admin.", Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        members = self.values

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

        await interaction.response.defer(ephemeral=True)

        member_details = []
        for member in members:
            try:
                await member.add_roles(role)
                member_details.append(f"╰ {member.mention} • `{member.name}`")
            except discord.Forbidden:
                e = make_embed("❌ Permission Error", "Bot lacks permission to assign roles. Contact an admin.", Theme.ERROR)
                await interaction.followup.send(embed=e, ephemeral=True)
                return

        player_names_str = "\n".join(member_details)

        log_channel = interaction.guild.get_channel(VERIFIED_TEAM_LOG_ID)
        if log_channel:
            log_embed = make_embed(
                "🛡️ New Team Verified",
                f"{Theme.SEP}",
                Theme.GOLD,
                f"Verified by {interaction.user.name}"
            )
            log_embed.add_field(name="🏷️ Team Name", value=f"**{self.team_name}**", inline=False)
            log_embed.add_field(name="👥 Verified Players", value=player_names_str, inline=False)
            await log_channel.send(embed=log_embed)

        embed = make_embed(
            f"✅ Team Verified — {self.team_name}",
            f"**Role Granted:** {role.mention}\n{Theme.THIN_SEP}\n\n**Squad Members:**\n{player_names_str}",
            Theme.SUCCESS
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

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
            await log_channel.send(embed=log_e)

        players_list = [p for p in players_input if p]
        roster = "\n".join([f"` {i+1} ` {p}" for i, p in enumerate(players_list)]) or "Solo player"
        e = make_embed(
            f"✅ Team Registered — {self.team.value}",
            f"{Theme.SEP}\n\n**Squad Roster:**\n{roster}\n\n{Theme.THIN_SEP}\n🎮 **Select a match below to claim your slot!**",
            Theme.SUCCESS
        )
        await interaction.response.send_message(embed=e, view=SlotSelectView(), ephemeral=True)

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
    def __init__(self):
        super().__init__(timeout=60)
        for s in SLOT_LIST_CHANNELS:
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
        assigned = None
        for slot_name in SLOT_LIST_CHANNELS:
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
            e = make_embed("❌ All Full", "Every match slot is currently taken. Try again later or cancel an existing slot.", Theme.ERROR)
            await interaction.response.send_message(embed=e, ephemeral=True)

class TeamChoiceView(discord.ui.View):
    def __init__(self, team_name):
        super().__init__(timeout=60)
        self.team_name = team_name

    @discord.ui.button(label="✅ Continue with this team", style=discord.ButtonStyle.success)
    async def continue_old(self, interaction: discord.Interaction, button: discord.ui.Button):
        e = make_embed(
            f"🏷️ Using Team — {self.team_name}",
            f"Select a match below to claim your slot.",
            Theme.SUCCESS
        )
        await interaction.response.send_message(embed=e, view=SlotSelectView(), ephemeral=True)

    @discord.ui.button(label="📝 Register New Team", style=discord.ButtonStyle.primary)
    async def update_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TeamModal())

class MainRegisterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="「📝」Register Your Squad", style=discord.ButtonStyle.green, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            roster = "\n".join([f"` {i+1} ` {p}" for i, p in enumerate(players)]) or "No players"
            matches = ", ".join([s.replace('_', ' ') for s in booked]) if booked else "None"
            e = make_embed(
                f"⚠️ Already Registered — {team_name}",
                f"{Theme.SEP}\n\n**Squad Roster:**\n{roster}\n\n**Active Matches:** {matches}\n\n{Theme.THIN_SEP}\n*Choose an option below:*",
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
        e = make_embed("🎮 Available Matches", "Select a match below to claim your slot.", Theme.ACCENT)
        await interaction.response.send_message(embed=e, view=SlotSelectView(), ephemeral=True)

# ================= 9. BOT CLASS & ADMIN COMMANDS =================
class SlotBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    
    async def setup_hook(self):
        self.add_view(MainRegisterView())
        self.add_view(AutoClaimView())
        self.add_view(CancelAndClaimView())
        self.add_view(PersistentVerifyView())

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
    roster = "\n".join([f"` {i+1} ` {p}" for i, p in enumerate(players)]) or "No players added"
    match_list = "\n".join([f"• {s.replace('_', ' ')}" for s in booked]) if booked else "*No matches booked*"
    embed = make_embed(
        f"🏷️ {info['team']}",
        f"{Theme.SEP}\n\n"
        f"**👥 Squad Roster:**\n{roster}\n\n"
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
            roster = "\n".join([f"` {i+1} ` {p}" for i, p in enumerate(players)]) or "None"
            matches = "\n".join([f"• {s.replace('_', ' ')}" for s in booked]) if booked else "None"
            embed = make_embed(
                f"🔍 Team — {info['team']}",
                f"{Theme.SEP}\n\n"
                f"**👤 Leader:** <@{uid}>\n"
                f"**🆔 User ID:** `{uid}`\n\n"
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
        except: pass
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

@bot.command()
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

@bot.command(name="export")
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
        lines.append(f"• **{team}** │ <@{uid}> │ {players} │ {booked}")
    output = "\n".join(lines)
    if len(output) > 1900:
        chunks = [output[i:i+1900] for i in range(0, len(output), 1900)]
        for chunk in chunks:
            await ctx.send(chunk)
    else:
        await ctx.send(output)

# ═══════════════════ 13. INTERACTIVE HELP MENU ═══════════════════
bot.remove_command("help")

class HelpDropdown(discord.ui.Select):
    def __init__(self, is_admin):
        options = [
            discord.SelectOption(label="Overview", description="Bot info & quick start", emoji="🏠", value="overview", default=True),
            discord.SelectOption(label="Player Commands", description="Commands for everyone", emoji="👤", value="player"),
        ]
        if is_admin:
            options.extend([
                discord.SelectOption(label="Announcements", description="Announce & schedule", emoji="📢", value="announce"),
                discord.SelectOption(label="Match Management", description="Setup, lock, notify", emoji="🔧", value="match"),
                discord.SelectOption(label="Data & Lookup", description="Stats, search, export", emoji="📊", value="data"),
            ])
        super().__init__(placeholder="📖 Select a category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        pages = {
            "overview": self._overview,
            "player": self._player,
            "announce": self._announce,
            "match": self._match,
            "data": self._data,
        }
        embed = pages.get(self.values[0], self._overview)()
        await interaction.response.edit_message(embed=embed)

    def _overview(self):
        return make_embed(
            "⚡ Tournament Bot — Command Center",
            f"{Theme.SEP}\n\n"
            "Welcome to the **Tournament Bot**! This bot manages team registration, "
            "match slot booking, and tournament operations.\n\n"
            f"{Theme.THIN_SEP}\n\n"
            "**🚀 Quick Start:**\n"
            "> `1.` Get verified in the verification channel\n"
            "> `2.` Register your team\n"
            "> `3.` Claim a match slot\n"
            "> `4.` Wait for room details before match\n\n"
            "*Use the dropdown below to explore commands.*",
            Theme.PREMIUM
        )

    def _player(self):
        return make_embed(
            "👤 Player Commands",
            f"{Theme.SEP}\n\n"
            "**`!myteam`**\n╰ View your team info, players & matches\n\n"
            "**`!help`**\n╰ Show this interactive help menu\n\n"
            f"{Theme.THIN_SEP}\n"
            "💡 *Use the buttons in registration & cancel channels for slot management.*",
            Theme.TEAL
        )

    def _announce(self):
        return make_embed(
            "📢 Announcement Commands",
            f"{Theme.SEP}\n\n"
            "**`!announce #channel message`**\n╰ Send a rich announcement to any channel\n\n"
            "**`!announce_match MATCH_X message`**\n╰ Announce to a specific match with role ping\n\n"
            "**`!announce_all message`**\n╰ Broadcast to all match channels\n\n"
            "**`!schedule MATCH_X time map mode`**\n╰ Post a match schedule card\n\n"
            "**`!room MATCH_X id password`**\n╰ Send room credentials to players",
            Theme.ORANGE
        )

    def _match(self):
        return make_embed(
            "🔧 Match Management",
            f"{Theme.SEP}\n\n"
            "**`!setup`** — Initialize all bot panels\n"
            "**`!setup_verify`** — Setup verification panel\n"
            "**`!init_tables`** — Refresh all live tables\n"
            "**`!lock`** / **`!unlock`** — Toggle registration\n"
            "**`!notify_start mins [MATCH_X]`** — Alert players\n"
            "**`!force_remove MATCH_X slot#`** — Remove a team\n"
            "**`!reset_match MATCH_X`** — Clear all slots\n"
            "**`!add_role @user @role`** — Add a role to player\n"
            "**`!remove_role @user @role`** — Remove a role from player\n"
            "**`!unverify @user`** — Remove verified role\n"
            "**`!clear [count]`** — Purge messages",
            Theme.ROSE
        )

    def _data(self):
        return make_embed(
            "📊 Data & Lookup",
            f"{Theme.SEP}\n\n"
            "**`!status`** — Live tournament dashboard\n"
            "**`!stats`** — Statistics overview\n"
            "**`!teaminfo name`** — Lookup team by name\n"
            "**`!whois @user`** — Find a player's team\n"
            "**`!update_team @user NewName`** — Rename team\n"
            "**`!swap_slot MATCH_X s1 s2`** — Swap two slots\n"
            "**`!move_team @user FROM TO`** — Transfer team\n"
            "**`!export`** — Export all team data",
            Theme.ACCENT
        )

class HelpView(discord.ui.View):
    def __init__(self, is_admin):
        super().__init__(timeout=120)
        self.add_item(HelpDropdown(is_admin))

@bot.command()
async def help(ctx):
    """Interactive help menu with dropdown categories."""
    is_admin = ctx.author.guild_permissions.administrator
    embed = HelpDropdown(is_admin)._overview()
    await ctx.send(embed=embed, view=HelpView(is_admin), delete_after=120)

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
