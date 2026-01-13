import discord
from discord.ext import commands
import json
import os
import asyncio
import keep_alive

# ================= CONFIGURATION =================
TOKEN = os.environ.get("TOKEN")

# --- CHANNELS ---
ADMIN_COMMAND_CHANNEL_ID = 1459806817734361282
REGISTRATION_CHANNEL_ID = 1458788627164303432
CANCEL_CLAIM_CHANNEL_ID = 1459791046547472540
ADMIN_LOG_CHANNEL_ID = 1459460369780047892

# These are the channels where the LIVE TABLE will appear
SLOT_LIST_CHANNELS = {
    "SLOT_1": 1459460237437435999,
    "SLOT_2": 1459471324593389725,
    "SLOT_3": 1459471494785531965,
    "SLOT_4": 1459472478651945070
}

# Private Room Channels (ID/Pass)
ROOM_CHANNELS = {
    "SLOT_1": 1458788771716792486,
    "SLOT_2": 1459772021448904822,
    "SLOT_3": 1459772074112454750,
    "SLOT_4": 1459772130232373512
}

SLOT_ROLES = {
    "SLOT_1": "Slot 1 Player",
    "SLOT_2": "Slot 2 Player",
    "SLOT_3": "Slot 3 Player",
    "SLOT_4": "Slot 4 Player"
}

MAX_SLOTS = 20
DATA_FILE = "data.json"
REGISTRATION_OPEN = True

# ================= DATA HANDLING =================
def load_data():
    if not os.path.exists(DATA_FILE):
        # We add 'table_messages' to store the ID of the live table in each channel
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
        # Ensure backward compatibility if upgrading from old code
        if "table_messages" not in data:
            data["table_messages"] = {}
        return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# ================= CORE LOGIC: LIVE TABLE UPDATE =================
async def refresh_table(guild, slot_name):
    """Updates the single pinned message in the slot channel."""
    
    # 1. Get the Channel
    channel_id = SLOT_LIST_CHANNELS.get(slot_name)
    if not channel_id: return
    channel = guild.get_channel(channel_id)
    if not channel: return

    # 2. Build the Table String
    registered_uids = data["slots"].get(slot_name, [])
    
    table_lines = []
    table_lines.append(f"{'NO.':<3} | {'TEAM NAME'}")
    table_lines.append("-" * 30)
    
    # Fill in the rows
    for i in range(MAX_SLOTS):
        slot_num = i + 1
        if i < len(registered_uids):
            uid = registered_uids[i]
            team_name = data["teams"].get(uid, {}).get("team", "Unknown")
            # Truncate long names to keep table clean
            team_name = (team_name[:18] + '..') if len(team_name) > 18 else team_name
            table_lines.append(f"{slot_num:02d}  | {team_name}")
        else:
            table_lines.append(f"{slot_num:02d}  | [ OPEN ]")

    tabular_data = "\n".join(table_lines)
    
    # 3. Create the Embed
    display_name = slot_name.replace("_", " ") # SLOT_1 -> SLOT 1
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

    # 4. Edit Existing Message OR Send New One
    msg_id = data["table_messages"].get(slot_name)
    
    message = None
    if msg_id:
        try:
            message = await channel.fetch_message(msg_id)
            await message.edit(embed=embed)
        except discord.NotFound:
            message = None # Message was deleted manually, send new one
    
    if message is None:
        # Send new message and save ID
        message = await channel.send(embed=embed)
        data["table_messages"][slot_name] = message.id
        save_data(data)

# ================= LOGIC: ADD / REMOVE =================

async def add_player_to_slot(interaction, slot_name):
    uid = str(interaction.user.id)
    guild = interaction.guild
    
    if not REGISTRATION_OPEN:
        await interaction.response.send_message("⛔ **Registration is Closed.**", ephemeral=True)
        return False
        
    if len(data["slots"][slot_name]) >= MAX_SLOTS:
        return False

    if uid in data["slots"][slot_name]:
        await interaction.response.send_message(f"⚠️ You are already in **{slot_name}**.", ephemeral=True)
        return False

    # 1. Update Database
    data["slots"][slot_name].append(uid)
    if "booked_slots" not in data["teams"][uid]:
        data["teams"][uid]["booked_slots"] = []
    
    if slot_name not in data["teams"][uid]["booked_slots"]:
        data["teams"][uid]["booked_slots"].append(slot_name)
        
    save_data(data)

    # 2. Assign Role
    role_name = SLOT_ROLES.get(slot_name)
    if role_name:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            try: await interaction.user.add_roles(role)
            except: pass

    # 3. UPDATE THE LIVE TABLE
    await refresh_table(guild, slot_name)

    return True

async def remove_single_slot_logic(interaction, slot_to_remove):
    uid = str(interaction.user.id)
    guild = interaction.guild
    
    if uid not in data["teams"]: return False, "No team data."
    booked = data["teams"][uid].get("booked_slots", [])
    
    if slot_to_remove not in booked:
        return False, "You don't own this slot."

    # 1. Remove from Data
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

    # 3. UPDATE THE LIVE TABLE (This deletes them from the list visually)
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

# ================= VIEWS =================

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
            await interaction.response.send_message(f"✅ Successfully joined **{self.slot}**!", ephemeral=True)
        else:
             # Just in case it failed silently (e.g. full)
             if not interaction.response.is_done():
                 await interaction.response.send_message("❌ Failed to join. Slot might be full.", ephemeral=True)

class SlotSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        for s in SLOT_LIST_CHANNELS:
            self.add_item(SlotButton(s))

class TeamModal(discord.ui.Modal, title="Team Registration"):
    team = discord.ui.TextInput(label="Team Name", placeholder="Enter your team name")
    p1 = discord.ui.TextInput(label="Player 1 (IGL)", placeholder="IGN / Discord ID")
    
    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        data["teams"][uid] = {
            "team": self.team.value,
            "players": [self.p1.value],
            "booked_slots": []
        }
        save_data(data)
        
        # Log it
        log_channel = interaction.guild.get_channel(ADMIN_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(title="🆕 New Team Registered", color=discord.Color.blue())
            embed.add_field(name="Team Name", value=self.team.value)
            embed.add_field(name="IGL", value=f"<@{uid}>")
            await log_channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Team **{self.team.value}** Saved! Now select a slot:", 
            view=SlotSelectView(), 
            ephemeral=True
        )

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

class CancelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🗑️ Manage/Cancel Slots", style=discord.ButtonStyle.danger, custom_id="cancel_main_btn")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid not in data["teams"] or not data["teams"][uid].get("booked_slots"):
            await interaction.response.send_message("❌ You have no active slots.", ephemeral=True)
            return
        
        booked = data["teams"][uid]["booked_slots"]
        await interaction.response.send_message("Select slot to remove:", view=discord.ui.View().add_item(CancelDropdown(booked)), ephemeral=True)

# ================= BOT SETUP =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.add_view(MainRegisterView())
    bot.add_view(CancelView())

def is_admin():
    async def predicate(ctx):
        return ctx.channel.id == ADMIN_COMMAND_CHANNEL_ID
    return commands.check(predicate)

# --- SETUP COMMANDS ---

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin()
async def setup_registration(ctx):
    """Sets up the Registration and Cancel buttons."""
    await ctx.message.delete()
    
    # 1. Registration Channel
    reg_ch = ctx.guild.get_channel(REGISTRATION_CHANNEL_ID)
    if reg_ch:
        await reg_ch.purge(limit=5)
        await reg_ch.send(
            "📝 **TOURNAMENT REGISTRATION**\nClick below to register or join a slot.", 
            view=MainRegisterView()
        )
    
    # 2. Cancel Channel
    can_ch = ctx.guild.get_channel(CANCEL_CLAIM_CHANNEL_ID)
    if can_ch:
        await can_ch.purge(limit=5)
        await can_ch.send(
            "⚙️ **SLOT MANAGEMENT**\nClick below to cancel your slot.", 
            view=CancelView()
        )
    
    await ctx.send("✅ Registration & Cancel buttons posted.")

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin()
async def init_tables(ctx):
    """
    RUN THIS ONCE! 
    It creates the initial Table Message in every slot channel.
    """
    await ctx.send("🔄 Initializing Live Tables in all slot channels...")
    
    for slot_name in SLOT_LIST_CHANNELS:
        await refresh_table(ctx.guild, slot_name)
        await asyncio.sleep(1) # Small delay to be safe
    
    await ctx.send("✅ All tables are live and ready!")

if __name__ == "__main__":
    keep_alive.keep_alive()
    bot.run(TOKEN)
