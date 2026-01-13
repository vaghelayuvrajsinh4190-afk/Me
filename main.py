import discord
from discord.ext import commands
import json
import os
import asyncio

# ================= CONFIGURATION =================
# Ensure you set 'TOKEN' in your Environment Variables
TOKEN = os.environ.get("TOKEN")

# --- CHANNELS ---
ADMIN_COMMAND_CHANNEL_ID = 1459806817734361282
REGISTRATION_CHANNEL_ID = 1458788627164303432
CANCEL_CLAIM_CHANNEL_ID = 1459791046547472540
ADMIN_LOG_CHANNEL_ID = 1459460369780047892

# 3. Slot Text Channels (Chat/List) - Locked to role
SLOT_LIST_CHANNELS = {
    "SLOT_1": 1459460237437435999,
    "SLOT_2": 1459471324593389725,
    "SLOT_3": 1459471494785531965,
    "SLOT_4": 1459472478651945070
}

# 4. Private Room Channels (ID/Pass) - Locked to role
ROOM_CHANNELS = {
    "SLOT_1": 1458788771716792486,
    "SLOT_2": 1459772021448904822,
    "SLOT_3": 1459772074112454750,
    "SLOT_4": 1459772130232373512
}

# 5. Role Names (Bot will look for these or create them)
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

# ================= HELPER: MANAGE ROLES =================
async def get_or_create_role(guild, role_name):
    """Finds a role by name, or creates it if missing."""
    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        try:
            role = await guild.create_role(name=role_name, mentionable=True)
            print(f"🆕 Created new role: {role_name}")
        except Exception as e:
            print(f"❌ Error creating role {role_name}: {e}")
            return None
    return role

async def setup_channel_perms(guild):
    """Locks channels so ONLY the bot and the specific Role can see them."""
    for slot_name, role_name in SLOT_ROLES.items():
        role = await get_or_create_role(guild, role_name)
        if not role: continue

        # Defined channels for this slot
        channels_to_lock = []
        if slot_name in SLOT_LIST_CHANNELS:
            channels_to_lock.append(guild.get_channel(SLOT_LIST_CHANNELS[slot_name]))
        if slot_name in ROOM_CHANNELS:
            channels_to_lock.append(guild.get_channel(ROOM_CHANNELS[slot_name]))
        
        # Apply Overwrites
        for ch in channels_to_lock:
            if ch:
                # Deny @everyone, Allow Role
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
                await ch.edit(overwrites=overwrites)
                print(f"🔒 Locked channel {ch.name} to role {role.name}")

# ================= CORE LOGIC =================

async def add_player_to_slot(interaction, slot_name):
    """Adds user to data, assigns ROLE, and updates channel."""
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
    
    data["teams"][uid]["booked_slots"].append(slot_name)
    save_data(data)

    # 2. Assign Role (Auto Role)
    role_name = SLOT_ROLES.get(slot_name)
    if role_name:
        role = await get_or_create_role(guild, role_name)
        if role:
            try:
                await interaction.user.add_roles(role)
            except discord.Forbidden:
                print(f"❌ Bot missing permissions to add role {role_name}")
            except Exception as e:
                print(f"Error adding role: {e}")

    # 3. Post to List Channel
    slot_list_id = SLOT_LIST_CHANNELS.get(slot_name)
    if slot_list_id:
        try:
            ch = guild.get_channel(slot_list_id)
            if ch: 
                idx = len(data["slots"][slot_name])
                team_name = data["teams"][uid]["team"]
                await ch.send(f"**{idx:02d}** | {team_name} <@{uid}>")
        except Exception as e:
            print(f"Error posting list: {e}")

    return True

async def remove_player_logic(interaction):
    """Removes user from data AND removes their role."""
    uid = str(interaction.user.id)
    
    if uid not in data["teams"] or not data["teams"][uid].get("booked_slots"):
        return False, "You don't have any booked slots to cancel."

    booked = data["teams"][uid]["booked_slots"]
    guild = interaction.guild
    removed_from = []
    
    for slot_name in booked:
        if uid in data["slots"][slot_name]:
            data["slots"][slot_name].remove(uid)
            removed_from.append(slot_name)
            
            # Remove Role
            role_name = SLOT_ROLES.get(slot_name)
            if role_name:
                role = discord.utils.get(guild.roles, name=role_name)
                if role:
                    try:
                        await interaction.user.remove_roles(role)
                    except Exception as e:
                        print(f"Error removing role: {e}")

            # Notify in slot channel
            list_ch_id = SLOT_LIST_CHANNELS.get(slot_name)
            if list_ch_id:
                try:
                    ch = guild.get_channel(list_ch_id)
                    if ch:
                        await ch.send(f"🔻 **Slot Cancelled!** 1 Space opened up.")
                except:
                    pass

    # Clear user data
    data["teams"][uid]["booked_slots"] = []
    save_data(data)
    
    return True, f"✅ Successfully cancelled slot(s): **{', '.join(removed_from)}**. Roles removed."

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

        if data["teams"][uid].get("booked_slots"):
             await interaction.response.send_message("⚠️ You already have a slot!", ephemeral=True)
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

class SlotButton(discord.ui.Button):
    def __init__(self, slot):
        count = len(data["slots"][slot])
        label = f"{slot} ({count}/{MAX_SLOTS})"
        style = discord.ButtonStyle.green if count < MAX_SLOTS else discord.ButtonStyle.red
        super().__init__(label=label, style=style, disabled=(count >= MAX_SLOTS))
        self.slot = slot

    async def callback(self, interaction: discord.Interaction):
        if not REGISTRATION_OPEN:
            await interaction.response.send_message("⛔ **Registration Closed.**", ephemeral=True)
            return
        
        uid = str(interaction.user.id)
        success = await add_player_to_slot(interaction, self.slot)
        if success:
            await interaction.response.send_message(f"✅ Claimed **{self.slot}**.", ephemeral=True)
        else:
             await interaction.response.send_message("❌ Slot Full or Error.", ephemeral=True)

class SlotSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        for s in SLOT_LIST_CHANNELS:
            self.add_item(SlotButton(s))

class TeamModal(discord.ui.Modal, title="Team Registration"):
    team = discord.ui.TextInput(label="Team Name", placeholder="Enter your team name")
    p1 = discord.ui.TextInput(label="Player 1 (IGL)", placeholder="IGN / Discord ID")
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
            f"✅ Team **{self.team.value}** Saved! Now select a slot:", 
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
            await interaction.response.send_message("❌ No team found. Please create a new team.", ephemeral=True)
            return
        await interaction.response.send_message("Select a slot:", view=SlotSelectView(), ephemeral=True)

    @discord.ui.button(label="🆕 Create/Update Team", style=discord.ButtonStyle.primary)
    async def create_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TeamModal())

class MainRegisterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📝 Register", style=discord.ButtonStyle.green, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not REGISTRATION_OPEN:
             await interaction.response.send_message("⛔ Registration Closed.", ephemeral=True)
             return
        
        uid = str(interaction.user.id)
        if uid in data["teams"]:
             await interaction.response.send_message("Choose an option:", view=RegisterChoiceView(), ephemeral=True)
        else:
            await interaction.response.send_modal(TeamModal())

class CancelAndClaimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🗑️ Cancel My Slot", style=discord.ButtonStyle.danger, custom_id="cancel_slot_btn")
    async def cancel_slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid not in data["teams"]:
            await interaction.response.send_message("❌ You are not registered.", ephemeral=True)
            return

        success, msg = await remove_player_logic(interaction)
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="♻️ Claim Open Slot", style=discord.ButtonStyle.primary, custom_id="claim_open_btn")
    async def claim_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not REGISTRATION_OPEN:
            await interaction.response.send_message("⛔ **Claims Closed.**", ephemeral=True)
            return

        uid = str(interaction.user.id)
        
        if uid not in data["teams"]:
            await interaction.response.send_message("❌ You must register a team first.", ephemeral=True)
            return
        
        if data["teams"][uid].get("booked_slots"):
            await interaction.response.send_message("⚠️ You already have a slot! Cancel it first.", ephemeral=True)
            return

        available = False
        for s in SLOT_LIST_CHANNELS:
            if len(data["slots"][s]) < MAX_SLOTS:
                available = True
                break
        
        if available:
            await interaction.response.send_message("✅ Slots are available! Pick one:", view=SlotSelectView(), ephemeral=True)
        else:
            await interaction.response.send_message("❌ **All slots are currently FULL.** Wait for someone to cancel.", ephemeral=True)

# ================= BOT SETUP =================
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
            await ctx.send(f"❌ **Wrong Channel!** Admin commands only work in <#{ADMIN_COMMAND_CHANNEL_ID}>", delete_after=5)
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
    """Sets up Channels, Roles, and Panels."""
    await ctx.message.delete()
    
    msg = await ctx.send("⚙️ **Configuring Roles & Channels... (This might take a moment)**")
    
    # Run the setup for roles and permissions
    await setup_channel_perms(ctx.guild)
    
    # 1. Post Registration Panel
    reg_ch = ctx.guild.get_channel(REGISTRATION_CHANNEL_ID)
    if reg_ch:
        await reg_ch.send("📝 **TOURNAMENT REGISTRATION**\nClick below to register your team.", view=MainRegisterView())
    
    # 2. Post Cancel/Claim Panel
    can_ch = ctx.guild.get_channel(CANCEL_CLAIM_CHANNEL_ID)
    if can_ch:
        embed = discord.Embed(title="Slot Management", description="Use this menu to **Cancel** your booking or **Claim** a slot if one opens up.", color=discord.Color.orange())
        await can_ch.send(embed=embed, view=CancelAndClaimView())

    await msg.edit(content="✅ **Setup Complete!** Roles created, Channels locked, Panels posted.")

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def notify_start(ctx, minutes: int = 10):
    """Notifies specific slot roles that match starts in X minutes."""
    await ctx.message.delete()
    
    count = 0
    # Loop through every slot channel
    for slot_name, channel_id in SLOT_LIST_CHANNELS.items():
        # Get the Role name for this slot
        role_name = SLOT_ROLES.get(slot_name)
        if not role_name: continue
        
        # Find the actual Role object and Channel object
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        channel = ctx.guild.get_channel(channel_id)
        
        # Get the Room channel for linking
        room_channel_id = ROOM_CHANNELS.get(slot_name)
        room_channel = ctx.guild.get_channel(room_channel_id) if room_channel_id else None

        if role and channel:
            room_link = room_channel.mention if room_channel else "the room channel"
            
            # Send the specific notification
            await channel.send(
                f"⚠️ {role.mention} **ATTENTION!** ⚠️\n"
                f"Match is starting in **{minutes} minutes**!\n"
                f"Please check {room_link} for ID & Password."
            )
            count += 1
            
    await ctx.send(f"✅ Sent start notifications to {count} active slot channels.", delete_after=5)

@bot.command()
@commands.has_permissions(administrator=True)
@is_admin_channel()
async def notify_pending(ctx):
    await ctx.message.delete()
    pending = [f"<@{uid}>" for uid, d in data["teams"].items() if not d.get("booked_slots")]
    
    if not pending:
        await ctx.send("✅ Everyone has a slot!", delete_after=5)
        return

    msg = (
        "⚠️ **LAST CALL FOR SLOTS!** ⚠️\n"
        f"{', '.join(pending)}\n\n"
        "**Match starts soon!** Click below to auto-claim."
    )
    reg_ch = ctx.guild.get_channel(REGISTRATION_CHANNEL_ID)
    if reg_ch:
        await reg_ch.send(msg, view=AutoClaimView())

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
    bot.run(TOKEN)
