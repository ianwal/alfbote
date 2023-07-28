from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks
from rich import print
import queue

if TYPE_CHECKING:
    from discord import Message, Guild
    from typing import Any, Callable

intents = discord.Intents.default()
intents.message_content = True


class GuildDB:
    def __init__(self):
        self.db: dict = {}

    # Create a guild in the DB
    def create(self, guild: Guild, data: dict) -> None:
        self.db[guild.id] = data

    # Get an item from the DB
    def get(self, guild: Guild, key: str) -> Any | None:
        return self.db.get(guild.id, None).get(key, None)

    # Insert an entry into a guild in the DB without overwriting existing entries
    def insert(self, guild: Guild, key: str, data: Any) -> None:
        if self.db[guild.id].get(key, None) is None:
            self.db[guild.id][key] = data

    # Update an entry for a guild in the DB
    def update(self, guild: Guild, key: str, data: Any) -> None:
        self.db[guild.id][key] = data

    # Delete a guild from the DB
    def delete(self, key: str) -> None:
        del self.db[key]

    def __str__(self):
        return str(self.db)


class CLICog(commands.Cog, name="Input"):
    def __init__(self, bot: Alfbote):
        self.bot = bot
        self.cli.start()
        self.input_queue = queue.Queue()

    def cog_unload(self):
        self.cli.cancel()

    @tasks.loop()
    async def cli(self):
        input_queue = queue.Queue()
        print("Command line interface started.")
        while True:
            input_queue.put(input("> "))
            cmd = input_queue.get()
            pgm = cmd.split(" ")[0]
            args = cmd.split(" ")[1:]
            try:
                match pgm:
                    case "msg":
                        # Specify channel with chan=<channel_id>
                        if "chan" in args[0]:
                            chan = self.bot.get_channel(int(args[0].split("=")[1]))
                            msg = " ".join(args[1:])
                        else:
                            chan = self.bot.get_channel(469733139552534531)
                            msg = " ".join(args)

                        await chan.send(msg)
                    case "exit":
                        exit(0)
                    case _:
                        print("Unknown command")
            except Exception as e:
                print(e)

    @cli.before_loop
    async def before_inner(self):
        await self.bot.wait_until_ready()


class Alfbote(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="#", intents=intents, status=discord.Status.online)
        self.guild_db = GuildDB()
