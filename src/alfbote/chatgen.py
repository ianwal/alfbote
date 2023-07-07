from gpt4all import GPT4All

CHAT_MODEL = "nous-hermes-13b.ggmlv3.q4_0.bin"
TTS_MODEL = "tts_models/en/ljspeech/tacotron2-DCA"


class ChatGen:
    def __init__(self, tts: bool = False, gpu: bool = False):
        self.model = GPT4All(CHAT_MODEL)
        self.model._is_chat_session_activated = True
        self.model.current_chat_session = []

        if tts:
            from TTS.api import TTS

            self.tts = TTS(TTS_MODEL, gpu=gpu)
        else:
            self.tts = None

    def generate_message(self, msg: str) -> str:
        output = self.model.generate(msg, n_batch=16)
        return output

    def generate_speech(self, text: str, audio_file: str):
        if self.tts is not None:
            self.tts.tts_to_file(
                text=text, emotion="Happy", speed=2, file_path=audio_file
            )
