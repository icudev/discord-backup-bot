import discord
import logging
import os

from discord.ext import commands
from dotenv import load_dotenv
from utils import Database, get_path

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="[ %(levelname)s ] %(name)s: %(message)s"
)

logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("discord").setLevel(logging.INFO)


BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# List of all cogs that will be loaded on startup
EXTENSIONS = [
    "cogs.backuphandler",
]

# Turn this on if the bot takes a long time to start
# Do *NOT* turn this on on the first run
DISABLE_COMMAND_SYNC = False


class BackupBot(commands.Bot):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.db = Database()

    async def load_extensions(self) -> None:
        """Loads all extensions listed in `EXTENSIONS`"""

        for extension in set(EXTENSIONS):
            try:
                await self.load_extension(extension)
                logging.info(f'Loaded extension "{extension}"')

            except commands.errors.NoEntryPointError:
                logging.error(f'Extension "{extension}" does not have a setup function')

            except commands.errors.ExtensionNotFound:
                logging.error(f'Extension "{extension}" does not exist')

            except Exception as extension_load_exception:
                logging.error(
                    f'There was an error when loading extension "{extension}": {extension_load_exception}'
                )

    async def setup_hook(self) -> None:
        await self.load_extensions()

        if not DISABLE_COMMAND_SYNC:
            logging.info("Syncing command tree...")

            await self.tree.sync()

            logging.info("Synced command tree.")

    async def on_ready(self) -> None:
        logging.info(f"Logged in as {self.user}")


if __name__ == "__main__":
    bot = BackupBot(
        command_prefix=[], help_command=None, intents=discord.Intents.default()
    )

    bot.run(token=BOT_TOKEN, log_handler=None)
