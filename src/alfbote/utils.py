from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any


# Run blocking function with async to avoid Discord heartbeat timeouts
async def run_blocking(bot, blocking_func: Callable, *args, **kwargs) -> Any:
    func = partial(blocking_func, *args, **kwargs)  # `run_in_executor` doesn't support kwargs, `functools.partial` does
    return await bot.loop.run_in_executor(None, func)
