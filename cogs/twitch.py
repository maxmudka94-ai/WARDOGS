import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord.ext import commands, tasks

import config
from twitch_api import fetch_stream, TwitchError

log = logging.getLogger(__name__)

LIVE_COLOR = discord.Color(0x9146FF)      # фиолетовый Twitch
OFFLINE_COLOR = discord.Color(0x5865F2)   # близко к EMBED_COLOR


class TwitchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._was_live: bool | None = None   # None = ещё не проверяли
        self.twitch_loop.start()

    def cog_unload(self):
        self.twitch_loop.cancel()

    @tasks.loop(seconds=config.TWITCH_CHECK_INTERVAL)
    async def twitch_loop(self):
        try:
            await self._tick()
        except TwitchError as e:
            log.warning("Twitch API error: %s", e)
        except Exception as e:
            log.warning("Twitch tick error: %s", e)

    @twitch_loop.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    async def _tick(self):
        stream = await fetch_stream(config.TWITCH_CHANNEL_LOGIN)
        channel = self.bot.get_channel(config.TWITCH_ANNOUNCE_CHANNEL)
        if channel is None:
            log.warning("Канал %s не найден", config.TWITCH_ANNOUNCE_CHANNEL)
            return

        if stream.is_live:
            embed = self._live_embed(stream)
            await channel.send(embed=embed)
            self._was_live = True
        else:
            # Периодично не спамим оффлайном: уведомляем один раз после стрима.
            if self._was_live is True:
                embed = self._offline_embed(stream)
                await channel.send(embed=embed)
            self._was_live = False

    def _live_embed(self, stream) -> discord.Embed:
        embed = discord.Embed(
            title="🔴 Прямо в эфире!",
            description=f"**{stream.stream_title}**" if stream.stream_title else None,
            url=stream.url,
            color=LIVE_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=stream.display_name, url=stream.url)
        embed.add_field(name="🎮 Игра", value=stream.game, inline=True)
        embed.add_field(name="👥 Зрители", value=f"**{stream.viewers}**", inline=True)
        if stream.thumbnail:
            embed.set_image(url=stream.thumbnail)
        embed.set_footer(text=f"Twitch • {stream.login}", icon_url="https://static.twitchcdn.net/assets/favicon-32-d6025c14e900565d6177.png")
        return embed

    def _offline_embed(self, stream) -> discord.Embed:
        embed = discord.Embed(
            title="Стрим закончился",
            description=f"[{stream.display_name}]({stream.url}) вернулся(ась) в оффлайн.",
            color=OFFLINE_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(TwitchCog(bot))
