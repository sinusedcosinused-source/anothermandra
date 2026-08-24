from random import choice
import re
import discord
from discord.ext import commands
from discord import app_commands

triggerwords = ["hell", "fuck", "bitch", "bastard", "nah"]
replacement_words = ["he'ww", "fwick", "bwitch", "bastawd", "nyahh"]
uwus = ["uwu", "owo", "~~", ":3"]

LOG_CHANNEL_ID = 1540709807370018887
ALLOWED_ROLE_ID = 1205591566836834424
ALLOWED_USER_ID = 411897831885111339

# Any Member with one of these permissions counts as a "mod" for uwulock
# purposes, on top of the specific role/user above.
MOD_PERMISSIONS = (
    "administrator",
    "manage_guild",
    "manage_messages",
    "manage_roles",
    "kick_members",
    "ban_members",
    "moderate_members",
)

URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')


def uwuify(text):
    urls = []

    def stash_url(match):
        urls.append(match.group(0))
        return f"\x00{len(urls) - 1}\x00"

    text = URL_PATTERN.sub(stash_url, text)

    text = re.sub(r'[rl]', 'w', text)
    text = re.sub(r'[RL]', 'W', text)
    text = re.sub(r'([.!?])', lambda m: m.group(1) + ' ' + choice(uwus), text)
    text = re.sub(r'n([aeiou])', r'ny\1', text)
    for trigger, replacement in zip(triggerwords, replacement_words):
        text = re.sub(r'\b' + re.escape(trigger) + r'\b', replacement, text, flags=re.IGNORECASE)
    text = text.rstrip() + ' ' + choice(uwus)

    for i, url in enumerate(urls):
        text = text.replace(f"\x00{i}\x00", url)

    return text


def is_allowed(interaction: discord.Interaction) -> bool:
    if interaction.user.id == ALLOWED_USER_ID:
        return True
    if isinstance(interaction.user, discord.Member):
        if any(role.id == ALLOWED_ROLE_ID for role in interaction.user.roles):
            return True
        # Anyone holding any conventional "mod" permission is treated as a
        # mod, so they don't need the specific role above.
        perms = interaction.user.guild_permissions
        if any(getattr(perms, perm, False) for perm in MOD_PERMISSIONS):
            return True
    return False


class Uwyfy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.locked: set[int] = set()
        self._webhook_cache: dict[int, discord.Webhook] = {}

    async def get_webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        if channel.id in self._webhook_cache:
            return self._webhook_cache[channel.id]
        webhooks = await channel.webhooks()
        webhook = discord.utils.get(webhooks, name="uwulock-hook")
        if webhook is None:
            webhook = await channel.create_webhook(name="uwulock-hook")
        self._webhook_cache[channel.id] = webhook
        return webhook

    async def log_action(self, action: str, mod: discord.Member, target: discord.Member):
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if log_channel is None:
            try:
                log_channel = await self.bot.fetch_channel(LOG_CHANNEL_ID)
            except discord.NotFound:
                print(f"Log channel {LOG_CHANNEL_ID} not found")
                return
            except discord.Forbidden:
                print(f"No permission to access log channel {LOG_CHANNEL_ID}")
                return

        embed = discord.Embed(
            title=f"UwuLock — {action}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Mod", value=f"{mod.display_name} (`{mod.id}`)", inline=True)
        embed.add_field(name="Target", value=f"{target.display_name} (`{target.id}`)", inline=True)
        await log_channel.send(embed=embed)

    async def _build_reply_prefix(self, message: discord.Message) -> str:
        """Webhooks can't create a real Discord reply reference, so we fake
        the look of one by quoting the message being replied to."""
        if not message.reference or not message.reference.message_id:
            return ""

        ref_msg = message.reference.resolved
        if ref_msg is None or isinstance(ref_msg, discord.DeletedReferencedMessage):
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return ""

        ref_author = ref_msg.author.display_name
        ref_content = ref_msg.content or "*attachment/embed*"
        ref_content = ref_content.replace("\n", " ")
        if len(ref_content) > 80:
            ref_content = ref_content[:77] + "..."

        jump = f" [↗]({ref_msg.jump_url})" if hasattr(ref_msg, "jump_url") else ""
        return f"> ↪️ **{ref_author}:** {ref_content}{jump}\n"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or not message.content:
            return
        if message.author.id not in self.locked:
            return

        try:
            webhook = await self.get_webhook(message.channel)
            reply_prefix = await self._build_reply_prefix(message)
            content = reply_prefix + uwuify(message.content)

            await message.delete()
            await webhook.send(
                content=content,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
            )
        except discord.Forbidden:
            pass

    @app_commands.command(name="uwulock", description="Abandon all hope ye who use this command")
    @app_commands.check(is_allowed)
    async def uwulock(self, interaction: discord.Interaction, member: discord.Member):
        if member.id in self.locked:
            await interaction.response.send_message(f"**{member.display_name}** is already uwulocked.", ephemeral=True)
            return

        self.locked.add(member.id)
        await interaction.response.send_message(f"Added **{member.display_name}** to uwulock.")
        await self.log_action("Locked", interaction.user, member)

    @app_commands.command(name="uwuunlock", description="release a user from uwulock")
    @app_commands.check(is_allowed)
    async def uwuunlock(self, interaction: discord.Interaction, member: discord.Member):
        if member.id not in self.locked:
            await interaction.response.send_message(f"**{member.display_name}** isn't uwulocked.", ephemeral=True)
            return

        if interaction.user.id == member.id:
            await interaction.response.send_message(
                "You can't unlock yourself — get another mod to do it.", ephemeral=True
            )
            return

        self.locked.discard(member.id)
        await interaction.response.send_message(f"Released **{member.display_name}** from uwulock.")
        await self.log_action("Unlocked", interaction.user, member)

    @uwulock.error
    @uwuunlock.error
    async def uwulock_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("Your mortal mind cannot fathom such a destructive spell", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Uwyfy(bot))
