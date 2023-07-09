from tempfile import TemporaryDirectory
from threading import Lock
from typing import Iterable

import discord
from discord.ext import commands
from gpt4all import GPT4All
from rich import print

from alfbote.people import People
from alfbote.utils import run_blocking

# CHAT_MODEL = "nous-hermes-13b.ggmlv3.q4_0.bin"
# CHAT_MODEL = "ggml-gpt4all-j-v1.3-groovy.bin"
CHAT_MODEL = "wizardLM-13B-Uncensored.ggmlv3.q4_0.bin"  # VERY GOOD
# CHAT_MODEL = "ggml-mpt-7b-chat.bin"
# CHAT_MODEL = "ggml-model-gpt4all-falcon-q4_0.bin"
TTS_MODEL = "tts_models/en/ljspeech/tacotron2-DCA"


class MyView(discord.ui.View):
    stop_pressed = False

    def __init__(self):
        super().__init__(timeout=120, disable_on_timeout=True)

    async def interaction_check(self, interaction):
        if interaction.user.id != interaction.message.author.id and interaction.user.id not in People.admins:
            # await interaction.response.send_message("Its not for you!", ephemeral=True)
            # await interaction.response.defer()
            return False
        return True

    @discord.ui.button(label="stop", style=discord.ButtonStyle.danger)
    async def button_callback(self, button, interaction: discord.Interaction):
        self.stop_pressed = True
        self.clear_items()
        await interaction.response.edit_message(content=f"{self.message.content} [STOPPED]", view=self)


class ChatGen(commands.Cog, name="ChatGen"):
    def __init__(self, bot: discord.Bot, tts: bool = False, gpu: bool = False):
        self.bot = bot
        self.model = GPT4All(CHAT_MODEL, n_threads=12)
        self.model._is_chat_session_activated = True
        self.model.current_chat_session = []

        self.TTS_ENABLED = tts

        self.chat_lock = Lock()
        self.tts = None
        if tts:
            from TTS.api import TTS

            self.tts = TTS(TTS_MODEL, gpu=gpu)

    # Chat Interaction
    @commands.command()
    async def c(self, ctx: discord.ApplicationContext, *, msg):
        # Only process one prompt at a time
        if self.chat_lock.locked():
            return

        output = []
        with self.chat_lock:
            # Generate and edit message one word at a time just like ChatGPT
            message: discord.Message = None
            stop_view = MyView()
            async with ctx.typing():
                for a, token in enumerate(self.generate_message(msg, streaming=True), 0):
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

        if self.TTS_ENABLED:
            # Only play TTS for users in a channel
            if ctx.message.author.voice is None:
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

    def generate_message(self, msg: str, streaming: bool = False, max_tokens: int = 1000) -> str | Iterable:
        # This model is really good but it needs this prompt for it to return stuff easily
        if CHAT_MODEL == "wizardLM-13B-Uncensored.ggmlv3.q4_0.bin":
            msg = f"explain, describe, or continue the conversation: {msg}"

        if streaming:
            return self.model.generate(msg, n_batch=16, max_tokens=max_tokens, streaming=True)
        else:
            output = self.model.generate(msg, max_tokens=max_tokens, n_batch=16)
            return output

    def generate_speech(self, text: str, audio_file: str):
        if self.tts is not None:
            self.tts.tts_to_file(text=text, emotion="Happy", speed=2, file_path=audio_file)
