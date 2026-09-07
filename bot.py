import asyncio
import logging
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import discord
from discord.ext import commands

import config
from database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("bot")

bot = commands.Bot(
    command_prefix="!",
    intents=config.intents,
    reconnect=True,
    help_command=None,
)


@bot.event
async def on_ready():
    log.info("%s запущен. Гильдий: %s", bot.user, len(bot.guilds))
    # Глобальный sync — команды видны и на серверах, и в ЛС бота.
    # Серверные команды (guild_only) не показываются в ЛС автоматически.
    try:
        await bot.tree.sync()
        log.info("Слэш-команды синхронизированы глобально")
    except Exception as e:
        log.error("Ошибка глобального синка команд: %s", e)


COGS = [
    "cogs.translate",
    "cogs.temp_voice",
    "cogs.tickets",
    "cogs.announce",
    "cogs.levels",
    "cogs.activity_roles",
    "cogs.streamers",
    "cogs.mirror",
    "cogs.backgrounds",
    "cogs.logging",
    "cogs.automod",
]


async def main():
    init_db()
    tg = config.TICKET_GUILD_ID
    if not tg:
        log.warning("TICKET_GUILD_ID не задан — тикеты работать не будут")
    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                log.info("Загружен ког: %s", cog)
            except Exception as e:
                log.exception("Ошибка загрузки %s: %s", cog, e)
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())