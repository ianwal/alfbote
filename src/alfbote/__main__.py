from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, Callable

import discord
from discord.ext import commands
from dotenv import load_dotenv
from rich import print

from alfbote.people import People
from alfbote.emojis import Emojis
from alfbote.imagegen import ImageGen
from alfbote.chatgen import ChatGen

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="#", intents=intents, status=discord.Status.online)

if TYPE_CHECKING:
    from discord import Message, Guild

load_dotenv()

DISCORD_API_KEY = os.getenv("DISCORD_API_KEY")
if DISCORD_API_KEY is None:
    print("[red] ERROR: No API key set. Exiting...")
    exit(1)

COLLAB = bool(int(os.getenv("COLLAB", "0")))
# Options
GPU = bool(int(os.getenv("GPU", "1")))
SD_ENABLED = bool(int(os.getenv("IMAGE", "1")))
CHAT_ENABLED = bool(int(os.getenv("CHAT", "1")))
TTS_ENABLED = bool(int(os.getenv("TTS", "1")))
ALLOWED_CHANNEL = os.getenv("ALLOWED_CHANNEL", "bot-channel")

if COLLAB:
    import nest_asyncio

    nest_asyncio.apply()


class GuildDB:
    def __init__(self):
        self.db: dict = {}

    # Create a guild in the DB
    def create(self, guild: Guild, data: dict) -> None:
        self.db[guild.id] = data

    # Get an item from the DB
    def get(self, guild: Guild, key: str) -> Any | None:
        return self.db.get(guild.id, None).get(key, None)

    # Insert an entry into a guild in the DB without overwriting existing entries
    def insert(self, guild: Guild, key: str, data: Any) -> None:
        if self.db[guild.id].get(key, None) is None:
            self.db[guild.id][key] = data

    # Update an entry for a guild in the DB
    def update(self, guild: Guild, key: str, data: Any) -> None:
        self.db[guild.id][key] = data

    # Delete a guild from the DB
    def delete(self, key: str) -> None:
        del self.db[key]

    def __str__(self):
        return str(self.db)


guild_db = GuildDB()


@bot.slash_command(
    name="test1", description="testcommand", guild_ids=[469733139019989013, 719804911377973269]
)  # Add the guild ids in which the slash command will appear. If it should be in all, remove the argument, but note that it will take some time (up to an hour) to register the command if it's for all guilds.
async def test1(ctx: discord.ApplicationContext):
    await ctx.respond(f"testcmd {bot.latency}")


# Delete the last message posted by the bot
@bot.command(pass_context=True)
async def wtf(ctx: discord.ApplicationContext):
    last_msg: Message = guild_db.get(ctx.message.guild, "last_msg")
    if last_msg is not None:
        try:
            await last_msg.delete(reason="Deleted by wtf command")
        except AssertionError:
            print(f"[red] ERROR: Cannot delete last message. Last message is {type(last_msg)}")
        except Exception as exc:
            print(f"[red] {exc}")


# Remove messages sent by the bot on certain emojis
@bot.event
async def on_reaction_add(reaction: discord.Reaction, user):
    if reaction.message.author.bot:
        if reaction.emoji in Emojis.sad_emojis:
            last_msg = guild_db.get(reaction.message.guild, "last_msg")
            if last_msg is not None:
                await last_msg.delete()


@bot.event
async def on_message(msg: Message):
    global guild_db
    if msg.author == bot.user:
        guild_db.update(msg.guild, "last_msg", msg)
        return

    if msg.author.id in People.bad_users:
        return

    ALLOWED_CHANNELS = [ALLOWED_CHANNEL, "bot-channel", "bot", "alfbote"]
    if msg.channel.name in ALLOWED_CHANNELS:
        await bot.process_commands(msg)


@bot.event
async def on_ready():
    global guild_db
    print(f"[blue] Logged in as {bot.user}")
    for guild in bot.guilds:
        guild_db.create(guild, {"last_msg": None, "last_msg_lock": Lock()})
    print(str(guild_db))


if GPU:
    print("[green] GPU enabled")

if SD_ENABLED:
    print("[green] ImageGen enabled")
    if not GPU:
        print("[red] ERROR: ImageGen requires GPU=True.")
        exit(1)

    bot.add_cog(ImageGen(bot, ROCM=True))

if CHAT_ENABLED:
    print("[green] ChatGen enabled")
    if TTS_ENABLED:
        print("[green] TTS enabled")

    bot.add_cog(ChatGen(bot, tts=TTS_ENABLED, gpu=GPU))

bot.run(DISCORD_API_KEY)
