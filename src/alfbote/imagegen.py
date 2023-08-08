from __future__ import annotations

import os
from random import randint
from tempfile import SpooledTemporaryFile
from threading import Lock
from typing import TYPE_CHECKING
from rich import print
from io import BytesIO

from alfbote.utils import run_blocking

if TYPE_CHECKING:
    from alfbote.bots import Alfbote

from discord import ApplicationContext

import torch
from diffusers import (
    StableDiffusionPipeline,
)
from discord import File
from discord.ext import commands


class ImageGen(commands.Cog, name="ImageGen"):
    # I don't have enough VRAM to run 768x768 on a RX 6600XT
    IMAGE_DIM = 512
    MODEL_ID = "SG161222/Realistic_Vision_V5.1_noVAE"
    DEFAULT_PROMPT = ""
    DEFAULT_NEGATIVE_PROMPT = "visual artifacts, nsfw, nude, naked, (deformed eyes, mutated hands and fingers:1.4), (deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, extra limb, missing limb, floating limbs, disconnected limbs, mutation, mutated, ugly, disgusting, amputation"

    def __init__(self, bot: Alfbote, gpu: bool = False, low_vram: bool = True, ROCM: bool = False):
        self.bot: Alfbote = bot
        self.image_lock = Lock()
        self.GPU: bool = gpu
        self.low_vram: bool = low_vram

        if gpu:
            if not torch.cuda.is_available():
                print("[red] ERROR: CUDA not detected in ImageGen. Falling back to CPU.")
                self.GPU = False
            else:
                # enabling benchmark option seems to enable a range of cards to do fp16 when they otherwise can't
                # see https://github.com/AUTOMATIC1111/stable-diffusion-webui/pull/4407
                if any(
                    torch.cuda.get_device_capability(devid) == (7, 5) for devid in range(0, torch.cuda.device_count())
                ):
                    torch.backends.cudnn.benchmark = True

                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True

        torch.set_float32_matmul_precision('medium')
        torch_dtype = torch.float16 if self.GPU else torch.float32
        self.pipe = StableDiffusionPipeline.from_pretrained(
            ImageGen.MODEL_ID,
            use_safetensors=True,
            torch_dtype=torch_dtype,
        )

        if self.GPU:
            if ROCM:
                print("[green] ImageGen: ROCM enabled")
                os.environ["HSA_OVERRIDE_GFX_VERSION"] = "10.3.0"
            else:
                print("[green] ImageGen: CUDA enabled")

            self.device = torch.device("cuda")
            self.pipe.enable_attention_slicing()
            self.pipe.enable_vae_tiling()
            if self.low_vram:
                print("[yellow] ImageGen: Low VRAM enabled")
                self.pipe.enable_model_cpu_offload()
            else:
                # Below does not work for me currently. Maybe an ROCM issue?
                # from platform import python_version_tuple
                # if int(python_version_tuple()[1]) < 11:
                # Use torch compile if <3.11 because it's not supported for 3.11
                #     self.pipe.unet.to(memory_format=torch.channels_last)
                #     self.pipe.unet = torch.compile(self.pipe.unet, mode="reduce-overhead", fullgraph=True)
                self.pipe = self.pipe.to(self.device)
        else:
            self.device = torch.device("cpu")

    # Image generation
    @commands.command()
    async def i(self, ctx: ApplicationContext, *, msg: str = None):
        # Only process one prompt at a time
        if msg is None or self.image_lock.locked():
            return

        async with ctx.typing():
            with self.image_lock:
                with SpooledTemporaryFile(mode="w+b") as file:
                    images = await run_blocking(self.bot, ImageGen.generate_image, self, msg)
                    images[0].save(file, "jpeg")
                    file.seek(0)
                    discord_file = File(BytesIO(file.read()), filename=f"{msg[:64]}.jpg")
                    await ctx.send(f"{ctx.message.author.mention} {msg}", file=discord_file)

    def generate_image(self, prompt: str, iterations: int = 25, negative_prompt: str | None = DEFAULT_NEGATIVE_PROMPT):
        prompt = prompt + " , " + ImageGen.DEFAULT_PROMPT
        iterations = max(min(iterations, 60), 5)  # Get iterations in range (5, 60)

        seed = randint(0, 2147483647)
        generator = torch.Generator(self.device).manual_seed(seed)

        images = self.pipe(
            prompt,
            height=ImageGen.IMAGE_DIM,
            width=ImageGen.IMAGE_DIM,
            num_inference_steps=iterations,
            guidance_scale=7,
            num_images_per_prompt=1,
            negative_prompt=negative_prompt,
            generator=generator,
        ).images
        self.torch_gc()
        return images

    def torch_gc(self):
        if torch.cuda.is_available():
            with torch.cuda.device(self.device):
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
