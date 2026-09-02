import asyncio
import discord
from discord import app_commands
from deep_translator import GoogleTranslator

TOKEN = "MTU0Mjk0MDM3OTUyNjA3NDM5OA.GI81xd.dM9ns01bz9o0jp1vX8MesQGy1xm3JyrH9Tw_rY"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

user_attachments = {}
user_target_channel = {}


async def async_translate_text(text: str, target_lang: str = 'ru') -> str:
    """Безопасный асинхронный перевод через deep-translator"""
    try:
        def sync_translate():
            translator = GoogleTranslator(source='auto', target=target_lang)
            return translator.translate(text)

        translated = await asyncio.to_thread(sync_translate)
        return translated
    except Exception as e:
        print(f"[ОШИБКА ПЕРЕВОДА]: {e}")
        return None


class SendMessageModal(discord.ui.Modal, title="Отправка сообщения"):
    message_text = discord.ui.TextInput(
        label="Текст сообщения (необязательно)",
        style=discord.TextStyle.paragraph,
        placeholder="Введите текст или оставьте пустым, если отправляете только фото...",
        required=False,
        max_length=2000
    )

    def __init__(self, channel: discord.TextChannel, attachments: list = None):
        super().__init__()
        self.channel = channel
        self.attachments = attachments or []

    async def on_submit(self, interaction: discord.Interaction):
        try:
            files_to_send = []
            for att in self.attachments:
                file_bytes = await att.to_file()
                files_to_send.append(file_bytes)

            content = self.message_text.value.strip() if self.message_text.value else None

            if not content and not files_to_send:
                await interaction.response.send_message(
                    "❌ Сообщение не может быть пустым! Введите текст или прикрепите фото.",
                    ephemeral=True
                )
                return

            await self.channel.send(content=content, files=files_to_send)
            user_attachments.pop(interaction.user.id, None)
            user_target_channel.pop(interaction.user.id, None)

            await interaction.response.send_message(
                f"✅ Сообщение успешно отправлено в канал #{self.channel.name}!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Не удалось отправить сообщение: {e}",
                ephemeral=True
            )


class PhotoChoiceView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.channel = channel

    @discord.ui.button(label="Да", style=discord.ButtonStyle.success)
    async def photo_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_target_channel[interaction.user.id] = self.channel
        await interaction.response.send_message(
            "📸 Прикрепите фото к сообщению прямо в этот чат (через + в Discord). "
            "После отправки фото откроется кнопка публикации.",
            ephemeral=True
        )

    @discord.ui.button(label="Нет", style=discord.ButtonStyle.danger)
    async def photo_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        saved_attachments = user_attachments.get(interaction.user.id, [])
        await interaction.response.send_modal(SendMessageModal(self.channel, saved_attachments))


class ChannelSelectView(discord.ui.View):
    def __init__(self, guild: discord.Guild, page: int = 0):
        super().__init__(timeout=60)
        self.guild = guild
        self.page = page

        all_channels = guild.text_channels
        
        start = page * 25
        end = start + 25
        current_channels = all_channels[start:end]

        options = [
            discord.SelectOption(label=f"#{ch.name}", value=str(ch.id))
            for ch in current_channels
        ]
        total_pages = (len(all_channels) - 1) // 25 + 1
        placeholder = f"Выбери канал (Стр. {page + 1}/{total_pages})..." if total_pages > 1 else "Выбери канал..."

        select = discord.ui.Select(
            placeholder=placeholder,
            options=options
        )
        select.callback = self.channel_selected
        self.add_item(select)

        if page > 0:
            prev_btn = discord.ui.Button(label="◀ Назад", style=discord.ButtonStyle.gray)
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)

        if end < len(all_channels):
            next_btn = discord.ui.Button(label="Вперед ▶", style=discord.ButtonStyle.gray)
            next_btn.callback = self.next_page
            self.add_item(next_btn)

    async def prev_page(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=ChannelSelectView(self.guild, self.page - 1)
        )

    async def next_page(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=ChannelSelectView(self.guild, self.page + 1)
        )

    async def channel_selected(self, interaction: discord.Interaction):
        channel_id = int(interaction.data["values"][0])
        channel = interaction.client.get_channel(channel_id)
        
        await interaction.response.send_message(
            "**Шаг 3:** Вы хотите добавить фото к сообщению?",
            view=PhotoChoiceView(channel),
            ephemeral=True
        )


class GuildSelectView(discord.ui.View):
    def __init__(self, guilds: list, page: int = 0):
        super().__init__(timeout=60)
        self.guilds = guilds
        self.page = page
        
        start = page * 25
        end = start + 25
        current_guilds = guilds[start:end]

        options = [
            discord.SelectOption(label=guild.name, value=str(guild.id))
            for guild in current_guilds
        ]

        total_pages = (len(guilds) - 1) // 25 + 1
        placeholder = f"Выбери сервер (Стр. {page + 1}/{total_pages})..." if total_pages > 1 else "Выбери сервер..."

        select = discord.ui.Select(
            placeholder=placeholder,
            options=options
        )
        select.callback = self.guild_selected
        self.add_item(select)

        if page > 0:
            prev_btn = discord.ui.Button(label="◀ Назад", style=discord.ButtonStyle.gray)
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)

        if end < len(guilds):
            next_btn = discord.ui.Button(label="Вперед ▶", style=discord.ButtonStyle.gray)
            next_btn.callback = self.next_page
            self.add_item(next_btn)

    async def prev_page(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=GuildSelectView(self.guilds, self.page - 1)
        )

    async def next_page(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            view=GuildSelectView(self.guilds, self.page + 1)
        )

    async def guild_selected(self, interaction: discord.Interaction):
        guild_id = int(interaction.data["values"][0])
        guild = interaction.client.get_guild(guild_id)
        
        await interaction.response.send_message(
            f"**Шаг 2:** Выбери канал на сервере {guild.name}:",
            view=ChannelSelectView(guild),
            ephemeral=True
        )


@tree.context_menu(name="Перевести")
async def translate_context(interaction: discord.Interaction, message: discord.Message):
    text = message.content.strip()

    if not text:
        await interaction.response.send_message(
            "❌ Сообщение не содержит текста для перевода.",
            ephemeral=True
        )
        return

    translated_text = await async_translate_text(text, 'ru')

    if not translated_text:
        await interaction.response.send_message(
            "❌ Не удалось перевести сообщение или текст уже на русском.",
            ephemeral=True
        )
        return

    author_name = message.author.display_name

    embed = discord.Embed(
        title=f"🌐 Перевод • {author_name}",
        description=translated_text,
        color=0x5865F2
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_ready():
    # Глобальная синхронизация для ЛС и всех серверов одновременно
    await tree.sync()
    print(f"🐺 {bot.user} запущен! Контекстное меню «Перевести» синхронизировано глобально.")


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user or message.author.bot:
        return

    text = message.content.strip()
    text_lower = text.lower()
    attachments = list(message.attachments)

    # 1. ОБРАБОТКА ЛИЧНЫХ СООБЩЕНИЙ (ЛС)
    if isinstance(message.channel, discord.DMChannel):
        if message.author.id in user_target_channel and attachments:
            channel = user_target_channel.pop(message.author.id)
            user_attachments[message.author.id] = attachments
            
            view = discord.ui.View()
            btn = discord.ui.Button(label="Перейти к отправке текста/публикации", style=discord.ButtonStyle.primary)

            async def btn_callback(interaction: discord.Interaction):
                await interaction.response.send_modal(SendMessageModal(channel, attachments))

            btn.callback = btn_callback
            view.add_item(btn)

            await message.channel.send(
                f"✅ Успешно прикреплено фото: **{len(attachments)} шт.** Нажмите кнопку ниже для отправки:",
                view=view
            )
            return

        # Если введена команда панельки — обрабатываем и выходим
        if text_lower in ["старт", "start"] or (attachments and message.author.id not in user_target_channel):
            admin_guilds = []
            for guild in bot.guilds:
                member = guild.get_member(message.author.id)
                if not member:
                    try:
                        member = await guild.fetch_member(message.author.id)
                    except Exception:
                        continue

                if member and (member.guild_permissions.manage_guild or member.guild_permissions.administrator):
                    admin_guilds.append(guild)
            
            if not admin_guilds:
                await message.channel.send("❌ У тебя нет прав администратора («Управление сервером») ни на одном из общих серверов!")
                return

            if attachments:
                user_attachments[message.author.id] = attachments

            await message.channel.send(
                "⚙️ **Панель отправки сообщений**\n**Шаг 1:** Выбери сервер:",
                view=GuildSelectView(admin_guilds)
            )
            return

    # 2. ОБЩИЙ АВТОПЕРЕВОД (Работает и в ЛС, и в каналах серверов)
    if not text or len(text) < 2:
        return

    if text.startswith(("http://", "https://", "!", "/", ".")):
        return

    translated_text = await async_translate_text(text, 'ru')

    if translated_text and translated_text.strip().lower() != text.lower():
        author_name = message.author.display_name

        embed = discord.Embed(
            title=f"🌐 Перевод • {author_name}",
            description=translated_text,
            color=0x5865F2
        )
        await message.reply(embed=embed, mention_author=False)


@tree.command(
    name="announce",
    description="Отправить объявление от имени WARDOGS RU"
)
@app_commands.describe(text="Текст объявления")
async def announce(interaction: discord.Interaction, text: str):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ У тебя нет прав для этой команды.",
            ephemeral=True
        )
        return

    await interaction.channel.send(
        f"🐺 **WARDOGS RU**\n\n{text}"
    )

    await interaction.response.send_message(
        "✅ Объявление отправлено.",
        ephemeral=True
    )


@tree.command(
    name="rules",
    description="Опубликовать правила WARDOGS RU"
)
async def rules(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ У тебя нет прав для этой команды.",
            ephemeral=True
        )
        return
    embed = discord.Embed(
        title="🐺 WARDOGS RU",
        description=(
            "## 📜 Правила сообщества\n\n"
            "Добро пожаловать в русскоязычное сообщество "
            "**WARDOGS RU!**\n"
            "Здесь мы играем, общаемся и собираемся в отряды."
        ),
        color=0x5865F2
    )

    embed.add_field(
        name="🤝 1. Уважение",
        value=(
            "Уважайте других участников.\n"
            "Оскорбления, травля, унижение и провокации запрещены."
        ),
        inline=False
    )

    embed.add_field(
        name="💬 2. Общение",
        value="Спорить можно. Переходить на личности — нет.",
        inline=False
    )

    embed.add_field(
        name="🚫 3. Запрещённый контент",
        value=(
            "NSFW-контент, шок-контент, угрозы, "
            "распространение личных данных и незаконные материалы запрещены."
        ),
        inline=False
    )

    embed.add_field(
        name="📢 4. Спам и реклама",
        value=(
            "Запрещены флуд, спам и навязчивая реклама.\n"
            "Реклама разрешена только в соответствующих каналах."
        ),
        inline=False
    )

    embed.add_field(
        name="🎮 5. WARDOGS",
        value=(
            "Не выдавайте себя за администрацию сообщества "
            "или разработчиков игры."
        ),
        inline=False
    )

    embed.add_field(
        name="🎙 6. Голосовые каналы",
        value=(
            "Не мешайте другим участникам играть и общаться.\n"
            "Намеренный шум и провокации запрещены."
        ),
        inline=False
    )

    embed.add_field(
        name="🛡 7. Администрация",
        value=(
            "**Предупреждение → Мут → Кик → "
            "Временный бан → Перманентный бан**\n\n"
            "За серьёзные нарушения наказание может быть выдано сразу."
        ),
        inline=False
    )

    embed.add_field(
        name="🐺 Главное правило",
        value=(
            "**Мы здесь ради игры, общения и хорошей атмосферы.**\n\n"
            "Добро пожаловать в WARDOGS RU! 🐺"
        ),
        inline=False
    )

    embed.set_footer(
        text="WARDOGS RU • Русскоязычное сообщество"
    )

    await interaction.channel.send(embed=embed)

    await interaction.response.send_message(
        "✅ Правила опубликованы.",
        ephemeral=True
    )


bot.run(TOKEN)
