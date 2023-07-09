from __future__ import annotations

import functools
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any, Callable
import asyncio

import discord
from discord.ext import commands
from dotenv import load_dotenv
from rich import print

from alfbote.people import People
from alfbote.emojis import Emojis
from alfbote.utils import run_blocking
from alfbote.imagegen import ImageGen
from alfbote.chatgen import ChatGen

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="#", intents=intents, status=discord.Status.online)

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

last_msg = None


@bot.slash_command(
    name="test",
    description="testcommand",  # guild_ids=["302888848466378762"]
)  # Add the guild ids in which the slash command will appear. If it should be in all, remove the argument, but note that it will take some time (up to an hour) to register the command if it's for all guilds.
async def test(ctx: discord.ApplicationContext):
    await ctx.respond(f"testcmd {bot.latency}")


# Delete the last message posted by the bot
@bot.command(pass_context=True)
async def wtf(ctx: discord.ApplicationContext):
    if last_msg is not None:
        try:
            await last_msg.delete()
        except:
            pass


# Remove messages sent by the bot on certain emojis
@bot.event
async def on_reaction_add(reaction, user):
    if reaction.message.author.bot:
        if reaction.emoji in Emojis.sad_emojis:
            if last_msg is not None:
                await last_msg.delete()


@bot.event
async def on_message(msg):
    global last_msg
    if msg.author == bot.user:
        last_msg = msg
        return

    if msg.author.id in People.bad_users:
        return

    # ALLOWED_CHANNELS = [ALLOWED_CHANNEL, "bot-channel", "bot"]
    # if msg.channel.name in ALLOWED_CHANNELS:
    await bot.process_commands(msg)


@bot.event
async def on_ready():
    print(f"[blue] Logged in as {bot.user}")


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
