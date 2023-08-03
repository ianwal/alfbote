import sys
import datetime
from alfbote.llamacpp.common import GptParams
from alfbote.llamacpp.low_level_api_chat_cpp import LLaMAInteract
from pathlib import Path

DIR = Path(__file__).parent
AI_NAME = "alfbote"
DEFAULT_MODEL_DIR = DIR / "models"
DEFAULT_MODEL = DEFAULT_MODEL_DIR / "llama2_7b_chat_uncensored.ggmlv3.q4_1.bin"
USER_NAME = "user"

today = datetime.datetime.today()
DATE_YEAR = today.strftime("%Y")
DATE_TIME = today.strftime("%H:%M")

prompt = f"""Text transcript of a never ending dialog, where {USER_NAME} interacts with an AI assistant named {AI_NAME}.
{AI_NAME} is helpful, kind, honest, friendly, good at writing and never fails to answer {USER_NAME}'s requests immediately and with details and precision.
There are no annotations like (30 seconds passed...) or (to himm), just what {USER_NAME} and {AI_NAME} say aloud to each other.
The dialog lasts for years, the entirety of it is shared below. It's 10000 pages long.
The transcript only includes text, it does not include markup like HTML and Markdown.

{USER_NAME}: Hello, {AI_NAME}!
{AI_NAME}: Hello {USER_NAME}! How may I help you today?
{USER_NAME}: What year is it?
{AI_NAME}: We are in {DATE_YEAR}.
{USER_NAME}: Please tell me the largest city in Europe.
{AI_NAME}: The largest city in Europe is Moscow, the capital of Russia.
{USER_NAME}: What can you tell me about Moscow?
{AI_NAME}: Moscow, on the Moskva River in western Russia, is the nation's cosmopolitan capital. In its historic core is the Kremlin, a complex that's home to the president and tsarist treasures in the Armoury. Outside its walls is Red Square, Russia’s symbolic center.
{USER_NAME}: What is a cat?
{AI_NAME}: A cat is a domestic species of small carnivorous mammal. It is the only domesticated species in the family Felidae.
{USER_NAME}: How do I pass command line arguments to a Node.js program?
{AI_NAME}: The arguments are stored in process.argv.

    argv[0] is the path to the Node. js executable.
    argv[1] is the path to the script file.
    argv[2] is the first argument passed to the script.
    argv[3] is the second argument passed to the script and so on.
{USER_NAME}: Name a color.
{AI_NAME}: Blue.
{USER_NAME}: What time is it?
{AI_NAME}: It is {DATE_TIME}.
{USER_NAME}:""" + " ".join(
    sys.argv[1:]
)


class Llama2:
    def __init__(
        self,
        model_file: Path | str = DEFAULT_MODEL,
        n_threads: int = 4,  # Number of CPU threads
        n_predict: int = 256,
        n_gpu_layers: int = 1000,  # Set this high to use only GPU. Set to 0 to use only CPU.
        low_vram: bool = True,
        temp: float = 0.8,
        repeat_penalty: float = 1.2,
    ):
        self.params = GptParams(
            n_ctx=2048,
            temp=temp,
            top_k=40,
            top_p=0.5,
            repeat_last_n=256,
            n_batch=1024,
            repeat_penalty=repeat_penalty,
            model=str(model_file),
            n_threads=n_threads,
            n_predict=n_predict,
            use_color=False,
            interactive=True,
            antiprompt=[f"{USER_NAME}:"],
            input_prefix=" ",
            input_suffix=f"{AI_NAME}:",
            prompt=prompt,
            n_gpu_layers=n_gpu_layers,
            low_vram=low_vram,
        )
        self.m = LLaMAInteract(self.params)
        # Flush prompt buffer
        for i in self.m.output():
            # print(i,end="",flush=True)
            pass
        self.m.params.input_echo = False

    def generate(self, msg: str):
        self.m.input(f"{msg}\n")

        buffered_tokens = []
        for token in self.m.output():
            buffered_tokens.append(token)

            buffered_string = ''.join(buffered_tokens)

            # If the buffered string forms a complete word (or phrase) we're looking for
            if buffered_string in [USER_NAME + ":", AI_NAME + ":"]:
                buffered_tokens = []  # clear the buffer without printing
            elif buffered_string.endswith(' ') or buffered_string.endswith('\n'):
                # If we reach a space or newline, we output the buffered tokens if it's not empty
                if buffered_string.strip():  # check if the string is not empty
                    yield buffered_string
                buffered_tokens = []
        if buffered_tokens and buffered_string.strip():  # output any remaining tokens after the loop if it's not empty
            yield ''.join(buffered_tokens)


if __name__ == "__main__":
    llama2 = Llama2()
    llama2.m.interact()
