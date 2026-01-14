import discord
from discord.ext import commands
import json
import os
import asyncio
import keep_alive

# ================= 1. CONFIGURATION =================
TOKEN = os.environ.get("TOKEN")

# --- CHANNELS ---
ADMIN_COMMAND_CHANNEL_ID = 1459806817734361282
REGISTRATION_CHANNEL_ID = 1458788627164303432
CANCEL_CLAIM_CHANNEL_ID = 1459791046547472540
ADMIN_LOG_CHANNEL_ID = 1459460369780047892

# LIVE TABLES: The bot will update the list in these channels
SLOT_LIST_CHANNELS = {
    "SLOT_1": 1459460237437435999,
    "SLOT_2": 1459471324593389725,
    "SLOT_3": 1459471494785531965,
    "SLOT_4": 1459472478651945070
}

# PRIVATE ROOMS: Where ID/Pass is sent
ROOM_CHANNELS = {
    "SLOT_1": 1458788771716792486,
    "SLOT_2": 1459772021448904822,
    "SLOT_3": 1459772074112454750,
    "SLOT_4": 1459772130232373512
}

# ROLES: Exact names of roles to assign
SLOT_ROLES = {
    "SLOT_1": "Slot 1 Player",
    "SLOT_2": "Slot 2 Player",
    "SLOT_3": "Slot 3 Player",
    "SLOT_4": "Slot 4 Player"
}

MAX_SLOTS = 16
DATA_FILE = "data.json"
REGISTRATION_OPEN = True

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
        return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# ================= 3. HELPER: MANAGE ROLES =================
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
    """Updates the single pinned message in the slot channel."""
    channel_id = SLOT_LIST_CHANNELS.get(slot_name)
    if not channel_id: return
    channel = guild.get_channel(channel_id)
    if not channel: return

    registered_uids = data["slots"].get(slot_name, [])
    
    # Create the Table Strings
    table_lines = [f"{'NO.':<3} | {'TEAM NAME'}", "-" * 30]
    
    for i in range(MAX_SLOTS):
        slot_num = i + 1
        if i < len(registered_uids):
            uid = registered_uids[i]
            team_name = data["teams"].get(uid, {}).get("team", "Unknown")
            # Truncate long names to prevent breaking layout
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

    # Update Logic
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

# ================= 5. CORE LOGIC (ADD/REMOVE) =================

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

    # 1. Save Data
    data["slots"][slot_name].append(uid)
    if "booked_slots" not in data["teams"][uid]:
        data["teams"][uid]["booked_slots"] = []
    
    if slot_name not in data["teams"][uid]["booked_slots"]:
        data["teams"][uid]["booked_slots"].append(slot_name)
    save_data(data)

    # 2. Assign Role
    role_name = SLOT_ROLES.get(slot_name)
    if role_name:
        role = await get_or_create_role(guild, role_name)
        if role:
            try: await interaction.user.add_roles(role)
            except: pass

    # 3. Update Visual Table
    await refresh_table(guild, slot_name)
    return True

async def remove_single_slot_logic(interaction, slot_to_remove):
    uid = str(interaction.user.id)
    guild = interaction.guild
    
    if uid not in data["teams"]: return False, "No team data."
    booked = data["teams"][uid].get("booked_slots", [])
    
    if slot_to_remove not in booked:
        return False, "You don't own this slot."

    # 1. Remove Data
    if uid in data["slots"][slot_to_remove]:
        data["slots"][slot_to_remove].remove(uid)
    
    data["teams"][uid]["booked_slots"].remove(slot_to_remove)
    save_data(data)

    # 2. Remove Role
    role_name = SLOT_ROLES.get(slot_to_remove)
    if role_name:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            try: await interaction.user.remove_roles(role)
            except: pass

    # 3. Update Visual Table
    await refresh_table(guild, slot_to_remove)
    return True, f"✅ Removed from **{slot_to_remove}**."

async def remove_all_slots_logic(interaction):
    uid = str(interaction.user.id)
    if uid not in data["teams"] or not data["teams"][uid].get("booked_slots"):
        return False, "You have no slots to cancel."

    booked = list(data["teams"][uid]["booked_slots"])
    for s in booked:
        await remove_single_slot_logic(interaction, s)
    return True, "✅ All slots cancelled."

# ================= 6. VIEWS & MODALS =================

class TeamModal(discord.ui.Modal, title="Team Registration"):
    team = discord.ui.TextInput(label="Team Name", placeholder="Enter your team name")
    
    # 4 Players Inputs
    p1 = discord.ui.TextInput(label="Player 1 (IGL)", placeholder="IGN / Discord ID")
    p2 = discord.ui.TextInput(label="Player 2", placeholder="IGN", required=False)
    p3 = discord.ui.TextInput(label="Player 3", placeholder="IGN", required=False)
    p4 = discord.ui.TextInput(label="Player 4", placeholder="IGN", required=False)
    
    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        
        # Save all 4 players
        data["teams"][uid] = {
            "team": self.team.value,
            "players": [self.p1.value, self.p2.value, self.p3.value, self.p4.value],
            "booked_slots": []
        }
        save_data(data)
        
        # Log to Admin Channel
        log_channel = interaction.guild.get_channel(ADMIN_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(title="🆕 New Team Registered", color=discord.Color.blue())
            embed.add_field(name="Team Name", value=self.team.value)
            embed.add_field(name="Roster", value=f"{self.p1.value}, {self.p2.value}, {self.p3.value}, {self.p4.value}", inline=False)
            embed.add_field(name="IGL", value=f"<@{uid}>")
            await log_channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Team **{self.team.value}** Saved! Now select a slot:", 
            view=SlotSelectView(), 
            ephemeral=True
        )

class SlotButton(discord.ui.Button):
    def __init__(self, slot):
        count = len(data["slots"][slot])
        label = f"{slot} ({count}/{MAX_SLOTS})"
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
            await interaction.response.send_message("❌ All slots are full!", ephemeral=True)

class MainRegisterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📝 Register Team", style=discord.ButtonStyle.green, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid in data["teams"]:
             await interaction.response.send_message("✅ Team found! Select a slot:", view=SlotSelectView(), ephemeral=True)
        else:
            await interaction.response.send_modal(TeamModal())

class CancelDropdown(discord.ui.Select):
    def __init__(self, booked_slots):
        options = []
        for slot in booked_slots:
            options.append(discord.SelectOption(label=f"Cancel {slot}", value=slot, emoji="🗑️"))
        options.append(discord.SelectOption(label="Cancel ALL", value="ALL", emoji="❌"))
        super().__init__(placeholder="Select slot to cancel...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "ALL":
            success, msg = await remove_all_slots_logic(interaction)
        else:
            success, msg = await remove_single_slot_logic(interaction, self.values[0])
        await interaction.response.send_message(msg, ephemeral=True)

class CancelAndClaimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🗑️ Cancel My Slot", style=discord.ButtonStyle.danger, custom_id="cancel_slot_btn")
    async def cancel_slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid not in data["teams"] or not data["teams"][uid].get("booked_slots"):
             await interaction.response.send_message("⚠️ You have no active slots.", ephemeral=True)
             return
        booked = data["teams"][uid]["booked_slots"]
        await interaction.response.send_message("Select slot to cancel:", view=discord.ui.View().add_item(CancelDropdown(booked)), ephemeral=True)

    @discord.ui.button(label="♻️ Claim Open Slot", style=discord.ButtonStyle.primary, custom_id="claim_open_btn")
    async def claim_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not REGISTRATION_OPEN:
            await interaction.response.send_message("⛔ **Claims Closed.**", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid not in data["teams"]:
            await interaction.response.send_message("❌ Register first.", ephemeral=True)
            return
        await interaction.response.send_message("✅ Checking availability...", view=SlotSelectView(), ephemeral=True)

# ================= 7. BOT & ADMIN COMMANDS =================
class SlotBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    
    async def setup_hook(self):
        self.add_view(MainRegisterView())
        self.add_view(AutoClaimView())
        self.add_view(CancelAndClaimView())

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

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def setup(ctx):
    """Restores Register, AutoClaim, and Cancel Buttons."""
    await ctx.message.delete()
    msg = await ctx.send("⚙️ **Configuring Roles & Channels...**")
    await setup_channel_perms(ctx.guild)
    
    reg_ch = ctx.guild.get_channel(REGISTRATION_CHANNEL_ID)
    if reg_ch:
        await reg_ch.purge(limit=5)
        await reg_ch.send("📝 **TOURNAMENT REGISTRATION**", view=MainRegisterView())
        await reg_ch.send("⚡ **Quick Actions:**", view=AutoClaimView())
    
    can_ch = ctx.guild.get_channel(CANCEL_CLAIM_CHANNEL_ID)
    if can_ch:
        await can_ch.purge(limit=5)
        embed = discord.Embed(title="Slot Management", description="Cancel your booking or claim open slots.", color=discord.Color.orange())
        await can_ch.send(embed=embed, view=CancelAndClaimView())

    await msg.edit(content="✅ **Setup Complete!**")

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def init_tables(ctx):
    """Creates the Live Tables in all slot channels (Run Once)."""
    await ctx.send("🔄 Initializing Live Tables in all slot channels...")
    for slot_name in SLOT_LIST_CHANNELS:
        await refresh_table(ctx.guild, slot_name)
        await asyncio.sleep(1) 
    await ctx.send("✅ Tables are live!")

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def notify_start(ctx, minutes: int, slot_name: str = None):
    """Sends 'Match Starting in X mins' to Room channels."""
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
