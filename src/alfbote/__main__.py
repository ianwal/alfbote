from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from dotenv import load_dotenv
from rich import print

from alfbote.people import People
from alfbote.emojis import Emojis
from alfbote.imagegen import ImageGen
from alfbote.chatgen import ChatGen
from alfbote.bots import Alfbote, GuildDB, CLICog

if TYPE_CHECKING:
    from discord import Message, Guild
    from typing import Any, Callable

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

bot = Alfbote()


@bot.slash_command(
    name="test1", description="testcommand", guild_ids=[469733139019989013, 719804911377973269]
)  # Add the guild ids in which the slash command will appear. If it should be in all, remove the argument, but note that it will take some time (up to an hour) to register the command if it's for all guilds.
async def test1(ctx: discord.ApplicationContext):
    await ctx.respond(f"testcmd {bot.latency}")


# Delete the last message posted by the bot
@bot.command(pass_context=True)
async def wtf(ctx: discord.ApplicationContext):
    last_msg: Message = bot.guild_db.get(ctx.message.guild, "last_msg")
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
            try:
                await reaction.message.delete()
            except discord.errors.NotFound:
                pass


@bot.event
async def on_message(msg: Message):
    if msg.author == bot.user:
        bot.guild_db.update(msg.guild, "last_msg", msg)
        return

    if msg.author.id in People.bad_users:
        return

    ALLOWED_CHANNELS = [ALLOWED_CHANNEL, "bot-channel", "bot", "alfbote"]
    if msg.channel.name in ALLOWED_CHANNELS:
        await bot.process_commands(msg)


@bot.event
async def on_ready():
    print(f"[blue] Logged in as {bot.user}")
    for guild in bot.guilds:
        bot.guild_db.create(guild, {"last_msg": None})
    print(str(bot.guild_db))


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

cli = CLICog(bot)
bot.add_cog(cli)
bot.run(DISCORD_API_KEY)
