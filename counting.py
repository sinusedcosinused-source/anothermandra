import discord
from discord.ext import commands

COUNT_CHANNEL_ID = 1540457972457807953

# number -> response sent when someone hits it
FUNNY_NUMBERS = {
    80085: "80085",
    8008135: "8008135",
    42: "42",
    11037: "11037",
    1337: "1337 ",
    9001: "9001",
    21: "21",
    69: "69",
    67: "67",
}


class Counting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.channel.id != COUNT_CHANNEL_ID:
            return

        content = message.content.strip()
        if not content.isdigit():
            return

        number = int(content)
        if (number) in FUNNY_NUMBERS:
            await message.channel.send(FUNNY_NUMBERS[number])


async def setup(bot: commands.Bot):
    await bot.add_cog(Counting(bot))
