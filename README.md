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

## License

`alfbote` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
