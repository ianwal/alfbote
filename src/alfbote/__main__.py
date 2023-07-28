from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
import queue

import discord
from discord.ext import commands
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
IMAGEGEN = bool(int(os.getenv("IMAGEGEN", "1")))
CHATGEN = bool(int(os.getenv("CHATGEN", "1")))
TTSGEN = bool(int(os.getenv("TTSGEN", "1")))
ALLOWED_CHANNEL = os.getenv("ALLOWED_CHANNEL", "bot-channel")

if COLLAB:
    import nest_asyncio

    nest_asyncio.apply()

bot = Alfbote()

import yt_dlp


class MusicPlayer:
    def __init__(self, bot: Alfbote, guild: Guild):
        self.bot = bot
        self.song_queue = queue.Queue()
        self.guild = guild

    async def join_channel(self, ctx: discord.ApplicationContext):
        try:
            if ctx.voice_client is None:
                await ctx.message.author.voice.channel.connect()
            elif ctx.author.voice.channel and (ctx.author.voice.channel == ctx.voice_client.channel):
                return
            else:
                await ctx.voice_client.disconnect(force=True)
                await ctx.message.author.voice.channel.connect()
        except discord.ClientException:
            print("Error connecting to channel.")

    async def skip_song(self, ctx: discord.ApplicationContext):
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()

    def next_song(self):
        try:
            next_song = self.song_queue.get(block=False)
        except queue.Empty:
            return
        assert next_song is not None

        coro = self.play_song(next_song)
        self.bot.loop.create_task(coro)

    async def play_song(self, song_url: str):
        try:
            ffmpeg_options = {
                "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                "options": "-vn",
            }

            ydl_opts = {"format": "bestaudio"}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                song_info = ydl.extract_info(song_url, download=False)
            self.guild.voice_client.play(
                discord.FFmpegOpusAudio(song_info["url"], **ffmpeg_options),
                after=lambda e: self.next_song(),
            )
        except Exception as err:
            print(err)
            self.next_song()


class MusicCog(commands.Cog, name="MusicCog"):
    def __init__(self, bot: Alfbote):
        self.bot = bot

    @commands.command()
    async def p(self, ctx: discord.ApplicationContext, msg: str = None):
        # Only play TTS for users in a channel
        if msg is None:
            return

        music_player: MusicPlayer = bot.guild_db.get(ctx.message.guild, "music_player")
        await music_player.join_channel(ctx)
        music_player.song_queue.put(msg)
        if music_player.song_queue.qsize() == 1:
            await music_player.play_song(msg)


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
        bot.guild_db.create(guild, {"last_msg": None, "music_player": MusicPlayer(bot, guild)})
    print(str(bot.guild_db))


if GPU:
    print("[green] GPU enabled")

if IMAGEGEN:
    print("[green] ImageGen enabled")
    if not GPU:
        print("[red] ERROR: ImageGen requires GPU=True.")
        exit(1)

    bot.add_cog(ImageGen(bot, ROCM=True))

if CHATGEN:
    print("[green] ChatGen enabled")
    if TTSGEN:
        print("[green] TTS enabled")

    bot.add_cog(ChatGen(bot, tts=TTSGEN, gpu=GPU))

bot.add_cog(MusicCog(bot))
# bot.add_cog(CLICog(bot))
bot.run(DISCORD_API_KEY)
