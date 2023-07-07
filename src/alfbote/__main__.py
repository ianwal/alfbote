import functools
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any, Callable

import discord
from discord.ext import commands
from dotenv import load_dotenv
from rich import print as rprint

from alfbote.people import People

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="#", intents=intents, status=discord.Status.online)

load_dotenv()

DISCORD_API_KEY = os.getenv("DISCORD_API_KEY")
if DISCORD_API_KEY is None:
    rprint("[red] ERROR: No API key set. Exiting...")
    exit(-1)

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

if GPU:
    # ROCM workaround
    os.environ["HSA_OVERRIDE_GFX_VERSION"] = "10.3.0"
    rprint("[green] GPU Enabled")

if SD_ENABLED:
    if not GPU:
        rprint("[red] ERROR: Image generation requires GPU.")
        exit(-1)
    rprint("[green] Image generation enabled")

    from alfbote.imagegen import ImageGen

if CHAT_ENABLED:
    rprint("[green] Chat enabled")
    if TTS_ENABLED:
        rprint("[green] TTS Enabled")

    from alfbote.chatgen import ChatGen

    chatgen = ChatGen(tts=TTS_ENABLED, gpu=GPU)

# Mutexes for generators
# Chat lock is necessary
# Image lock is just because of VRAM
chat_lock = Lock()
image_lock = Lock()


# Run blocking function with async to avoid Discord heartbeat timeouts
async def run_blocking(blocking_func: Callable, *args, **kwargs) -> Any:
    func = functools.partial(
        blocking_func, *args, **kwargs
    )  # `run_in_executor` doesn't support kwargs, `functools.partial` does
    return await bot.loop.run_in_executor(None, func)


# Image generation
@bot.command(pass_context=True)
async def i(ctx, *, msg):
    if not SD_ENABLED or not GPU:
        return

    # Only process one prompt at a time
    if image_lock.locked():
        return

    with image_lock:
        async with ctx.typing():
            with tempfile.SpooledTemporaryFile(mode="w+b") as file:
                images = await run_blocking(ImageGen.generate_image, msg)
                images[0].save(file, "jpeg")
                file.seek(0)
                discord_file = discord.File(file, filename=f"{msg}.jpg")
                await ctx.send(f"{ctx.message.author.mention} {msg}", file=discord_file)


# Chat and TTS
@bot.command(pass_context=True)
async def c(ctx, *, msg):
    if not CHAT_ENABLED:
        return

    # Only process one prompt at a time
    if chat_lock.locked():
        return

    with chat_lock:
        async with ctx.typing():
            output = await run_blocking(chatgen.generate_message, msg)
            if output is not None:
                await ctx.channel.send(output)
                if TTS_ENABLED:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        audio_file = tmpdir + "audio.wav"
                        try:
                            await run_blocking(
                                chatgen.generate_speech, output, audio_file
                            )
                        except Exception as exc:
                            print(exc)
                            return

                        try:
                            if ctx.voice_client is None:
                                await ctx.message.author.voice.channel.connect()
                            elif ctx.author.voice.channel and (
                                ctx.author.voice.channel == ctx.voice_client.channel
                            ):
                                pass
                            else:
                                await ctx.voice_client.disconnect(force=True)
                                await ctx.message.author.voice.channel.connect()
                        except discord.ClientException:
                            print("Error connecting to channel.")
                            return

                        if ctx.voice_client.is_playing():
                            ctx.voice_client.stop()

                        ffmpeg_options = {"options": "-vn"}

                        try:
                            ctx.voice_client.play(
                                discord.FFmpegPCMAudio(
                                    source=audio_file, **ffmpeg_options
                                )
                            )
                        except discord.ClientException:
                            pass

@bot.event
async def on_message(msg):
    if msg.author == bot.user:
        return
    
    if msg.author.id in People.bad_users:
        return

    ALLOWED_CHANNELS = [ALLOWED_CHANNEL, "bot-channel", "bot"]
    if msg.channel.name in ALLOWED_CHANNELS:
        await bot.process_commands(msg)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


bot.run(DISCORD_API_KEY)
