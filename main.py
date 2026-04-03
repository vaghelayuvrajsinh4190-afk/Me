“””
╔══════════════════════════════════════════════════════════════════╗
║          TOURNAMENT BOT — UPGRADED EDITION                      ║
║  Features: Registration · Slots · Verification · Admin Suite    ║
╚══════════════════════════════════════════════════════════════════╝

GitHub: https://github.com/YOUR_USERNAME/tournament-bot

QUICK START:

1. pip install -r requirements.txt
1. cp .env.example .env  →  fill in BOT_TOKEN
1. Edit config.py with your role/channel names
1. python tournament_bot.py
   “””

import discord
from discord.ext import commands, tasks
import json
import os
import asyncio
import io
from datetime import datetime, timedelta
import pytz

# ── Import all config ──────────────────────────────────────────────

from config import (
BOT_TOKEN,
ADMIN_ROLE_NAME,
VERIFIED_ROLE_NAME,
ADMIN_CHANNEL_NAME,
LOG_CHANNEL_NAME,
REG_CHANNEL_NAME,
SLOT_CHANNELS,
SLOTS_PER_MATCH,
TIMEZONE,
DATA_FILE,
)

IST = pytz.timezone(TIMEZONE)

# ──────────────────────────────────────────────────────────────────

# DATA STORE

# ──────────────────────────────────────────────────────────────────

def load_data():
if not os.path.exists(DATA_FILE):
return {
“teams”: {},
“slots”: {
“MATCH_1”: {},
“MATCH_2”: {},
“MATCH_3”: {},
“MATCH_4”: {},
},
“registration_open”: True,
“slot_table_messages”: {},
“registration_message_id”: None,
}
with open(DATA_FILE, “r”) as f:
return json.load(f)

def save_data(data):
with open(DATA_FILE, “w”) as f:
json.dump(data, f, indent=2)

data = load_data()

# ──────────────────────────────────────────────────────────────────

# BOT SETUP

# ──────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=”!”, intents=intents)

# ──────────────────────────────────────────────────────────────────

# HELPERS

# ──────────────────────────────────────────────────────────────────

def is_admin(ctx):
“”“Check if the command author has the Admin role.”””
return any(r.name == ADMIN_ROLE_NAME for r in ctx.author.roles)

def error_embed(msg: str) -> discord.Embed:
return discord.Embed(title=“❌ Error”, description=msg, color=0xFF4444)

def success_embed(title: str, msg: str) -> discord.Embed:
return discord.Embed(title=f”✅ {title}”, description=msg, color=0x00CC66)

def get_slot_table_embed(match_id: str) -> discord.Embed:
“”“Build the live slot table embed for a match.”””
slots = data[“slots”].get(match_id, {})
lines = []
for i in range(1, SLOTS_PER_MATCH + 1):
team = slots.get(str(i))
lines.append(f”`{i:02d}` ✅  **{team}**” if team else f”`{i:02d}` 🟢  *— Open —*”)

```
filled = len([v for v in slots.values() if v])
embed = discord.Embed(
    title=f"🎮 {match_id} — Slot List",
    description="\n".join(lines),
    color=0x00BFFF,
)
embed.set_footer(
    text=f"Slots filled: {filled}/{SLOTS_PER_MATCH}  •  "
         f"Last updated: {datetime.now(IST).strftime('%d %b %Y, %I:%M %p IST')}"
)
return embed
```

async def update_slot_table(guild: discord.Guild, match_id: str):
“”“Post or edit the slot table message in the correct channel.”””
channel_name = SLOT_CHANNELS.get(match_id)
channel = discord.utils.get(guild.text_channels, name=channel_name)
if not channel:
return

```
embed = get_slot_table_embed(match_id)
msg_id = data["slot_table_messages"].get(match_id)

try:
    if msg_id:
        msg = await channel.fetch_message(int(msg_id))
        await msg.edit(embed=embed)
    else:
        raise discord.NotFound(None, None)
except discord.NotFound:
    msg = await channel.send(embed=embed)
    data["slot_table_messages"][match_id] = str(msg.id)
    save_data(data)
```

async def log_action(
guild: discord.Guild,
title: str,
description: str,
color: int = 0xFFA500,
fields: dict = None,
):
“”“Send an audit log embed to the log channel.”””
log_ch = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
if not log_ch:
return
embed = discord.Embed(
title=f”📋 {title}”,
description=description,
color=color,
timestamp=datetime.now(IST),
)
if fields:
for name, value in fields.items():
embed.add_field(name=name, value=value, inline=False)
embed.set_footer(text=“Tournament Bot • Audit Log”)
await log_ch.send(embed=embed)

# ──────────────────────────────────────────────────────────────────

# REGISTRATION MODAL

# ──────────────────────────────────────────────────────────────────

class RegisterModal(discord.ui.Modal, title=“📝 Register Your Team”):
team_name = discord.ui.TextInput(
label=“Team Name”, placeholder=“e.g. Shadow Squad”, max_length=32
)
player1 = discord.ui.TextInput(
label=“Player 1 IGN”, placeholder=“In-game name of Player 1”, max_length=32
)
player2 = discord.ui.TextInput(
label=“Player 2 IGN”, placeholder=“In-game name of Player 2”, max_length=32
)
player3 = discord.ui.TextInput(
label=“Player 3 IGN”, placeholder=“In-game name of Player 3”, max_length=32
)
player4 = discord.ui.TextInput(
label=“Player 4 IGN”, placeholder=“In-game name of Player 4”, max_length=32
)

```
async def on_submit(self, interaction: discord.Interaction):
    # Registration closed?
    if not data["registration_open"]:
        return await interaction.response.send_message(
            embed=error_embed("Registrations are currently **closed**. Please wait for an admin."),
            ephemeral=True,
        )

    tname = self.team_name.value.strip()
    players = [
        self.player1.value.strip(),
        self.player2.value.strip(),
        self.player3.value.strip(),
        self.player4.value.strip(),
    ]

    # Duplicate team name check
    if tname.lower() in [t.lower() for t in data["teams"]]:
        return await interaction.response.send_message(
            embed=error_embed(f"Team name **{tname}** is already taken. Choose a different name."),
            ephemeral=True,
        )

    # Duplicate player IGN check (across all registered teams)
    existing = [p.lower() for t in data["teams"].values() for p in t["players"]]
    dupes = [p for p in players if p.lower() in existing]
    if dupes:
        return await interaction.response.send_message(
            embed=error_embed(f"These IGNs are already registered: **{', '.join(dupes)}**"),
            ephemeral=True,
        )

    # Save team
    data["teams"][tname] = {
        "players": players,
        "captain_id": str(interaction.user.id),
        "registered_at": datetime.now(IST).isoformat(),
    }
    save_data(data)

    embed = discord.Embed(
        title="🎉 Team Registered!",
        description=f"**{tname}** has been successfully registered.",
        color=0x00CC66,
    )
    embed.add_field(name="👥 Players", value="\n".join(f"• {p}" for p in players), inline=False)
    embed.set_footer(text="Head to a match channel to claim your slot!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

    await log_action(
        interaction.guild,
        "Team Registered",
        f"**{tname}** registered by {interaction.user.mention}",
        color=0x00CC66,
        fields={"Players": "\n".join(players)},
    )
```

# ──────────────────────────────────────────────────────────────────

# REGISTRATION BUTTON VIEW (persistent across restarts)

# ──────────────────────────────────────────────────────────────────

class RegistrationView(discord.ui.View):
def **init**(self):
super().**init**(timeout=None)

```
@discord.ui.button(
    label="📝 Register Team",
    style=discord.ButtonStyle.primary,
    custom_id="open_register_modal",
)
async def register_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
    if not data["registration_open"]:
        return await interaction.response.send_message(
            embed=error_embed("Registrations are currently **closed**."), ephemeral=True
        )
    await interaction.response.send_modal(RegisterModal())
```

# ──────────────────────────────────────────────────────────────────

# SLOT CLAIM VIEW

# ──────────────────────────────────────────────────────────────────

class SlotClaimView(discord.ui.View):
def **init**(self, match_id: str):
super().**init**(timeout=None)
self.match_id = match_id

```
    # Slot buttons 1–16 (rows 0–2, max 5 per row)
    for i in range(1, SLOTS_PER_MATCH + 1):
        btn = discord.ui.Button(
            label=str(i),
            style=discord.ButtonStyle.secondary,
            custom_id=f"slot_{match_id}_{i}",
            row=(i - 1) // 5,
        )
        btn.callback = self._make_slot_callback(i)
        self.add_item(btn)

    # Quick claim button
    quick = discord.ui.Button(
        label="⚡ Quick Claim (Auto-Assign)",
        style=discord.ButtonStyle.success,
        custom_id=f"quick_{match_id}",
        row=3,
    )
    quick.callback = self._quick_claim
    self.add_item(quick)

def _get_user_team(self, user_id: str):
    for tname, tdata in data["teams"].items():
        if tdata["captain_id"] == user_id:
            return tname
    return None

def _make_slot_callback(self, slot_no: int):
    async def callback(interaction: discord.Interaction):
        team_name = self._get_user_team(str(interaction.user.id))
        if not team_name:
            return await interaction.response.send_message(
                embed=error_embed("You don't have a registered team. Please register first."),
                ephemeral=True,
            )

        slot_key = str(slot_no)
        occupant = data["slots"][self.match_id].get(slot_key)
        if occupant:
            return await interaction.response.send_message(
                embed=error_embed(f"Slot **{slot_no}** is already taken by **{occupant}**."),
                ephemeral=True,
            )

        # Already booked a slot in this match?
        for k, v in data["slots"][self.match_id].items():
            if v == team_name:
                return await interaction.response.send_message(
                    embed=error_embed(f"**{team_name}** already has Slot **{k}** in {self.match_id}."),
                    ephemeral=True,
                )

        data["slots"][self.match_id][slot_key] = team_name
        save_data(data)
        await update_slot_table(interaction.guild, self.match_id)

        await interaction.response.send_message(
            embed=success_embed("Slot Claimed!", f"**{team_name}** claimed **Slot {slot_no}** in **{self.match_id}**. Good luck! 🏆"),
            ephemeral=True,
        )
        await log_action(
            interaction.guild,
            "Slot Claimed",
            f"**{team_name}** claimed Slot {slot_no} in {self.match_id}",
            color=0x00BFFF,
        )

    return callback

async def _quick_claim(self, interaction: discord.Interaction):
    team_name = self._get_user_team(str(interaction.user.id))
    if not team_name:
        return await interaction.response.send_message(
            embed=error_embed("You don't have a registered team."), ephemeral=True
        )

    for k, v in data["slots"][self.match_id].items():
        if v == team_name:
            return await interaction.response.send_message(
                embed=error_embed(f"**{team_name}** already has Slot **{k}** in {self.match_id}."),
                ephemeral=True,
            )

    for i in range(1, SLOTS_PER_MATCH + 1):
        if not data["slots"][self.match_id].get(str(i)):
            data["slots"][self.match_id][str(i)] = team_name
            save_data(data)
            await update_slot_table(interaction.guild, self.match_id)
            await interaction.response.send_message(
                embed=success_embed("⚡ Auto-Assigned!", f"**{team_name}** → **Slot {i}** in **{self.match_id}**!"),
                ephemeral=True,
            )
            await log_action(
                interaction.guild,
                "Quick Claim",
                f"**{team_name}** auto-assigned Slot {i} in {self.match_id}",
                color=0x00BFFF,
            )
            return

    await interaction.response.send_message(
        embed=error_embed(f"**{self.match_id}** is completely full! No slots available."),
        ephemeral=True,
    )
```

# ──────────────────────────────────────────────────────────────────

# VERIFICATION VIEW

# ──────────────────────────────────────────────────────────────────

class VerifyTeamView(discord.ui.View):
def **init**(self, team_name: str):
super().**init**(timeout=120)
self.team_name = team_name

```
@discord.ui.select(
    cls=discord.ui.UserSelect,
    placeholder="Select all 4 team members...",
    min_values=4,
    max_values=4,
    custom_id="verify_member_select",
)
async def select_members(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
    guild = interaction.guild
    verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
    if not verified_role:
        verified_role = await guild.create_role(
            name=VERIFIED_ROLE_NAME, color=discord.Color.green()
        )

    members = select.values
    for m in members:
        await m.add_roles(verified_role)

    embed = discord.Embed(
        title="✅ Team Verified!",
        description=f"**{self.team_name}** has been verified and roles assigned.",
        color=0x00CC66,
    )
    embed.add_field(
        name="Members",
        value="\n".join(f"{m.mention} ({m.display_name})" for m in members),
        inline=False,
    )
    await interaction.response.send_message(embed=embed)

    await log_action(
        guild,
        "Team Verified",
        f"**{self.team_name}** verified by {interaction.user.mention}",
        color=0x00CC66,
        fields={"Members": "\n".join(f"{m.mention} ({m.display_name})" for m in members)},
    )
```

# ──────────────────────────────────────────────────────────────────

# ADMIN COMMANDS

# ──────────────────────────────────────────────────────────────────

@bot.command()
async def setup(ctx):
“”“Creates all channels and posts the registration button + slot tables.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))

```
guild = ctx.guild

# Create channels if they don't exist
for name in [REG_CHANNEL_NAME, LOG_CHANNEL_NAME, *SLOT_CHANNELS.values()]:
    if not discord.utils.get(guild.text_channels, name=name):
        await guild.create_text_channel(name)

# Post registration embed + button
reg_ch = discord.utils.get(guild.text_channels, name=REG_CHANNEL_NAME)
embed = discord.Embed(
    title="🏆 Tournament Registration",
    description=(
        "Welcome to the **Tournament Registration System**!\n\n"
        "Click the button below to register your team.\n"
        "You'll need your **Team Name** and **4 Player IGNs**.\n\n"
        "After registering, head to a match channel to claim your slot!"
    ),
    color=0x00BFFF,
)
embed.set_footer(text="Registrations are currently OPEN ✅")
await reg_ch.send(embed=embed, view=RegistrationView())

# Post slot tables for all matches
for match_id in data["slots"]:
    await update_slot_table(guild, match_id)

await ctx.send(embed=success_embed("Setup Complete!", "All channels and tables have been created."))
await log_action(guild, "Bot Setup", f"Setup completed by {ctx.author.mention}", color=0x9B59B6)
```

@bot.command()
async def lock(ctx):
“”“Closes team registrations.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))
data[“registration_open”] = False
save_data(data)
await ctx.send(embed=discord.Embed(title=“🔒 Registrations Locked”, description=“No new teams can register.”, color=0xFF4444))
await log_action(ctx.guild, “Registrations Locked”, f”Locked by {ctx.author.mention}”, color=0xFF4444)

@bot.command()
async def unlock(ctx):
“”“Opens team registrations.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))
data[“registration_open”] = True
save_data(data)
await ctx.send(embed=discord.Embed(title=“🔓 Registrations Opened”, description=“Teams can now register!”, color=0x00CC66))
await log_action(ctx.guild, “Registrations Opened”, f”Opened by {ctx.author.mention}”, color=0x00CC66)

@bot.command()
async def announce(ctx, match_id: str):
“”“Posts a rich match announcement embed with all registered teams.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))

```
match_id = match_id.upper()
if match_id not in data["slots"]:
    return await ctx.send(embed=error_embed("Invalid match. Use: MATCH_1, MATCH_2, MATCH_3, MATCH_4"))

slots = data["slots"][match_id]
filled = [v for v in slots.values() if v]
teams_list = (
    "\n".join(f"`{k}.` {v}" for k, v in sorted(slots.items(), key=lambda x: int(x[0])) if v)
    or "*No teams registered yet.*"
)

embed = discord.Embed(
    title=f"📢 {match_id} — Official Announcement",
    description=f"**{len(filled)}/{SLOTS_PER_MATCH}** slots filled.\n\nRegistered teams for this match:",
    color=0xFFD700,
    timestamp=datetime.now(IST),
)
embed.add_field(name="🏅 Registered Teams", value=teams_list, inline=False)
embed.set_footer(text="Tournament Bot • Good luck to all participants!")
await ctx.send(embed=embed)
await log_action(ctx.guild, "Match Announced", f"{match_id} announced by {ctx.author.mention}", color=0xFFD700)
```

@bot.command()
async def notify_start(ctx, minutes: int):
“”“Pings all registered team captains with a match start warning.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))

```
embed = discord.Embed(
    title="⏰ Match Starting Soon!",
    description=f"Your match starts in **{minutes} minute(s)**!\nMake sure your entire team is ready.",
    color=0xFF8800,
    timestamp=datetime.now(IST),
)
embed.set_footer(text="Good luck to all teams! 🏆")

mentions = []
for tdata in data["teams"].values():
    cap_id = tdata.get("captain_id")
    if cap_id:
        member = ctx.guild.get_member(int(cap_id))
        if member:
            mentions.append(member.mention)

ping_str = " ".join(mentions) if mentions else "@here"
await ctx.send(content=ping_str, embed=embed)
await log_action(
    ctx.guild,
    "Match Notification Sent",
    f"Notified {len(mentions)} captain(s) — {minutes}min warning by {ctx.author.mention}",
    color=0xFF8800,
)
```

@bot.command()
async def force_remove(ctx, match_id: str, slot_no: int):
“”“Admin removes a team from a specific slot.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))

```
match_id = match_id.upper()
slot_key = str(slot_no)
team = data["slots"].get(match_id, {}).get(slot_key)
if not team:
    return await ctx.send(embed=error_embed(f"Slot {slot_no} in {match_id} is already empty."))

del data["slots"][match_id][slot_key]
save_data(data)
await update_slot_table(ctx.guild, match_id)
await ctx.send(embed=success_embed("Slot Cleared", f"**{team}** removed from Slot {slot_no} in {match_id}."))
await log_action(
    ctx.guild,
    "Force Remove",
    f"Slot {slot_no} in {match_id} cleared by {ctx.author.mention} (was: **{team}**)",
    color=0xFF4444,
)
```

@bot.command()
async def swap_slots(ctx, match_id: str, slot1: int, slot2: int):
“”“Swaps two teams’ slot positions within a match.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))

```
match_id = match_id.upper()
s = data["slots"].get(match_id, {})
t1 = s.get(str(slot1))
t2 = s.get(str(slot2))

if not t1 and not t2:
    return await ctx.send(embed=error_embed("Both slots are empty. Nothing to swap."))

# Perform swap
if t2:
    s[str(slot1)] = t2
else:
    s.pop(str(slot1), None)
if t1:
    s[str(slot2)] = t1
else:
    s.pop(str(slot2), None)

save_data(data)
await update_slot_table(ctx.guild, match_id)
await ctx.send(embed=success_embed(
    "Slots Swapped",
    f"Slot {slot1} ({t1 or 'empty'}) ↔ Slot {slot2} ({t2 or 'empty'}) in {match_id}."
))
await log_action(
    ctx.guild,
    "Slots Swapped",
    f"Slot {slot1} ↔ {slot2} in {match_id} by {ctx.author.mention}",
    color=0xFFA500,
)
```

@bot.command()
async def match_status(ctx):
“”“Shows a visual fill-bar overview of all 4 matches.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))

```
embed = discord.Embed(title="📊 Match Status Overview", color=0x9B59B6, timestamp=datetime.now(IST))
for match_id in ["MATCH_1", "MATCH_2", "MATCH_3", "MATCH_4"]:
    slots = data["slots"].get(match_id, {})
    filled = len([v for v in slots.values() if v])
    bar = "█" * filled + "░" * (SLOTS_PER_MATCH - filled)
    pct = int((filled / SLOTS_PER_MATCH) * 100)
    embed.add_field(
        name=f"🎮 {match_id}",
        value=f"`{bar}` {filled}/{SLOTS_PER_MATCH} ({pct}%)",
        inline=False,
    )
embed.set_footer(text="Tournament Bot")
await ctx.send(embed=embed)
```

@bot.command()
async def export_teams(ctx):
“”“Downloads all registered teams as a .txt file.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))

```
lines = ["TOURNAMENT TEAMS EXPORT", "=" * 40]
for tname, tdata in data["teams"].items():
    lines.append(f"\nTeam: {tname}")
    lines.append(f"  Registered: {tdata.get('registered_at', 'N/A')}")
    lines.append("  Players:")
    for p in tdata.get("players", []):
        lines.append(f"    - {p}")

lines += ["\n" + "=" * 40, f"Total Teams: {len(data['teams'])}"]

buf = io.BytesIO("\n".join(lines).encode("utf-8"))
await ctx.send(
    embed=success_embed("Export Ready", f"Exporting **{len(data['teams'])}** teams."),
    file=discord.File(buf, filename="teams_export.txt"),
)
```

@bot.command()
async def broadcast(ctx, *, message: str):
“”“DMs all registered team captains with a custom message.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))

```
embed = discord.Embed(
    title="📣 Tournament Broadcast",
    description=message,
    color=0x00BFFF,
    timestamp=datetime.now(IST),
)
embed.set_footer(text="Message from Tournament Organizers")

sent = failed = 0
for tdata in data["teams"].values():
    cap_id = tdata.get("captain_id")
    if cap_id:
        member = ctx.guild.get_member(int(cap_id))
        if member:
            try:
                await member.send(embed=embed)
                sent += 1
            except Exception:
                failed += 1

await ctx.send(embed=success_embed("Broadcast Sent", f"Delivered to **{sent}** captain(s). Failed: {failed}."))
await log_action(
    ctx.guild,
    "Broadcast Sent",
    f"By {ctx.author.mention} — Sent: {sent}, Failed: {failed}\n\n**Message:** {message}",
    color=0x00BFFF,
)
```

@bot.command()
async def verify_team(ctx, *, team_name: str):
“”“Start verification for a team — admin selects 4 Discord members.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))
if team_name not in data[“teams”]:
return await ctx.send(embed=error_embed(f”Team **{team_name}** not found.”))

```
embed = discord.Embed(
    title=f"🔍 Verify: {team_name}",
    description="Use the dropdown below to select all 4 Discord members for this team.",
    color=0x9B59B6,
)
await ctx.send(embed=embed, view=VerifyTeamView(team_name))
```

@bot.command()
async def init_tables(ctx):
“”“Refreshes all live slot tables.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))
for match_id in data[“slots”]:
await update_slot_table(ctx.guild, match_id)
await ctx.send(embed=success_embed(“Tables Refreshed”, “All slot tables have been updated.”))

@bot.command()
async def clear(ctx):
“”“Purges the last 100 messages in the current channel.”””
if not is_admin(ctx):
return await ctx.send(embed=error_embed(“Admins only.”))
deleted = await ctx.channel.purge(limit=100)
msg = await ctx.send(embed=success_embed(“Cleared”, f”Deleted **{len(deleted)}** messages.”))
await asyncio.sleep(3)
await msg.delete()

# ──────────────────────────────────────────────────────────────────

# AUTO MIDNIGHT RESET (IST)

# ──────────────────────────────────────────────────────────────────

@tasks.loop(minutes=1)
async def midnight_reset():
now = datetime.now(IST)
if now.hour == 0 and now.minute == 0:
# Clear all slots
for match_id in data[“slots”]:
data[“slots”][match_id] = {}

```
    # Delete teams older than 7 days
    cutoff = datetime.now(IST) - timedelta(days=7)
    to_delete = []
    for tname, tdata in data["teams"].items():
        reg_at = tdata.get("registered_at")
        if reg_at:
            try:
                if datetime.fromisoformat(reg_at) < cutoff:
                    to_delete.append(tname)
            except ValueError:
                pass

    for tname in to_delete:
        del data["teams"][tname]

    save_data(data)

    for guild in bot.guilds:
        # Remove Verified Team roles from all members
        verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
        if verified_role:
            for member in verified_role.members:
                try:
                    await member.remove_roles(verified_role)
                except Exception:
                    pass

        # Refresh all slot tables
        for match_id in data["slots"]:
            await update_slot_table(guild, match_id)

        await log_action(
            guild,
            "Daily Reset",
            f"Auto-reset at midnight IST. Slots cleared. {len(to_delete)} old team(s) removed.",
            color=0x9B59B6,
        )
```

# ──────────────────────────────────────────────────────────────────

# BOT EVENTS

# ──────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
print(f”✅ Tournament Bot online as {bot.user} (ID: {bot.user.id})”)
print(f”   Serving {len(bot.guilds)} guild(s)”)
bot.add_view(RegistrationView())  # Persist registration button across restarts
midnight_reset.start()

@bot.event
async def on_command_error(ctx, error):
if isinstance(error, commands.MissingRequiredArgument):
await ctx.send(
embed=error_embed(
f”Missing argument: `{error.param.name}`\n”
f”Usage: `!{ctx.command.name} {ctx.command.signature}`”
)
)
elif isinstance(error, commands.BadArgument):
await ctx.send(embed=error_embed(“Invalid argument type. Check the command usage.”))
elif isinstance(error, commands.CommandNotFound):
pass  # Silently ignore unknown commands
else:
await ctx.send(embed=error_embed(f”An unexpected error occurred:\n`{error}`”))

# ──────────────────────────────────────────────────────────────────

# ENTRY POINT

# ──────────────────────────────────────────────────────────────────

if **name** == “**main**”:
if BOT_TOKEN == “YOUR_BOT_TOKEN_HERE”:
print(“❌ ERROR: Please set your BOT_TOKEN in the .env file!”)
else:
bot.run(BOT_TOKEN)
