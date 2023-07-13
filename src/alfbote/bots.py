from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from rich import print

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


class Alfbote(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="#", intents=intents, status=discord.Status.online)
        self.guild_db = GuildDB()
