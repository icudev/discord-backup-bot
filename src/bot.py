import asyncio
import discord
import logging
import os

from discord.ext import commands
from dotenv import load_dotenv
from utils import Backup, get_path

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="[ %(levelname)s ] %(name)s: %(message)s"
)


BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# List of all cogs that will be loaded on startup
EXTENSIONS = [
    "cogs.backuphandler",
]

# Turn this on if the bot takes a long time to start
# Do *NOT* turn this on on the first run
DISABLE_COMMAND_SYNC = False

FILES_NEEDED = {"backup.json": "{}", "ref_channels.json": "{}"}


class BackupBot(commands.Bot):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

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
        self.setup_files()
        await self.load_extensions()

        # Loads the backup cache
        Backup.setup_cache()

        if not DISABLE_COMMAND_SYNC:
            logging.info("Syncing command tree...")

            # Syncs the command tree and registers the slash commands
            await self.tree.sync()

            logging.info("Synced command tree.")

    async def on_ready(self) -> None:
        logging.info(f"Logged in as {self.user}")

    async def close(self) -> None:
        Backup.write_to_file()

    @staticmethod
    async def save_cache_loop() -> None:
        """Loop to write the cache into a file"""

        while True:
            # Tries to write the cache into a file every five seconds
            await asyncio.sleep(5)

            if Backup.write_to_file():
                logging.info("Saved backups to file")

    @staticmethod
    def setup_files() -> None:
        """Creates necessary files for the bot to run if not already existing"""

        for file_name, file_contents in FILES_NEEDED.items():
            if not os.path.exists(get_path(file_name)):
                with open(get_path(file_name), "x") as new_file:
                    new_file.write(file_contents)

                logging.info(f"Created {file_name}")


if __name__ == "__main__":
    bot = BackupBot(
        command_prefix=[], help_command=None, intents=discord.Intents.default()
    )

    bot.run(token=BOT_TOKEN, log_handler=None)
