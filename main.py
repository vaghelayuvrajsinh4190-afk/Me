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

# ================= 4. LIVE TABLE REFRESH =================
async def refresh_table(guild, slot_name):
    channel_id = SLOT_LIST_CHANNELS.get(slot_name)
    if not channel_id: return
    channel = guild.get_channel(channel_id)
    if not channel: return

    registered_uids = data["slots"].get(slot_name, [])
    table_lines = [f"{'NO.':<3} | {'TEAM NAME'}", "-" * 30]
    
    for i in range(MAX_SLOTS):
        slot_num = i + 1
        if i < len(registered_uids):
            uid = registered_uids[i]
            team_name = data["teams"].get(uid, {}).get("team", "Unknown")
            team_name = (team_name[:18] + '..') if len(team_name) > 18 else team_name
            table_lines.append(f"{slot_num:02d}  | {team_name}")
        else:
            table_lines.append(f"{slot_num:02d}  | [ OPEN ]")

    tabular_data = "\n".join(table_lines)
    display_name = slot_name.replace("_", " ")
    count = len(registered_uids)
    color = discord.Color.green() if count < MAX_SLOTS else discord.Color.red()
    status = "🟢 Open" if count < MAX_SLOTS else "🔴 Full"

    embed = discord.Embed(
        title=f"🏆 {display_name} Live List",
        description=f"**Status:** {status}\n**Filled:** {count}/{MAX_SLOTS}",
        color=color
    )
    embed.add_field(name="Registered Teams", value=f"```text\n{tabular_data}\n```", inline=False)
    embed.set_footer(text="Updates automatically • Do not type here")

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

    # Save Data
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

# ================= 7. VERIFICATION SYSTEM =================
class PlayerSelect(ui.UserSelect):
    def __init__(self, team_name):
        self.team_name = team_name
        super().__init__(placeholder="Select the 4 Players...", min_values=4, max_values=4)

    async def callback(self, interaction: discord.Interaction):
        role = discord.utils.get(interaction.guild.roles, name=VERIFY_ROLE_NAME)
        if not role:
            await interaction.response.send_message(f"❌ Error: Role '{VERIFY_ROLE_NAME}' not found.", ephemeral=True)
            return

        members = self.values
        await interaction.response.defer(ephemeral=True)

        for member in members:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                await interaction.followup.send("❌ Error: Check Bot permissions.", ephemeral=True)
                return

        player_names = ", ".join([m.mention for m in members])
        embed = discord.Embed(
            title=f"✅ Team Verified: {self.team_name}",
            description=f"**Role Given:** {role.mention}\n**Players:** {player_names}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class PlayerSelectView(ui.View):
    def __init__(self, team_name):
        super().__init__(timeout=60)
        self.add_item(PlayerSelect(team_name))

class TeamNameModal(ui.Modal, title="Step 1: Team Name"):
    name_input = ui.TextInput(label="Enter Team Name", placeholder="e.g. Galaxy Crows", max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        team_name = self.name_input.value
        await interaction.response.send_message(
            f"Please select the **4 players** for **{team_name}** below:", 
            view=PlayerSelectView(team_name), 
            ephemeral=True
        )

class PersistentVerifyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) 

    @ui.button(label="Verify Team", style=discord.ButtonStyle.green, emoji="🛡️", custom_id="verify_btn_1")
    async def verify_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TeamNameModal())

# ================= 8. SLOT VIEWS =================
class TeamModal(discord.ui.Modal, title="Update / New Team"):
    team = discord.ui.TextInput(label="Team Name", placeholder="Enter your team name")
    p1 = discord.ui.TextInput(label="Player 1 (IGL)", placeholder="IGN / Discord ID")
    p2 = discord.ui.TextInput(label="Player 2", placeholder="IGN", required=False)
    p3 = discord.ui.TextInput(label="Player 3", placeholder="IGN", required=False)
    p4 = discord.ui.TextInput(label="Player 4", placeholder="IGN", required=False)
    
    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        data["teams"][uid] = {
            "team": self.team.value,
            "players": [self.p1.value, self.p2.value, self.p3.value, self.p4.value],
            "booked_slots": [],
            "last_updated": datetime.datetime.utcnow().isoformat()
        }
        save_data(data)
        
        log_channel = interaction.guild.get_channel(ADMIN_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(title="🆕 Team Registered/Updated", color=discord.Color.blue())
            embed.add_field(name="Team", value=self.team.value)
            embed.add_field(name="User", value=f"<@{uid}>")
            await log_channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Team **{self.team.value}** Saved! Select a Match:", 
            view=SlotSelectView(), 
            ephemeral=True
        )

class SlotButton(discord.ui.Button):
    def __init__(self, slot):
        count = len(data["slots"][slot])
        display_name = slot.replace("_", " ") 
        label = f"{display_name} ({count}/{MAX_SLOTS})"
        style = discord.ButtonStyle.green if count < MAX_SLOTS else discord.ButtonStyle.red
        super().__init__(label=label, style=style, disabled=(count >= MAX_SLOTS))
        self.slot = slot

    async def callback(self, interaction: discord.Interaction):
        success = await add_player_to_slot(interaction, self.slot)
        if success:
            await interaction.response.send_message(f"✅ Claimed **{self.slot}**.", ephemeral=True)
        else:
             if not interaction.response.is_done():
                 await interaction.response.send_message("❌ Failed or Full.", ephemeral=True)

class SlotSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        for s in SLOT_LIST_CHANNELS:
            self.add_item(SlotButton(s))

class AutoClaimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚡ Quick Claim (Auto-Assign)", style=discord.ButtonStyle.blurple, custom_id="auto_claim_btn")
    async def auto_claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not REGISTRATION_OPEN:
            await interaction.response.send_message("⛔ **Claims Closed.**", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid not in data["teams"]:
            await interaction.response.send_message("❌ Register first.", ephemeral=True)
            return
        assigned = None
        for slot_name in SLOT_LIST_CHANNELS:
            if len(data["slots"][slot_name]) < MAX_SLOTS and uid not in data["slots"][slot_name]:
                assigned = slot_name
                break
        if assigned:
            success = await add_player_to_slot(interaction, assigned)
            if success:
                await interaction.response.send_message(f"✅ Auto-Assigned to **{assigned}**!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ All matches are full!", ephemeral=True)

class TeamChoiceView(discord.ui.View):
    def __init__(self, team_name):
        super().__init__(timeout=60)
        self.team_name = team_name

    @discord.ui.button(label=f"🟢 Continue as", style=discord.ButtonStyle.success)
    async def continue_old(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"✅ Using team: **{self.team_name}**. Select Match:", view=SlotSelectView(), ephemeral=True)

    @discord.ui.button(label="🔵 New / Update Team", style=discord.ButtonStyle.primary)
    async def update_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TeamModal())

class MainRegisterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📝 Register Team", style=discord.ButtonStyle.green, custom_id="reg_btn")
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
            await interaction.response.send_message(
                f"⚠️ You are already registered as **{team_name}**.\nDo you want to continue or register a new team?", 
                view=TeamChoiceView(team_name), 
                ephemeral=True
            )
        else:
            await interaction.response.send_modal(TeamModal())

class CancelDropdown(discord.ui.Select):
    def __init__(self, booked_slots):
        options = []
        for slot in booked_slots:
            display_name = slot.replace("_", " ")
            options.append(discord.SelectOption(label=f"Leave {display_name}", value=slot, emoji="🗑️"))
        options.append(discord.SelectOption(label="Leave ALL Matches", value="ALL", emoji="❌"))
        super().__init__(placeholder="Select match to leave...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "ALL":
            success, msg = await remove_all_slots_logic(interaction)
        else:
            success, msg = await remove_single_slot_logic(interaction, self.values[0])
        await interaction.response.send_message(msg, ephemeral=True)

class CancelAndClaimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🗑️ Leave Match", style=discord.ButtonStyle.danger, custom_id="cancel_slot_btn")
    async def cancel_slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid not in data["teams"] or not data["teams"][uid].get("booked_slots"):
             await interaction.response.send_message("⚠️ You have no active matches.", ephemeral=True)
             return
        booked = data["teams"][uid]["booked_slots"]
        await interaction.response.send_message("Select match to leave:", view=discord.ui.View().add_item(CancelDropdown(booked)), ephemeral=True)

    @discord.ui.button(label="♻️ Join Open Match", style=discord.ButtonStyle.primary, custom_id="claim_open_btn")
    async def claim_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not REGISTRATION_OPEN:
            await interaction.response.send_message("⛔ **Claims Closed.**", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid not in data["teams"]:
            await interaction.response.send_message("❌ Register first.", ephemeral=True)
            return
        await interaction.response.send_message("✅ Checking availability...", view=SlotSelectView(), ephemeral=True)

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
            await ctx.send(f"❌ Wrong Channel! Use <#{ADMIN_COMMAND_CHANNEL_ID}>", delete_after=5)
            return False
        return True
    return commands.check(predicate)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    if not daily_reset_task.is_running():
        daily_reset_task.start()

# --- NEW COMMAND: CLEAR CHAT (ANY CHANNEL) ---
@bot.command()
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int = 100):
    """
    Clears the specified number of messages in the current channel.
    Usage: !clear 50
    """
    try:
        # Purge the channel (limit includes the command message itself)
        deleted = await ctx.channel.purge(limit=amount + 1)
        
        # Send a confirmation message and delete it after 3 seconds
        msg = await ctx.send(f"🧹 **Cleared {len(deleted)-1} messages.**")
        await asyncio.sleep(3)
        await msg.delete()
    except Exception as e:
        await ctx.send(f"❌ Error: {e}", delete_after=5)

# --- VERIFY SETUP COMMAND ---
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_verify(ctx):
    if ctx.channel.id != VERIFY_CHANNEL_ID:
        await ctx.send(f"⚠️ Warning: This is not the configured VERIFY_CHANNEL ({VERIFY_CHANNEL_ID}).")
    
    embed = discord.Embed(
        title="🛡️ Team Verification",
        description="Click the button below to verify your squad and unlock the registration channel.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=PersistentVerifyView())
    await ctx.message.delete()

# --- SLOT ADMIN COMMANDS (RESTRICTED TO ADMIN CHANNEL) ---
@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def force_remove(ctx, match_name: str, slot_number: int):
    match_key = match_name.upper()
    if match_key not in SLOT_LIST_CHANNELS:
        await ctx.send(f"❌ Invalid Name. Use: `MATCH_1`, `MATCH_2`, `MATCH_3`, `MATCH_4`")
        return
    registered_uids = data["slots"].get(match_key, [])
    index = slot_number - 1 
    if index < 0 or index >= len(registered_uids):
        await ctx.send(f"❌ Slot number {slot_number} is empty.")
        return
    target_uid = registered_uids[index]
    await perform_removal(ctx.guild, target_uid, match_key)
    team_name = data["teams"].get(target_uid, {}).get("team", "Unknown")
    await ctx.send(f"✅ **Admin Removed:** Team '{team_name}' from {match_key} (Slot {slot_number}).")

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def setup(ctx):
    await ctx.message.delete()
    msg = await ctx.send("⚙️ **Configuring...**")
    await setup_channel_perms(ctx.guild)
    
    reg_ch = ctx.guild.get_channel(REGISTRATION_CHANNEL_ID)
    if reg_ch:
        await reg_ch.purge(limit=5)
        await reg_ch.send("📝 **TOURNAMENT REGISTRATION**", view=MainRegisterView())
        await reg_ch.send("⚡ **Quick Actions:**", view=AutoClaimView())
    
    can_ch = ctx.guild.get_channel(CANCEL_CLAIM_CHANNEL_ID)
    if can_ch:
        await can_ch.purge(limit=5)
        embed = discord.Embed(title="Match Management", description="Leave your match or join open spots.", color=discord.Color.orange())
        await can_ch.send(embed=embed, view=CancelAndClaimView())

    await msg.edit(content="✅ **Setup Complete!**")

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def init_tables(ctx):
    await ctx.send("🔄 Initializing Live Tables...")
    for slot_name in SLOT_LIST_CHANNELS:
        await refresh_table(ctx.guild, slot_name)
        await asyncio.sleep(1) 
    await ctx.send("✅ Tables are live!")

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def notify_start(ctx, minutes: int, slot_name: str = None):
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
            room_link = room_channel.mention if room_channel else "the room channel"
            await channel.send(
                f"⚠️ {role.mention} **ATTENTION!** ⚠️\n"
                f"Match is starting in **{minutes} minutes**!\n"
                f"Please check {room_link} for ID & Password."
            )
            count += 1
    await ctx.send(f"✅ Notification sent to {count} channels.", delete_after=5)

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def lock(ctx):
    global REGISTRATION_OPEN
    REGISTRATION_OPEN = False
    await ctx.send("⛔ **SYSTEM LOCKED.**")
    reg_ch = ctx.guild.get_channel(REGISTRATION_CHANNEL_ID)
    if reg_ch: await reg_ch.send("⛔ **REGISTRATION CLOSED.**")

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def unlock(ctx):
    global REGISTRATION_OPEN
    REGISTRATION_OPEN = True
    await ctx.send("✅ **SYSTEM UNLOCKED.** Registration is open.")

if __name__ == "__main__":
    keep_alive.keep_alive()  
    bot.run(TOKEN)
