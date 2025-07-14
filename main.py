import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from datetime import datetime
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# MongoDB setup
MONGO_URI = "mongodb+srv://kleindelaheim:aq5VfZH4AxB3KkDR@heuchera.qkdiesf.mongodb.net/?retryWrites=true&w=majority&appName=heuchera"
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["admin_points"]
collection = db["points"]

ADMIN_IDS = [368922842365952002, 808828370477383702]
BOT_OWNER_ID = 728066632953626684
PAYOUT_ROLE_ID = 1004073244363608134
CATEGORY_IDS = [1067139662302425228, 1045756596795490324]
POINTS_LOG_CHANNEL_ID = 1269903439630962783
LOG_CHANNEL_ID = 1202963157690089492

BLOOM_ROLE_ID = 1028555502319308840
SERAPH_ROLE_ID = 1004073244363608134


def has_required_role(member: discord.Member):
    return any(role.id in [BLOOM_ROLE_ID, SERAPH_ROLE_ID] for role in member.roles)


def add_points(user_id: int, amount: int):
    user_data = collection.find_one({"user_id": str(user_id)})
    if not user_data:
        collection.insert_one({"user_id": str(user_id), "points": 0})
        user_data = {"points": 0}

    new_points = user_data["points"] + amount
    collection.update_one({"user_id": str(user_id)}, {"$set": {"points": new_points}})

    if (user_data["points"] // 100) < (new_points // 100):
        return True, new_points
    return False, new_points


class StatusButtons(discord.ui.View):
    def __init__(self, author_id, member: discord.Member):
        super().__init__(timeout=None)
        self.author_id = author_id
        self.member = member
        self.message = None
        self.points_awarded = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        self.message = interaction.message
        return True

    @discord.ui.button(emoji="<:a032:1352281339386396722>", style=discord.ButtonStyle.secondary, label="")
    async def processing(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_required_role(interaction.user):
            return await interaction.response.send_message("You don't have the required role.", ephemeral=True)
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("You didn't create this log.", ephemeral=True)

        content = self.message.content.replace("noted", "processing")
        await self.message.edit(content=content)

        if not self.points_awarded:
            hit_payout, new_total = add_points(interaction.user.id, 5)
            self.points_awarded = True

            log_channel = bot.get_channel(POINTS_LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"{interaction.user.mention} updated an order as processing : {new_total} points")

            if hit_payout:
                await self.message.channel.send(f"<@&{PAYOUT_ROLE_ID}> payout")

        await interaction.response.send_message("Status updated to processing.", ephemeral=True)

    @discord.ui.button(emoji="<:a007:1352281435058343958>", style=discord.ButtonStyle.secondary, label="")
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_required_role(interaction.user):
            return await interaction.response.send_message("You don't have the required role.", ephemeral=True)
        content = self.message.content.replace("processing", "done").replace("noted", "done")
        await self.message.edit(content=content)
        await interaction.response.send_message("Status updated to done.", ephemeral=True)

    @discord.ui.button(emoji="<:a009:1352281368108728371>", style=discord.ButtonStyle.secondary, label="")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_required_role(interaction.user):
            return await interaction.response.send_message("You don't have the required role.", ephemeral=True)
        await self.message.delete()
        collection.update_one({"user_id": str(interaction.user.id)}, {"$inc": {"points": -5}})
        await interaction.response.send_message("Order cancelled. -5 points.", ephemeral=True)


@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.loop.create_task(monthly_reset())
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")


@bot.tree.command(name="log", description="Admin log command")
@app_commands.describe(user="User", channel="Channel", order="Order Details", payment="Payment Details")
async def log(interaction: discord.Interaction, user: str, channel: str, order: str, payment: str):
    if interaction.user.id not in ADMIN_IDS:
        return await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
    if not has_required_role(interaction.user):
        return await interaction.response.send_message("You must have the Bloom or Seraph role to use this.", ephemeral=True)

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel:
        return await interaction.response.send_message("Log channel not found.", ephemeral=True)

    msg = (
        "_ _\n"
        "⠀⠀ ⠀⠀　₍ᐢᐢ₎　　**order received** !!　   ꫂ ၴႅၴ \n"
        "_ _\n"
        f"　　<:a024:1352281308944007290> 　{user}     —　 {channel}\n"
        f"　　<:a007:1352281435058343958> 　**__order:__**　{order}\n"
        f"　　<:a032:1352281339386396722> 　**__payment:__**　{payment}\n\n"
        f"⠀⠀　    ♡ ⠀**__status:__** 　 noted      <:a030:1352281432596414548>\n_ _"
    )

    view = StatusButtons(interaction.user.id, interaction.user)
    await log_channel.send(msg, view=view)
    await interaction.response.send_message(f"Log sent to <#{LOG_CHANNEL_ID}>", ephemeral=True)


@bot.tree.command(name="points", description="Manage admin points")
@app_commands.describe(action="Action type", number="Point value", user="User to update")
@app_commands.choices(
    action=[
        app_commands.Choice(name="set", value="set"),
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="subtract", value="subtract"),
    ],
    user=[
        app_commands.Choice(name="keija", value="368922842365952002"),
        app_commands.Choice(name="sanake", value="808828370477383702"),
    ]
)
async def points(interaction: discord.Interaction, action: app_commands.Choice[str], number: int, user: app_commands.Choice[str]):
    if interaction.user.id != BOT_OWNER_ID:
        return await interaction.response.send_message("You are not authorized.", ephemeral=True)

    user_id = user.value
    user_data = collection.find_one({"user_id": str(user_id)})
    if not user_data:
        collection.insert_one({"user_id": str(user_id)}, {"points": 0})
        user_data = {"points": 0}

    current_points = user_data["points"]
    new_points = current_points
    if action.value == "set":
        new_points = number
    elif action.value == "add":
        new_points += number
    elif action.value == "subtract":
        new_points -= number

    collection.update_one({"user_id": str(user_id)}, {"$set": {"points": new_points}})
    await interaction.response.send_message(f"{user.name} now has {new_points} points.")


@bot.event
async def on_message(message):
    if message.author.bot or message.author.id not in ADMIN_IDS:
        return

    if not message.channel.category or message.channel.category.id not in CATEGORY_IDS:
        return

    if message.content.lower() in ["gc1", "gc2"]:
        hit_payout, new_total = add_points(message.author.id, 5)
        log_channel = bot.get_channel(POINTS_LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"{message.author.mention} claimed a ticket : {new_total} points")
        if hit_payout:
            await message.channel.send(f"<@&{PAYOUT_ROLE_ID}> payout")

    await bot.process_commands(message)


async def monthly_reset():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now()
        current_month = now.strftime("%Y-%m")
        config = db["config"]
        last_reset = config.find_one({"_id": "last_reset_month"})

        if not last_reset or last_reset.get("month") != current_month:
            for user_id in ADMIN_IDS:
                collection.update_one({"user_id": str(user_id)}, {"$set": {"points": 0}}, upsert=True)
            config.update_one({"_id": "last_reset_month"}, {"$set": {"month": current_month}}, upsert=True)
            log_channel = bot.get_channel(POINTS_LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send("✅ Monthly reset: Points have been reset to 0.")
        await asyncio.sleep(3600)


bot.run("your_token_here")
