from __future__ import annotations

from tempfile import TemporaryDirectory
from threading import Lock
from typing import TYPE_CHECKING, Iterable

import discord
from discord.ext import commands
from rich import print

from alfbote.llamacpp.chat import Llama2
from alfbote.people import People
from alfbote.utils import run_blocking

if TYPE_CHECKING:
    from alfbote.bots import Alfbote



class MyView(discord.ui.View):
    stop_pressed = False

    def __init__(self, respondent: discord.User | discord.Member = None):
        super().__init__(timeout=120, disable_on_timeout=True)
        self.respondent_id = None
        if respondent is not None:
            self.respondent_id = respondent.id  # The person's ID who the bot is responding to

    async def interaction_check(self, interaction):
        if interaction.user.id == self.respondent_id or interaction.user.id in People.admins:
            return True
        return False

    @discord.ui.button(label="stop", style=discord.ButtonStyle.danger)
    async def button_callback(self, button, interaction: discord.Interaction):
        self.stop_pressed = True
        self.clear_items()
        await interaction.response.edit_message(content=f"{self.message.content}—", view=self)


class ChatGen(commands.Cog, name="ChatGen"):
    def __init__(self, bot: Alfbote, tts: bool = False, gpu: bool = False):
        self.bot = bot
        n_gpu_layers = 1000 if gpu else 0
        self.model = Llama2(n_threads=12, n_gpu_layers=n_gpu_layers)

        self.TTS_ENABLED = tts

        self.chat_lock = Lock()
        self.tts = None
        if tts:
            from TTS.api import TTS
            TTS_MODEL = "tts_models/en/vctk/vits" # Very good model that is fairly fast
            TTS_SPEAKER = "p273" # VITS speaker. Change/remove this for other models
            self.tts = TTS(TTS_MODEL, speaker=TTS_SPEAKER, gpu=True)

    # Chat Interaction
    @commands.command()
    async def c(self, ctx: discord.ApplicationContext, *, msg):
        # Only process one prompt at a time
        if self.chat_lock.locked():
            return

        stopped = False
        output = []
        with self.chat_lock:
            # Generate and edit message one word at a time just like ChatGPT
            message: discord.Message = None
            stop_view = MyView(respondent=ctx.message.author)
            async with ctx.typing():
                try:
                    for a, token in enumerate(self.generate_response(msg), 0):
                        output.append(token)
                        current_msg = "".join(output)
                        if message is None:
                            message = await ctx.send(current_msg, view=stop_view)
                        else:
                            if a % 10 == 0:
                                await message.edit(content=" " + current_msg + " ")

                        if stop_view.stop_pressed:
                            await message.edit(content=f"{current_msg} —")
                            stopped = True
                            break

                    output = current_msg
                    # Remove stop button
                    stop_view.clear_items()
                    if message is not None:
                        await message.edit(content=current_msg, view=stop_view)

                # If the message is removed with the stop button or the wtf command, ignore the error
                except commands.errors.CommandInvokeError:
                    pass

        if self.TTS_ENABLED and not stopped:
            # Only play TTS for users in a channel
            if ctx.message.author.voice is None or ctx.message.author.voice.channel is None:
                return

            with TemporaryDirectory() as tmpdir:
                audio_file = tmpdir + "audio.wav"
                try:
                    await run_blocking(self.bot, self.generate_speech, output, audio_file)
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
    @commands.command()
    async def stfu(self, ctx: discord.ApplicationContext):
        if ctx.voice_client is None:
            pass
        elif ctx.author.voice.channel and (ctx.author.voice.channel == ctx.voice_client.channel):
            ctx.voice_client.stop()

    def generate_response(self, msg: str) -> str | Iterable:
        return self.model.generate(msg)

    def generate_speech(self, text: str, audio_file: str):
        if self.tts is not None:
            self.tts.tts_to_file(text=text, emotion="Happy", speed=2, file_path=audio_file)
