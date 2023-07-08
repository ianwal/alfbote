from gpt4all import GPT4All

from typing import Iterable

#CHAT_MODEL = "nous-hermes-13b.ggmlv3.q4_0.bin"
#CHAT_MODEL = "ggml-gpt4all-j-v1.3-groovy.bin"
CHAT_MODEL = "wizardLM-13B-Uncensored.ggmlv3.q4_0.bin" # BAD
#CHAT_MODEL = "ggml-mpt-7b-chat.bin"
#CHAT_MODEL = "ggml-model-gpt4all-falcon-q4_0.bin"
TTS_MODEL = "tts_models/en/ljspeech/tacotron2-DCA"


class ChatGen:
    def __init__(self, tts: bool = False, gpu: bool = False):
        self.model = GPT4All(CHAT_MODEL, n_threads=12)
        self.model._is_chat_session_activated = True
        self.model.current_chat_session = []

        if tts:
            from TTS.api import TTS

            self.tts = TTS(TTS_MODEL, gpu=gpu)
        else:
            self.tts = None

    def generate_message(self, msg: str, streaming: bool = False, max_tokens: int = 1000) -> str | Iterable:
        # This model is really good but it needs this prompt for it to return stuff easily
        if CHAT_MODEL == "wizardLM-13B-Uncensored.ggmlv3.q4_0.bin":
            msg = f"explain, describe, or write {msg}"

        if streaming:
            return self.model.generate(msg, n_batch=16, max_tokens=max_tokens, streaming=True)
        else:
            output = self.model.generate(msg, max_tokens=max_tokens, n_batch=16)
            return output

    def generate_speech(self, text: str, audio_file: str):
        if self.tts is not None:
            self.tts.tts_to_file(
                text=text, emotion="Happy", speed=2, file_path=audio_file
            )
