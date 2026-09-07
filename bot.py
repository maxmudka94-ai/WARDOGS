import asyncio
import logging
import os
import sys
import uuid

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import discord
from discord.ext import commands

import config
from database import (
    init_db,
    acquire_lease,
    renew_lease,
    release_lease,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("bot")

# Единая метка процесса — проставляется в footer каждого лог-сообщения,
# чтобы по дублям видеть, из одного экземпляра они или из разных.
RUN_ID = uuid.uuid4().hex[:6]

bot = commands.Bot(
    command_prefix="!",
    intents=config.intents,
    reconnect=True,
    help_command=None,
)


async def _lease_heartbeat():
    try:
        await bot.wait_until_ready()
    except Exception:
        return
    while True:
        renew_lease(RUN_ID)
        await asyncio.sleep(10)


@bot.event
async def on_ready():
    log.info("%s запущен. Гильдий: %s (run_id=%s)", bot.user, len(bot.guilds), RUN_ID)
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

    # Единственный инстанс: если лисcp держит другой живой процесс — выходим.
    if not acquire_lease(RUN_ID):
        log.warning("Второй инстанс бота уже работает (run_id другой) — завершаюсь.")
        return

    tg = config.TICKET_GUILD_ID
    if not tg:
        log.warning("TICKET_GUILD_ID не задан — тикеты работать не будут")

    try:
        async with bot:
            bot.run_id = RUN_ID
            for cog in COGS:
                try:
                    await bot.load_extension(cog)
                    log.info("Загружен ког: %s", cog)
                except Exception as e:
                    log.exception("Ошибка загрузки %s: %s", cog, e)
            # Сердцебиение лисцпа, чтобы живой бот не терял владение.
            bot.loop.create_task(_lease_heartbeat())
            await bot.start(config.TOKEN)
    finally:
        release_lease(RUN_ID)
        log.info("Лисцпа освобождён (run_id=%s)", RUN_ID)


if __name__ == "__main__":
    asyncio.run(main())