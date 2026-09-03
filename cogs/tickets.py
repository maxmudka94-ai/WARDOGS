import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from io import BytesIO

import config
from database import get_conn


class TicketCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Подать заявку", style=discord.ButtonStyle.green, custom_id="ticket_create")
    async def ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket(interaction, "clan")

    @discord.ui.button(label="Подать заявку в академию", style=discord.ButtonStyle.blurple, custom_id="ticket_create_academy")
    async def academy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket(interaction, "academy")

    async def _create_ticket(self, interaction: discord.Interaction, ticket_type: str):
        await interaction.response.defer(ephemeral=True)

        conn = get_conn()
        existing = conn.execute(
            "SELECT 1 FROM tickets WHERE user_id = ? AND status = 'open' AND ticket_type = ?",
            (interaction.user.id, ticket_type),
        ).fetchone()
        if existing:
            await interaction.followup.send("У вас уже есть открытый тикет этого типа.", ephemeral=True)
            return

        guild = interaction.guild
        user = interaction.user

        type_config = {
            "clan": {
                "prefix": "тикет",
                "color": discord.Color.dark_red(),
                "category": config.TICKET_CATEGORY,
                "title": "Заявка в клан",
                "question": (
                    "**Пожалуйста, ответьте на вопросы:**\n\n"
                    "**1.** Сколько часов в игре?\n"
                    "**2.** Для чего вы хотите вступить в клан?\n"
                    "**3.** Откуда вы узнали о WARDOGS?\n"
                    "**4.** Сколько вам лет?\n"
                    "**5.** Какой у вас часовой пояс?\n"
                    "**6.** Какой у вас средний онлайн в неделю?"
                ),
            },
            "academy": {
                "prefix": "академка",
                "color": discord.Color.gold(),
                "category": config.TICKET_CATEGORY,
                "title": "Заявка в академию",
                "question": (
                    "**Пожалуйста, ответьте на вопросы:**\n\n"
                    "**1.** Готовы ли вы пройти курс молодого бойца?\n"
                    "**2.** Сколько вам лет?\n"
                    "**3.** Откуда вы узнали о WARDOGS?\n"
                    "**4.** Сколько времени в неделю вы сможете уделять игре?\n"
                    "**5.** Чему вы хотите научиться?\n"
                    "**6.** Планируете ли вы повышаться до старшего состава?"
                ),
            },
            "promotion": {
                "prefix": "повышение",
                "color": discord.Color.green(),
                "category": config.TICKET_CATEGORY,
                "title": "Заявка на повышение",
                "question": (
                    "**Пожалуйста, ответьте на вопросы:**\n\n"
                    "**1.** Ваш никнейм в игре?\n"
                    "**2.** Какую должность вы занимаете сейчас?\n"
                    "**3.** На какую должность хотите повыситься?\n"
                    "**4.** Что вы сделали для клана за последнее время?\n"
                    "**5.** Почему вы заслуживаете повышения?"
                ),
            },
            "arma": {
                "prefix": "арма",
                "color": discord.Color.blue(),
                "category": config.TICKET_CATEGORY,
                "title": "Заявка на армача",
                "question": (
                    "**Пожалуйста, ответьте на вопросы:**\n\n"
                    "**1.** Ваш никнейм в игре?\n"
                    "**2.** Как давно играете?\n"
                    "**3.** Почему хотите стать армачом?\n"
                    "**4.** Какие классы/роли вы хорошо освоили?\n"
                    "**5.** Есть ли у вас опыт ведения армачей?"
                ),
            },
        }

        cfg = type_config[ticket_type]
        category = guild.get_channel(cfg["category"])

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True),
        }
        for staff_role_id in config.TICKET_STAFF_ROLES:
            staff = guild.get_role(staff_role_id)
            if staff:
                overwrites[staff] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        channel = await guild.create_text_channel(
            name=f"{cfg['prefix']}-{user.name}",
            category=category,
            overwrites=overwrites,
            topic=f"Тикет от {user} ({user.id}) | Тип: {ticket_type}",
        )

        embed = discord.Embed(
            title=cfg["title"],
            description=cfg["question"],
            color=cfg["color"],
            timestamp=datetime.utcnow(),
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        embed.set_footer(text=f"ID: {user.id}")

        if config.TICKET_STAFF_ROLES:
            staff_mention = " ".join(f"<@&{r}>" for r in config.TICKET_STAFF_ROLES)
        else:
            staff_mention = ""
        await channel.send(content=f"{staff_mention} {user.mention}", embed=embed, view=TicketCloseView())

        conn.execute(
            "INSERT INTO tickets (user_id, channel_id, ticket_type, status, created_at) VALUES (?, ?, ?, 'open', ?)",
            (user.id, channel.id, ticket_type, datetime.utcnow().isoformat()),
        )
        conn.commit()

        await interaction.followup.send(f"Тикет создан: {channel.mention}", ephemeral=True)

        if config.TICKET_LOG_CHANNEL:
            log_ch = guild.get_channel(config.TICKET_LOG_CHANNEL)
            if log_ch:
                await log_ch.send(f"🎫 Тикет создан: {channel.mention} | Тип: {ticket_type} | Пользователь: {user}")


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Закрыть тикет", style=discord.ButtonStyle.red, custom_id="ticket_close", emoji="🔒")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Вы уверены?", view=TicketCloseConfirmView(), ephemeral=True
        )


class TicketCloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Да", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        conn = get_conn()
        row = conn.execute("SELECT * FROM tickets WHERE channel_id = ?", (interaction.channel.id,)).fetchone()

        if row:
            conn.execute(
                "UPDATE tickets SET status = 'closed', closed_at = ?, closed_by = ? WHERE channel_id = ?",
                (datetime.utcnow().isoformat(), interaction.user.id, interaction.channel.id),
            )
            conn.commit()

            member = interaction.guild.get_member(row["user_id"])
            if member:
                await interaction.channel.set_permissions(member, overwrite=None)

        embed = discord.Embed(
            title="Тикет закрыт",
            description=f"Закрыт модератором {interaction.user.mention}.\nСохраните транскрипт или удалите канал.",
            color=discord.Color.greyple(),
        )
        await interaction.edit_original_response(embed=embed, view=TicketClosedView())

        if config.TICKET_LOG_CHANNEL:
            log_ch = interaction.guild.get_channel(config.TICKET_LOG_CHANNEL)
            if log_ch:
                await log_ch.send(f"🎫 Тикет закрыт: {interaction.channel.mention} | Закрыл: {interaction.user}")

    @discord.ui.button(label="Нет", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Закрытие отменено.", view=None)


class TicketClosedView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Удалить канал", style=discord.ButtonStyle.danger, custom_id="closed_delete", emoji="🗑️")
    async def delete_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        conn = get_conn()
        conn.execute("DELETE FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
        conn.commit()
        await interaction.channel.delete()

    @discord.ui.button(label="Сохранить транскрипт", style=discord.ButtonStyle.blurple, custom_id="closed_transcript", emoji="📄")
    async def save_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        messages = [msg async for msg in interaction.channel.history(oldest_first=True)]

        lines = []
        for msg in messages:
            ts = msg.created_at.strftime("%d.%m.%Y %H:%M:%S")
            content = msg.content or ""
            if msg.embeds:
                for e in msg.embeds:
                    if e.description:
                        content += f" {e.description}"
            lines.append(f"[{ts}] {msg.author}: {content}")

        transcript = "\n".join(lines)
        file = discord.File(fp=BytesIO(transcript.encode("utf-8")), filename=f"transcript-{interaction.channel.name}.txt")

        if config.TICKET_TRANSCRIPT_CHANNEL:
            tr_ch = interaction.guild.get_channel(config.TICKET_TRANSCRIPT_CHANNEL)
            if tr_ch:
                await tr_ch.send(file=file)

        await interaction.followup.send("Транскрипт сохранён.")

    @discord.ui.button(label="Одобрить", style=discord.ButtonStyle.green, custom_id="closed_approve", emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        conn = get_conn()
        row = conn.execute("SELECT * FROM tickets WHERE channel_id = ?", (interaction.channel.id,)).fetchone()
        if not row:
            await interaction.followup.send("Тикет не найден.")
            return

        conn.execute("UPDATE tickets SET status = 'approved' WHERE channel_id = ?", (interaction.channel.id,))
        conn.commit()

        member = interaction.guild.get_member(row["user_id"])
        if member:
            try:
                await member.send(f"✅ Ваша заявка ({row['ticket_type']}) одобрена! Добро пожаловать!")
            except discord.Forbidden:
                pass

        embed = discord.Embed(
            title="Заявка одобрена",
            description=f"Одобрена {interaction.user.mention}.",
            color=discord.Color.green(),
        )
        await interaction.edit_original_response(embed=embed)

        if config.TICKET_LOG_CHANNEL:
            log_ch = interaction.guild.get_channel(config.TICKET_LOG_CHANNEL)
            if log_ch:
                await log_ch.send(f"✅ Тикет одобрен: {interaction.channel.mention} | Пользователь: <@{row['user_id']}>")

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red, custom_id="closed_reject", emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        conn = get_conn()
        row = conn.execute("SELECT * FROM tickets WHERE channel_id = ?", (interaction.channel.id,)).fetchone()
        if not row:
            await interaction.followup.send("Тикет не найден.")
            return

        conn.execute("UPDATE tickets SET status = 'rejected' WHERE channel_id = ?", (interaction.channel.id,))
        conn.commit()

        member = interaction.guild.get_member(row["user_id"])
        if member:
            try:
                await member.send(f"❌ Ваша заявка ({row['ticket_type']}) отклонена.")
            except discord.Forbidden:
                pass

        embed = discord.Embed(
            title="Заявка отклонена",
            description=f"Отклонена {interaction.user.mention}.",
            color=discord.Color.red(),
        )
        await interaction.edit_original_response(embed=embed)

        if config.TICKET_LOG_CHANNEL:
            log_ch = interaction.guild.get_channel(config.TICKET_LOG_CHANNEL)
            if log_ch:
                await log_ch.send(f"❌ Тикет отклонён: {interaction.channel.mention}")


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    ticket_group = app_commands.Group(name="tickets", description="Управление тикетами")

    @ticket_group.command(name="panel", description="Отправить панель создания тикетов")
    @app_commands.describe(channel="Канал для панели")
    async def ticket_panel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel

        embed = discord.Embed(
            title="ПОДАЧА ЗАЯВКИ В WARDOGS RU",
            description=(
                "**Условия:**\n"
                "🔹 Возраст от 16 лет\n"
                "🔹 Адекватность\n"
                "🔹 Более 100 часов в игре\n"
                "🔹 Желание учиться\n\n"
                "Если менее 100 часов — нажмите **\"Подать заявку в академию\"**\n\n"
                "Нажимай кнопку **\"Подать заявку\"** 👇"
            ),
            color=discord.Color.dark_red(),
        )
        await target.send(embed=embed, view=TicketCreateView())
        await interaction.followup.send(f"Панель отправлена в {target.mention}.", ephemeral=True)

    @ticket_group.command(name="promote_panel", description="Панель заявок на повышение")
    @app_commands.describe(channel="Канал для панели")
    async def promote_panel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel

        embed = discord.Embed(
            title="📈 Заявка на повышение",
            description="Нажмите кнопку ниже, чтобы подать заявку на повышение.",
            color=discord.Color.green(),
        )

        view = discord.ui.View(timeout=None)

        @discord.ui.button(label="Подать заявку", style=discord.ButtonStyle.green, custom_id="ticket_promotion", emoji="📈")
        async def promo_btn(interaction: discord.Interaction, button: discord.ui.Button):
            await TicketCreateView()._create_ticket(interaction, "promotion")

        view.add_item(promo_btn)
        await target.send(embed=embed, view=view)
        await interaction.followup.send(f"Панель отправлена в {target.mention}.", ephemeral=True)

    @ticket_group.command(name="arma_panel", description="Панель заявок на армача")
    @app_commands.describe(channel="Канал для панели")
    async def arma_panel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel

        embed = discord.Embed(
            title="⚔️ Заявка на армача",
            description="Нажмите кнопку ниже, чтобы подать заявку на армача.",
            color=discord.Color.blue(),
        )

        view = discord.ui.View(timeout=None)

        @discord.ui.button(label="Подать заявку", style=discord.ButtonStyle.blurple, custom_id="ticket_arma", emoji="⚔️")
        async def arma_btn(interaction: discord.Interaction, button: discord.ui.Button):
            await TicketCreateView()._create_ticket(interaction, "arma")

        view.add_item(arma_btn)
        await target.send(embed=embed, view=view)
        await interaction.followup.send(f"Панель отправлена в {target.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
