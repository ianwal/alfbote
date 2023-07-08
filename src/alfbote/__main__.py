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
from rich import print as rprint
import torch

from alfbote.people import People
from alfbote.emojis import Emojis

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
    if not torch.cuda.is_available():
        rprint("[red] ERROR: CUDA not detected. Exiting...")

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

last_msg = None


# Run blocking function with async to avoid Discord heartbeat timeouts
async def run_blocking(blocking_func: Callable, *args, **kwargs) -> Any:
    func = functools.partial(
        blocking_func, *args, **kwargs
    )  # `run_in_executor` doesn't support kwargs, `functools.partial` does
    return await bot.loop.run_in_executor(None, func)


@bot.slash_command(
    name="test",
    description="testcommand",  # guild_ids=["302888848466378762"]
)  # Add the guild ids in which the slash command will appear. If it should be in all, remove the argument, but note that it will take some time (up to an hour) to register the command if it's for all guilds.
async def test(ctx: discord.ApplicationContext):
    await ctx.respond(f"testcmd {bot.latency}")


# Image generation
@bot.command(pass_context=True)
async def i(ctx: discord.ApplicationContext, *, msg):
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


class MyView(discord.ui.View):
    stop_pressed = False

    def __init__(self):
        super().__init__(timeout=120, disable_on_timeout=True)

    async def interaction_check(self, interaction):
        if interaction.user.id != interaction.message.author.id and interaction.user.id not in People.admins:
            # await interaction.response.send_message("Its not for you!", ephemeral=True)
            #await interaction.response.defer()
            return False
        return True

    @discord.ui.button(label="stop", style=discord.ButtonStyle.danger)
    async def button_callback(self, button, interaction: discord.Interaction):
        self.stop_pressed = True
        self.clear_items()
        await interaction.response.edit_message(content=f"{self.message.content} [STOPPED]", view=self)


# Chat and TTS
@bot.command(pass_context=True)
async def c(ctx: discord.ApplicationContext, *, msg):
    if not CHAT_ENABLED:
        return

    # Only process one prompt at a time
    if chat_lock.locked():
        return

    output = []
    with chat_lock:
        # Generate and edit message one word at a time just like ChatGPT
        message: discord.Message = None
        stop_view = MyView()
        async with ctx.typing():
            for a, token in enumerate(chatgen.generate_message(msg, streaming=True), 0):
                output.append(token)
                current_msg = "".join(output)
                if message is None:
                    message = await ctx.send(current_msg, view=stop_view)
                else:
                    if a % 10 == 0:
                        await message.edit(content=current_msg)

                if stop_view.stop_pressed:
                    await message.edit(content=f"{current_msg} [STOPPED]")
                    return

            output = current_msg
            # Remove stop button
            stop_view.clear_items()
            await message.edit(content=current_msg, view=stop_view)

    if TTS_ENABLED:
        # Only play TTS for users in a channel
        if ctx.message.author.voice is None:
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_file = tmpdir + "audio.wav"
            try:
                await run_blocking(chatgen.generate_speech, output, audio_file)
            except Exception as exc:
                print(exc)
                return

            try:
                if ctx.voice_client is None:
                    await ctx.message.author.voice.channel.connect()
                elif ctx.author.voice.channel and (ctx.author.voice.channel == ctx.voice_client.channel):
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
                ctx.voice_client.play(discord.FFmpegOpusAudio(source=audio_file, **ffmpeg_options))
            except discord.ClientException:
                pass


# Stop all voice output including TTS
@bot.command(pass_context=True)
async def stfu(ctx: discord.ApplicationContext):
    if ctx.voice_client is None:
        pass
    elif ctx.author.voice.channel and (ctx.author.voice.channel == ctx.voice_client.channel):
        ctx.voice_client.stop()


# Stop all voice output including TTS
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

    ALLOWED_CHANNELS = [ALLOWED_CHANNEL, "bot-channel", "bot"]
    if msg.channel.name in ALLOWED_CHANNELS:
        await bot.process_commands(msg)


@bot.event
async def on_ready():
    rprint(f"[blue] Logged in as {bot.user}")


bot.run(DISCORD_API_KEY)
