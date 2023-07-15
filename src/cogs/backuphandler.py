import discord
import json
import logging

from discord import app_commands
from discord.ext.commands import Cog
from utils import *
from typing import Dict, List, Optional


CHANNEL_TYPES = {
    "0": discord.ChannelType.text,
    "2": discord.ChannelType.voice,
    "4": discord.ChannelType.category,
    "5": discord.ChannelType.news,
    "13": discord.ChannelType.stage_voice,
    "15": discord.ChannelType.forum,
}


async def check_dm_and_user_permissions(interaction: discord.Interaction) -> bool:
    """
    Checks if the command was executed in a dm channel and if the user
    has enough permissions to use the command

    Parameters
    ----------
    interaction: discord.Interaction
        The interaction that should be checked

    Returns
    -------
    bool
        Wether or not the check was succesful
    """

    if not interaction.guild:
        await interaction.followup.send(
            f"This command can only be used in a server", ephemeral=True
        )
        return False

    if not interaction.user.guild_permissions.administrator:
        await interaction.followup.send(
            f"You do not have the required permissions to use this command",
            ephemeral=True,
        )
        return False

    return True


class BackupHandler(Cog):
    backup = app_commands.Group(name="backup", description="Base Backup command")

    def __init__(self, bot) -> None:
        self.bot = bot

        self.reference_channels = {}

    async def cog_load(self) -> None:
        with open(get_path("ref_channels.json"), "r") as ref_channels_file:
            self.reference_channels = json.load(ref_channels_file)

    def write_references_to_file(self) -> None:
        with open(get_path("ref_channels.json"), "w") as ref_channels_file:
            json.dump(self.reference_channels, ref_channels_file)

        logging.info("Saved references to file")

    @backup.command(name="create", description="Create a backup of the server")
    @app_commands.guild_only()  # Unnecessary since this decorator doesn't work on subcommands, but I'll leave it
    async def backup_create_callback(self, interaction: discord.Interaction) -> None:
        """Callback for the `/backup create` slash command"""

        await interaction.response.defer()

        if not await check_dm_and_user_permissions(interaction):
            return

        guild_backup = Backup.create(interaction.guild)

        logging.info(
            f'Created backup for server "{interaction.guild.name}" with ID "{guild_backup.id}"'
        )

        await interaction.followup.send(f'Backup created. ID: "{guild_backup.id}"')

    @backup.command(name="load", description="Load a backup of the server")
    @app_commands.describe(
        backup_id="The backup id",
        delete_all_guild_channels="Delete all guild channels before loading in the backup",
    )
    @app_commands.guild_only()  # Unnecessary since this decorator doesn't work on subcommands, but I'll leave it
    async def backup_load_callback(
        self,
        interaction: discord.Interaction,
        backup_id: str,
        delete_all_guild_channels: bool = False,
    ) -> None:
        """Callback for the `/backup load` slash command"""

        await interaction.response.defer()

        if not await check_dm_and_user_permissions(interaction):
            return

        guild_backup = Backup.from_id(backup_id)

        if guild_backup.id == "0":
            await interaction.followup.send("I couldn't find a backup with that id")
            return

        if not self.reference_channels.get(backup_id):
            self.reference_channels[backup_id] = {}

        references = self.reference_channels.get(backup_id)

        guild: discord.Guild = interaction.guild

        if delete_all_guild_channels:
            for guild_channel in guild.channels:
                try:
                    if references.get(str(guild_channel.id)):
                        del references[str(guild_channel.id)]

                    await guild_channel.delete()

                except Exception as exception:
                    await interaction.followup.send(
                        f"I couldn't delete <#{guild_channel.id}>.\n```{exception}```"
                    )
                    return

        all_backup_channels = []

        # Data on how to edit which channel
        channel_data = []
        category_data = []

        for guild_backup in guild_backup.channels:
            backup_channel = BackupChannel(**guild_backup)
            current_channel = guild.get_channel(backup_channel.id)

            backup_channel_data = backup_channel.to_json()
            current_channel_data = extract_attributes_from_class(
                attributes=CHANNEL_ATTRIBUTE_NAMES,
                _class=current_channel,
                convert={
                    "type": lambda object_type: object_type[1],
                    "overwrites": lambda overwrites: convert_permissionoverwrite_to_list(
                        overwrites=overwrites
                    ),
                    "video_quality_mode": lambda video_quality_mode: video_quality_mode[
                        1
                    ],
                },
            )

            _action = "create"

            if current_channel:
                _action = "edit"

            compare_data = {
                "current_channel": current_channel_data,
                "backup_channel": backup_channel_data,
                "action": _action,
            }

            if backup_channel.type == 4:
                category_data.append(compare_data)

            else:
                channel_data.append(compare_data)

        async def handle_channels(data: List[Dict]) -> bool:
            """Edits or creates new channels based on the data provided

            Parameters
            ----------
            data: list[dict]
                A list of dict containing which channel to edit or create

            Returns
            -------
            bool
                Wether or not all actions were succesful
            """

            for compare_channel_data in sorted(
                data, key=lambda _dict: _dict.get("backup_channel").get("position")
            ):
                action = compare_channel_data.get("action")

                current_channel = compare_channel_data.get("current_channel")
                backup_channel = compare_channel_data.get("backup_channel")

                reference_category: Optional[discord.CategoryChannel] = None

                backup_category_id = backup_channel.get("category_id")
                reference_category_id = references.get(
                    str(backup_category_id), backup_category_id
                )

                if reference_category_id:
                    reference_category = guild.get_channel(reference_category_id)

                backup_channel_id = backup_channel.get("id")
                reference_channel_id = references.get(
                    str(backup_channel_id), backup_channel_id
                )

                # The channel to perform the action on
                reference_channel: Optional[
                    discord.abc.GuildChannel
                ] = guild.get_channel(reference_channel_id)

                if reference_channel:
                    current_channel = extract_attributes_from_class(
                        attributes=CHANNEL_ATTRIBUTE_NAMES,
                        _class=reference_channel,
                        convert={
                            "type": lambda object_type: object_type[1],
                            "overwrites": lambda overwrites: convert_permissionoverwrite_to_list(
                                overwrites=overwrites
                            ),
                            "video_quality_mode": lambda video_quality_mode: video_quality_mode[
                                1
                            ],
                        },
                    )

                    all_backup_channels.append(reference_channel.id)

                # Convert the custom overwrite object into an object readable by discord
                overwrites = {}

                for overwrite_object in backup_channel.get("overwrites"):
                    target_id = overwrite_object.get("target_id")
                    target_object = guild.get_member(target_id) or guild.get_role(
                        target_id
                    )

                    if not target_object:
                        continue

                    overwrites.update(
                        {
                            target_object: discord.PermissionOverwrite(
                                **overwrite_object.get("overwrites")
                            )
                        }
                    )

                def pop_if_available(key: str) -> None:
                    """Pops keys out if the current and the backup channel as the keys cannot
                    be used to edit or create a channel

                    Parameters
                    ----------
                    key: str
                        The key to pop
                    """

                    if key in backup_channel.keys():
                        del backup_channel[key]

                    if key in current_channel.keys():
                        del current_channel[key]

                pop_if_available("category_id")

                if action == "edit" or reference_channel:
                    pop_if_available("type")

                    if sorted(current_channel.items(), key=lambda x: x[0]) != sorted(
                        backup_channel.items(), key=lambda x: x[0]
                    ):
                        # Pop the overwrites over here because they're used to compare the
                        # permissions of both channels
                        pop_if_available("overwrites")

                        try:
                            await reference_channel.edit(
                                **backup_channel,
                                category=reference_category,
                                overwrites=overwrites,
                                reason=f"Backup loaded by {interaction.user} ( {interaction.user.id} )",
                            )

                        except Exception as channel_edit_exception:
                            logging.error(
                                f'Error when editing channel "{reference_channel.name}": {channel_edit_exception}'
                            )

                            return False

                elif action == "create":
                    pop_if_available("overwrites")

                    try:
                        # Trying to create a channel but if certain channel types cannot be created the bot will create either a
                        # normal text channel or a normal voice channel
                        new_channel = await guild._create_channel(
                            **backup_channel,
                            category=reference_category,
                            channel_type=CHANNEL_TYPES.get(
                                str(backup_channel.get("type"))
                            ),
                            overwrites=overwrites,
                            reason=f"Backup loaded by {interaction.user} ( {interaction.user.id} )",
                        )

                    except discord.HTTPException:
                        #                                List of types of channels which inherit from the normal
                        #                                text channel
                        if backup_channel.get("type") in [0, 5, 10, 11, 12, 15]:
                            channel_type = 0  # Text Channel

                        else:
                            channel_type = 2  # Voice Channel

                            # Stage channels have a default user_limit of 10,000. Normal voice chats can only have a
                            # set limit of 99 so we remove the limit altogether
                            backup_channel.update({"user_limit": None})

                        new_channel = await guild._create_channel(
                            **backup_channel,
                            category=reference_category,
                            channel_type=CHANNEL_TYPES.get(str(channel_type)),
                            overwrites=overwrites,
                            reason=f"Backup loaded by {interaction.user} ( {interaction.user.id} )",
                        )

                    all_backup_channels.append(int(new_channel.get("id")))

                    # Reference the old channel id to the newly create channel id because the old channel
                    # is no longer available
                    self.reference_channels.get(backup_id).update(
                        {str(backup_channel.get("id")): int(new_channel.get("id"))}
                    )

            return True

        # Handling categories before normal channels because of positioning reasons
        category_backup_success = await handle_channels(category_data)
        channels_backup_success = await handle_channels(channel_data)

        self.write_references_to_file()

        overall_success = category_backup_success and channels_backup_success

        if overall_success:
            for guild_channel in guild.channels:
                if guild_channel.id not in all_backup_channels:
                    if interaction.channel_id == guild_channel.id:
                        delete_all_guild_channels = True

                    await guild_channel.delete(
                        reason=f"Backup loaded by {interaction.user} ( {interaction.user.id} )"
                    )

        message = "Loaded Backup." if overall_success else "Couldn't load Backup."

        # Since all channels were deleted before loading the backup, the original
        # interaction message was deleted, so we have to search for a channel to
        # send the confirmation that the backup was successful or not
        if delete_all_guild_channels:
            for guild_text_channel in guild.text_channels:
                try:
                    await guild_text_channel.send(
                        f"{interaction.user.mention} {message}"
                    )
                    break

                except discord.Forbidden:
                    continue

            return

        await interaction.followup.send(message)

    @backup.command(name="delete", description="Delete a backup")
    @app_commands.describe(backup_id="The backup id to delete")
    @app_commands.guild_only()  # Unnecessary since this decorator doesn't work on subcommands, but I'll leave it
    async def backup_delete_callback(
        self, interaction: discord.Interaction, backup_id: str
    ) -> None:
        """Callback for the `/backup delete` slash command"""

        await interaction.response.defer()

        if not await check_dm_and_user_permissions(interaction):
            return

        guild_backup = Backup.from_id(backup_id)

        if guild_backup.id == "0":
            await interaction.followup.send(
                f"I couldn't find a backup with that id", ephemeral=True
            )
            return

        deleted = guild_backup.delete()

        # Delete all references for that backup
        if self.reference_channels.get(backup_id):
            del self.reference_channels[backup_id]
            self.write_references_to_file()

        message = f'Succesfully deleted backup with id "{backup_id}"'

        if not deleted:
            message = f'I couldn\'t delete backup with id "{backup_id}"'

        await interaction.followup.send(message, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BackupHandler(bot))
