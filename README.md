# alfbote

## Installation


```console
pip install -e .
```

### GPU:
To use ROCM,

See https://pytorch.org/get-started/locally/

Install pytorch using the above guide before anything else e.g.

```sh
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.4.2
```

Also set the environment variable `HSA_OVERRIDE_GFX_VERSION=10.3.0` or it will segfault

For chatgen:

Install llama-cpp-python with OpenCL for ROCM:
```sh
CMAKE_ARGS="-DLLAMA_CLBLAST=on" FORCE_CMAKE=1 pip install llama-cpp-python --force-reinstall --no-cache-dir

Note: Using GPU for ImageGen and ChatGen at the same time is buggy and not recommended. It also requires a large amount of VRAM (>8GB).

```

## License

`alfbote` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
