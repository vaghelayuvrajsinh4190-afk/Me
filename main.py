import discord
from discord.ext import commands
import json
import os

# ================= CONFIGURATION =================
TOKEN = "MTQ1OTE2NDczMjAzMTI0MjM0Nw.GOkdIP.HkxafSs-Ew3KaZ3zKnHhK-GnVsJie-zMMCjYRo"

# --- CHANNELS ---
# 1. Admin Command Channel (Where you type !setup, !lock, etc.)
ADMIN_COMMAND_CHANNEL_ID = 1459806817734361282

# 2. Public Channels (Where the bot posts buttons)
REGISTRATION_CHANNEL_ID = 1458788627164303432
CANCEL_CLAIM_CHANNEL_ID = 1459791046547472540
ADMIN_LOG_CHANNEL_ID = 1459460369780047892

# 3. Slot Text Channels (For lists)
SLOT_LIST_CHANNELS = {
    "SLOT_1": 1459460237437435999,
    "SLOT_2": 1459471324593389725,
    "SLOT_3": 1459471494785531965,
    "SLOT_4": 1459472478651945070
}

# 4. Private Room Channels (For permissions)
ROOM_CHANNELS = {
    "SLOT_1": 1458788771716792486,
    "SLOT_2": 1459772021448904822,
    "SLOT_3": 1459772074112454750,
    "SLOT_4": 1459772130232373512
}

MAX_SLOTS = 20
DATA_FILE = "data.json"
REGISTRATION_OPEN = True

# ================= DATA HANDLING =================
def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {"teams": {}, "slots": {k: [] for k in SLOT_LIST_CHANNELS}}
        with open(DATA_FILE, "w") as f:
            json.dump(default_data, f, indent=4)
        return default_data
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# ================= CORE LOGIC =================
async def add_player_to_slot(interaction, slot_name):
    uid = str(interaction.user.id)
    
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
    data["teams"][uid]["booked_slots"].append(slot_name)
    save_data(data)

    # Grant Perms
    guild = interaction.guild
    room_id = ROOM_CHANNELS.get(slot_name)
    if room_id:
        try:
            room = guild.get_channel(room_id)
            if room: await room.set_permissions(interaction.user, view_channel=True)
        except: pass

    # Post List
    slot_list_id = SLOT_LIST_CHANNELS.get(slot_name)
    if slot_list_id:
        try:
            ch = guild.get_channel(slot_list_id)
            if ch: 
                idx = len(data["slots"][slot_name])
                team = data["teams"][uid]["team"]
                await ch.send(f"**{idx:02d}** | {team}")
        except: pass

    return True

# ================= VIEWS (BUTTONS) =================
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
        for slot in SLOT_LIST_CHANNELS:
            if len(data["slots"][slot]) < MAX_SLOTS and uid not in data["slots"][slot]:
                assigned = slot
                break
        
        if assigned:
            if await add_player_to_slot(interaction, assigned):
                await interaction.response.send_message(f"✅ Auto-Assigned to **{assigned}**!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ All slots full!", ephemeral=True)

class SlotButton(discord.ui.Button):
    def __init__(self, slot):
        super().__init__(label=slot, style=discord.ButtonStyle.green)
        self.slot = slot

    async def callback(self, interaction: discord.Interaction):
        if not REGISTRATION_OPEN:
            await interaction.response.send_message("⛔ **Registration Closed.**", ephemeral=True)
            return
        
        uid = str(interaction.user.id)
        if uid not in data["teams"]:
            await interaction.response.send_message("❌ Register first.", ephemeral=True)
            return
            
        success = await add_player_to_slot(interaction, self.slot)
        if success:
            await interaction.response.send_message(f"✅ Claimed **{self.slot}**.", ephemeral=True)
        elif len(data["slots"][self.slot]) >= MAX_SLOTS:
             await interaction.response.send_message("❌ Slot Full.", ephemeral=True)

class SlotSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        for s in SLOT_LIST_CHANNELS:
            self.add_item(SlotButton(s))

class TeamModal(discord.ui.Modal, title="Team Registration"):
    team = discord.ui.TextInput(label="Team Name")
    p1 = discord.ui.TextInput(label="Player 1")
    p2 = discord.ui.TextInput(label="Player 2", required=False)
    p3 = discord.ui.TextInput(label="Player 3", required=False)
    p4 = discord.ui.TextInput(label="Player 4", required=False)
    
    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        data["teams"][uid] = {
            "team": self.team.value,
            "players": [self.p1.value, self.p2.value, self.p3.value, self.p4.value],
            "booked_slots": []
        }
        save_data(data)
        await interaction.response.send_message(
            f"✅ Team **{self.team.value}** Saved! Select Slot:", 
            view=SlotSelectView(), 
            ephemeral=True
        )

class RegisterChoiceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="🏆 Claim Slot (Saved Team)", style=discord.ButtonStyle.success)
    async def claim_slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid not in data["teams"]:
            await interaction.response.send_message("❌ No team found.", ephemeral=True)
            return
        await interaction.response.send_message("Select a slot:", view=SlotSelectView(), ephemeral=True)

    @discord.ui.button(label="🆕 Create New Team", style=discord.ButtonStyle.primary)
    async def create_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TeamModal())

class MainRegisterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📝 Register / Claim", style=discord.ButtonStyle.green, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not REGISTRATION_OPEN:
             await interaction.response.send_message("⛔ Registration Closed.", ephemeral=True)
             return
        
        uid = str(interaction.user.id)
        if uid in data["teams"]:
             await interaction.response.send_message("Choose option:", view=RegisterChoiceView(), ephemeral=True)
        else:
            await interaction.response.send_modal(TeamModal())

# ================= BOT & COMMANDS =================
class SlotBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self):
        self.add_view(MainRegisterView())
        self.add_view(AutoClaimView())

bot = SlotBot()

# --- SECURITY CHECK: ONLY SPECIFIC ADMIN CHANNEL ---
def is_admin_channel():
    async def predicate(ctx):
        if ctx.channel.id != ADMIN_COMMAND_CHANNEL_ID:
            # Optional: Tell them they are in the wrong place, or just ignore
            await ctx.send(f"❌ **Wrong Channel!** Admin commands only work in <#{ADMIN_COMMAND_CHANNEL_ID}>", delete_after=5)
            return False
        return True
    return commands.check(predicate)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# --- COMMAND: SETUP (Only Admin + Only Admin Channel) ---
@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def setup(ctx):
    await ctx.message.delete()
    
    reg_ch = ctx.guild.get_channel(REGISTRATION_CHANNEL_ID)
    if reg_ch:
        await reg_ch.send("📝 **TOURNAMENT REGISTRATION**", view=MainRegisterView())
        await ctx.send(f"✅ Setup panels sent to {reg_ch.mention}", delete_after=5)

# --- COMMAND: NOTIFY PENDING (15 Mins Before Match) ---
@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def notify_pending(ctx):
    await ctx.message.delete()
    
    # Find users registered but with NO slots booked
    pending = [f"<@{uid}>" for uid, d in data["teams"].items() if not d.get("booked_slots")]
    
    if not pending:
        await ctx.send("✅ Everyone has a slot!", delete_after=5)
        return

    msg = (
        "⚠️ **LAST CALL FOR SLOTS!** ⚠️\n"
        f"{', '.join(pending)}\n\n"
        "**Match starts in 15 mins!** Click below to auto-claim a spot."
    )
    
    reg_ch = ctx.guild.get_channel(REGISTRATION_CHANNEL_ID)
    if reg_ch:
        await reg_ch.send(msg, view=AutoClaimView())
        await ctx.send(f"✅ Notified {len(pending)} pending users.")

# --- COMMAND: LOCK (Match Start) ---
@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def lock(ctx):
    global REGISTRATION_OPEN
    REGISTRATION_OPEN = False
    await ctx.send("⛔ **SYSTEM LOCKED.** No more claims allowed.")
    
    reg_ch = ctx.guild.get_channel(REGISTRATION_CHANNEL_ID)
    if reg_ch: await reg_ch.send("⛔ **REGISTRATION CLOSED. MATCH STARTING.**")

# --- COMMAND: UNLOCK ---
@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def unlock(ctx):
    global REGISTRATION_OPEN
    REGISTRATION_OPEN = True
    await ctx.send("✅ **SYSTEM UNLOCKED.** Registration is open.")

bot.run(TOKEN)
