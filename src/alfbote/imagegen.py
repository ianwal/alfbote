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
    pass

from discord import ApplicationContext, Member, Message

import torch
from diffusers import (
    DDIMScheduler,
    DPMSolverMultistepScheduler,
    EulerDiscreteScheduler,
    LMSDiscreteScheduler,
    PNDMScheduler,
    DiffusionPipeline,
    StableDiffusionPipeline,
)
from discord import File
from discord.ext import commands


class ImageGen(commands.Cog, name="ImageGen"):
    # I don't have enough VRAM to run 768x768 on a RX 6600XT
    IMAGE_DIM = 512
    MODEL_ID = "dreamlike-art/dreamlike-photoreal-2.0"

    def __init__(self, bot, gpu: bool = False, low_vram=False, ROCM: bool = False):
        self.bot = bot
        self.image_lock = Lock()
        self.GPU = gpu
        self.low_vram = low_vram

        if self.GPU:
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

        torch_dtype = torch.float16 if self.GPU else torch.float32
        torch.set_float32_matmul_precision('medium')
        self.pipe = StableDiffusionPipeline.from_pretrained(
            ImageGen.MODEL_ID,
            use_safetensors=True,
            torch_dtype=torch_dtype,
        )
        self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(self.pipe.scheduler.config)

        if self.GPU:
            if ROCM:
                print("[magenta] ImageGen: ROCM enabled")
                os.environ["HSA_OVERRIDE_GFX_VERSION"] = "10.3.0"
            else:
                print("[green] ImageGen: CUDA enabled")

            self.device = torch.device("cuda")
            self.pipe.enable_attention_slicing()
            self.pipe.enable_vae_tiling()
            if low_vram:
                print("[yellow] ImageGen: Low VRAM enabled")
                self.pipe.enable_model_cpu_offload()
            else:
                self.pipe = self.pipe.to(self.device)
        else:
            self.device = torch.device("cpu")

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
                    discord_file = File(BytesIO(file.read()), filename=f"{msg[:64]}.jpg")
                    await ctx.send(f"{ctx.message.author.mention} {msg}", file=discord_file)

    def generate_image(self, prompt: str, iterations: int = 20, negative_prompt: str = None):
        num_images = 1
        seed = randint(0, 2147483647)
        iterations = max(min(iterations, 60), 5)  # Get iterations in range (5, 60)

        if self.GPU:
            generator = torch.Generator("cuda").manual_seed(seed)
        else:
            generator = torch.Generator("cpu").manual_seed(seed)

        images = self.pipe(
            prompt,
            height=ImageGen.IMAGE_DIM,
            width=ImageGen.IMAGE_DIM,
            num_inference_steps=iterations,
            guidance_scale=9,
            num_images_per_prompt=num_images,
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
