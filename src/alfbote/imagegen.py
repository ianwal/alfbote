from __future__ import annotations

import os
from random import randint
from tempfile import SpooledTemporaryFile
from threading import Lock
from typing import TYPE_CHECKING
from rich import print

from alfbote.utils import run_blocking

if TYPE_CHECKING:
    pass

from discord import ApplicationContext, Member, Message

import mediapy as media
import torch
from diffusers import (
    DDIMScheduler,
    DPMSolverMultistepScheduler,
    EulerDiscreteScheduler,
    LMSDiscreteScheduler,
    PNDMScheduler,
    StableDiffusionPipeline,
)
from discord import File
from discord.ext import commands


class ImageGen(commands.Cog, name="ImageGen"):
    # I don't have enough VRAM to run larger images on a RX 6600XT
    IMAGE_LENGTH = 512

    def __init__(self, bot, ROCM: bool = False):
        self.bot = bot
        self.image_lock = Lock()

        if not torch.cuda.is_available():
            print("[red] ERROR: CUDA not detected. Exiting...")
            exit(1)

        scheduler = None
        MODEL_ID = "dreamlike-art/dreamlike-photoreal-2.0"
        # MODEL_ID = "runwayml/stable-diffusion-v1-5"

        if MODEL_ID.startswith("stabilityai/"):
            model_revision = "fp16"
        else:
            model_revision = None

        if scheduler is None:
            self.pipe = StableDiffusionPipeline.from_pretrained(
                MODEL_ID,
                torch_dtype=torch.float16,
                revision=model_revision,
            )
        else:
            self.pipe = StableDiffusionPipeline.from_pretrained(
                MODEL_ID,
                scheduler=scheduler,
                torch_dtype=torch.float16,
                revision=model_revision,
            )

        self.setup_gpu(ROCM=ROCM)

    def setup_gpu(self, ROCM: bool = False):
        if ROCM:
            # ROCM workaround
            os.environ["HSA_OVERRIDE_GFX_VERSION"] = "10.3.0"
        else:
            # xformers doesn't work on ROCM for some reason
            self.pipe.enable_xformers_memory_efficient_attention()

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.pipe = self.pipe.to(self.device)

    # Image generation
    @commands.command()
    async def i(self, ctx: ApplicationContext, *, msg: str = None):
        # Only process one prompt at a time
        if msg is None or self.image_lock.locked():
            return

        with self.image_lock:
            async with ctx.typing():
                with SpooledTemporaryFile(mode="w+b") as file:
                    images = await run_blocking(self.bot, ImageGen.generate_image, self, msg)
                    images[0].save(file, "jpeg")
                    file.seek(0)
                    discord_file = File(file, filename=f"{msg}.jpg")
                    await ctx.send(f"{ctx.message.author.mention} {msg}", file=discord_file)

    def generate_image(self, prompt: str, iterations: int = 25, negative_prompt: str = None):
        num_images = 1
        seed = randint(0, 2147483647)
        iterations = max(min(iterations, 60), 5)  # Get iterations in range (5, 60)
        remove_safety = True

        if remove_safety:
            self.pipe.safety_checker = None

        images = self.pipe(
            prompt,
            height=ImageGen.IMAGE_LENGTH,
            width=ImageGen.IMAGE_LENGTH,
            num_inference_steps=iterations,
            guidance_scale=9,
            num_images_per_prompt=num_images,
            negative_prompt=negative_prompt,
            generator=torch.Generator("cuda").manual_seed(seed),
        ).images

        return images
