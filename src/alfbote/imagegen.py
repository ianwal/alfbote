import random

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

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
scheduler = None
model_id = "dreamlike-art/dreamlike-photoreal-2.0"
ROCM = True

if model_id.startswith("stabilityai/"):
    model_revision = "fp16"
else:
    model_revision = None

if scheduler is None:
    pipe = StableDiffusionPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
        revision=model_revision,
    )
else:
    pipe = StableDiffusionPipeline.from_pretrained(
        model_id,
        scheduler=scheduler,
        torch_dtype=torch.float16,
        revision=model_revision,
    )

pipe = pipe.to(device)

# xformers doesn't work on ROCM for some reason
if not ROCM:
    # xformers only
    pipe.enable_xformers_memory_efficient_attention()

# if model_id.endswith('-base'):
#    image_length = 512
# else:
#    image_length = 768

# I don't have enough VRAM to run larger images on a RX 6600XT
image_length = 512


class ImageGen:
    @staticmethod
    def generate_image(prompt: str, iterations: int = 25):
        num_images = 1
        seed = random.randint(0, 2147483647)
        iterations = max(min(iterations, 60), 5)
        remove_safety = True

        if remove_safety:
            pipe.safety_checker = None

        # TODO: Add option for this
        negative_prompt = None

        images = pipe(
            prompt,
            height=image_length,
            width=image_length,
            num_inference_steps=iterations,
            guidance_scale=9,
            num_images_per_prompt=num_images,
            negative_prompt=negative_prompt,
            generator=torch.Generator("cuda").manual_seed(seed),
        ).images

        return images
