import discord
import logging
import os

from discord import app_commands
from discord.ext.commands import Cog
from utils import (
    Backup,
    BackupChannel,
    convert_guild_channel_to_json,
    convert_guild_role_to_json,
    get_path,
)
from typing import Callable, Dict, List, Optional, Union, Tuple


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
            "This command can only be used in a server", ephemeral=True
        )
        return False

    if not interaction.user.guild_permissions.administrator:
        await interaction.followup.send(
            "You do not have the required permissions to use this command",
            ephemeral=True,
        )
        return False

    return True


class BackupHandler(Cog):
    backup = app_commands.Group(name="backup", description="Base Backup command")

    def __init__(self, bot) -> None:
        self.bot = bot

    @backup.command(name="create", description="Create a backup of the server")
    async def backup_create_callback(self, interaction: discord.Interaction) -> None:
        """Callback for the `/backup create` slash command"""

        await interaction.response.defer()

        if not await check_dm_and_user_permissions(interaction):
            return

        guild_backup = await Backup.create(interaction.guild)

        self.bot.db.insert_backup(guild_backup)

        logging.info(
            f'Created backup for server "{interaction.guild.name}" with ID "{guild_backup.id}"'
        )

        await interaction.followup.send(f'Backup created. ID: "{guild_backup.id}"')

    @backup.command(name="load", description="Load a backup of the server")
    @app_commands.describe(
        backup_id="The backup id",
        clear_guild="Clears the whole server (roles, channels) before loading a backup",
    )
    async def backup_load_callback(
        self,
        interaction: discord.Interaction,
        backup_id: str,
        clear_guild: bool = False,
    ) -> None:
        """Callback for the `/backup load` slash command"""

        await interaction.response.defer()

        if not await check_dm_and_user_permissions(interaction):
            return

        guild_backup = self.bot.db.get_backup(backup_id)

        if guild_backup is None:
            await interaction.followup.send("I couldn't find a backup with that id")
            return

        guild: discord.Guild = interaction.guild

        get_reference = lambda old: self.bot.db.get_reference_id(guild_backup.id, guild.id, old)
        set_reference = lambda old, new: self.bot.db.set_reference_id(guild_backup.id, guild.id, old, new)
        del_reference = lambda old: self.bot.db.del_reference_id(guild_backup.id, guild.id, old)

        rules_id = None
        updates_id = None

        # Current guild is a community server
        if guild.rules_channel:
            rules_id = guild.rules_channel.id
            updates_id = guild.public_updates_channel.id

            # If the server in which the backup was made was also a community server
            # we have to reference the old rules and updates channel to the new ones
            if guild_backup.rules_channel:
                set_reference(guild_backup.rules_channel, rules_id)
                set_reference(guild_backup.public_updates_channel, updates_id)

        async def delete_all(
            iterable: List[Union[discord.Role, discord.abc.GuildChannel]],
            checks: Optional[List[Callable]] = None,
        ) -> Tuple[
            Optional[Union[discord.Role, discord.abc.GuildChannel]],
            Optional[str]
        ]:
            """Deletes all items in `iterable`

            specifically made only to delete roles and channel so don't use it for
            anything other

            Parameters
            ----------
            iterable: List[Union[discord.Role, discord.abc.GuildChannel]]
                A list containing all roles / channels to delete
            checks: Optional[List[Callable]]
                Optional checks to exclude some roles / channels from deletion

            Returns
            -------
            Tuple[Optional[Union[discord.Role, discord.abc.GuildChannel]], Optional[str]]
                Only returns non-None items when something went wrong
            """

            for item in iterable:
                if item.id in [
                    rules_id,
                    updates_id,
                ]:  # Item has the id of a non-deleteable channel
                    continue

                if checks:
                    if not all(
                        [callback(item) for callback in checks if callable(callback)]
                    ):
                        continue

                try:
                    del_reference(item.id)

                    await item.delete(
                        reason=f"Backup loaded by {interaction.user} ( {interaction.user.id} )"
                    )

                except Exception as exception:
                    return item, exception

            return None, None

        if clear_guild:
            base_response = "I couldn't delete <{}{}>.\n```{}```"

            role, role_exception = await delete_all(
                iterable=guild.roles,
                checks=[
                    lambda _role: _role.id != guild.id,
                    lambda _role: not _role.is_bot_managed(),
                    lambda _role: _role.is_assignable(),
                    lambda _role: not _role.is_integration(),
                ],
            )

            if role:
                await interaction.followup.send(
                    base_response.format("@&", role.id, role_exception)
                )
                return

            channel, channel_exception = await delete_all(guild.channels)

            if channel:
                await interaction.followup.send(
                    base_response.format("#", channel.id, channel_exception)
                )
                return

        all_used_roles: List[int] = []
        guild_roles_positions: Dict[discord.Role, int] = {}

        for backup_role_data in sorted(
            guild_backup.roles,
            key=lambda _dict: _dict.get("position")
        ):
            role_position = backup_role_data.get("position")

            backup_role = backup_role_data.copy()

            if role_position == 0:  # everyone role
                current_role = guild.get_role(guild.id)
                set_reference(backup_role_data.get("id"), guild.id)

            else:
                current_role = guild.get_role(get_reference(backup_role_data.get("id")))

            raw_current_role = await convert_guild_role_to_json(current_role)

            if current_role:
                # The current role is the bot role of self, which we cant edit
                if all(
                    [
                        current_role.is_bot_managed(),
                        current_role.members[0].id == self.bot.user.id
                        if len(current_role.members) > 0
                        else False,
                    ]
                ):
                    continue
            
            del_display_icon = False

            if "ROLE_ICONS" in guild.features:
                if (dis_icon_key := backup_role.get("display_icon")) is not None:
                    if not os.path.exists(get_path(f"assets/{dis_icon_key}.png")):
                        del_display_icon = True

                    else:
                        with open(
                            get_path(f"assets/{dis_icon_key}.png"), "b"
                        ) as role_icon:
                            backup_role.update({"display_icon": role_icon.read()})
                        
                else:
                    del_display_icon = True

            else:
                del_display_icon = True

            if del_display_icon:
                if backup_role.get("display_icon", False) is not False:
                    del backup_role["display_icon"]
                    
                if raw_current_role.get("display_role", False) is not False:
                    del raw_current_role["display_icon"]

            # There is no current role -> We have to create a new one
            if not current_role:
                role_id = backup_role_data.get("id")

                del backup_role["id"]
                del backup_role["position"]

                backup_role.update(
                    {
                        "permissions": discord.Permissions(
                            permissions=backup_role_data.get("permissions")
                        ),
                        "colour": discord.Colour.from_rgb(
                            **{
                                "rgb"[i]: backup_role_data.get("colour")[i]
                                for i in range(3)
                            }
                        ),
                    }
                )

                logging.debug(f"ROLE CREATE: {backup_role}")

                role = await guild.create_role(
                    **backup_role,
                    reason=f"Backup loaded by {interaction.user} ( {interaction.user.id} )",
                )

                guild_roles_positions.update({role: role_position})

                set_reference(role_id, role.id)
                all_used_roles.append(role.id)

            else:
                all_used_roles.append(current_role.id)

                del backup_role["id"]
                del raw_current_role["id"]

                if backup_role == raw_current_role:
                    continue

                backup_role.update(
                    {
                        "permissions": discord.Permissions(
                            permissions=backup_role_data.get("permissions")
                        ),
                        "colour": discord.Colour.from_rgb(
                            **{
                                "rgb"[i]: backup_role_data.get("colour")[i]
                                for i in range(3)
                            }
                        ),
                    }
                )

                if current_role.id == guild.id:
                    del backup_role["position"]
                    del raw_current_role["position"]

                logging.debug(f"ROLE EDIT: {backup_role}")

                try:
                    await current_role.edit(**backup_role)

                    guild_roles_positions.update({current_role: role_position})
                
                except discord.HTTPException:
                    logging.debug("EXCEPTION")
                    continue

        # For some reason the bot cannot edit the positions of roles, so I left this out
        #
        # await guild.edit_role_positions(
        #    positions=guild_roles_positions,
        #    reason=f"Backup loaded by {interaction.user} ( {interaction.user.id} )",
        # )

        all_backup_channels = []

        # Data on how to edit which channel
        channel_data = []
        category_data = []

        for backup_channel_data in guild_backup.channels:
            backup_channel = BackupChannel(**backup_channel_data)
            current_channel = guild.get_channel(backup_channel.id)

            current_channel_data = convert_guild_channel_to_json(current_channel)

            _action = "create"

            if current_channel:
                _action = "edit"

            compare_data = {
                "current_channel": current_channel_data.copy(),
                "backup_channel": backup_channel_data.copy(),
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
                reference_category_id = get_reference(backup_category_id)

                if reference_category_id:
                    reference_category = guild.get_channel(reference_category_id)

                backup_channel_id = backup_channel.get("id")
                reference_channel_id = get_reference(backup_channel_id)

                # The channel to perform the action on
                reference_channel = guild.get_channel(reference_channel_id)

                if reference_channel:
                    current_channel = convert_guild_channel_to_json(reference_channel)

                    all_backup_channels.append(reference_channel.id)

                # Convert the custom overwrite object into an object readable by discord
                overwrites = {}

                for overwrite_object in backup_channel.get("overwrites"):
                    target_id = overwrite_object.get("target_id")
                    target_id = get_reference(target_id)

                    target_object = guild.get_member(target_id) or \
                                    guild.get_role(target_id)

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

                if current_channel.get("type") == 4:
                    pop_if_available("category_id")
                
                else:
                    backup_channel.update({"category_id": get_reference(backup_channel.get("category_id"))})

                if action == "edit" or reference_channel:
                    if (
                        backup_channel.get("type") == 13
                        and reference_channel.type[1] == 2
                    ):
                        backup_channel.update({"user_limit": 0})

                    pop_if_available("id")
                    pop_if_available("type")

                    if sorted(
                        current_channel.items(),
                        key=lambda x: x[0]
                    ) != sorted(
                        backup_channel.items(),
                        key=lambda x: x[0]
                    ):
                        # Pop the overwrites over here because they're used to compare the
                        # permissions of both channels
                        pop_if_available("overwrites")

                        if not overwrites:
                            if sorted(
                                current_channel.items(),
                                key=lambda x: x[0]
                            ) == sorted(
                                backup_channel.items(),
                                key=lambda x: x[0]
                            ):
                                continue
                        
                        logging.debug(f"CHANNEL EDIT: {sorted(backup_channel.items(), key=lambda x: x[0])}")

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

                    logging.debug(f"CHANNEL CREATE: {backup_channel}")

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

                        elif backup_channel.get("type") in [3, 13]:
                            channel_type = 2  # Voice Channel

                            # Stage channels have a default user_limit of 10,000. Normal voice chats can only have a
                            # set limit of 99 so we remove the limit altogether
                            backup_channel.update({"user_limit": 0})

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
                    set_reference(int(backup_channel.get("id")), int(new_channel.get("id")))

            return True

        # Handling categories before normal channels because of positioning reasons
        category_backup_success = await handle_channels(category_data)
        channels_backup_success = await handle_channels(channel_data)

        overall_success = category_backup_success and channels_backup_success

        await delete_all(
            guild.roles,
            checks=[
                lambda _role: _role.id not in all_used_roles,
                lambda _role: _role.id != guild.id,
            ],
        )

        if overall_success:
            await delete_all(
                guild.channels,
                checks=[lambda _channel: _channel.id not in all_backup_channels],
            )

        message = "Loaded Backup." if overall_success else "Couldn't load Backup."

        # If the channel in which the `backup load` command was executed
        # is no longer available, we have to search for a channel in which
        # we send the confirmation wether or not the load was successful
        if interaction.channel not in guild.channels:
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
    async def backup_delete_callback(
        self, interaction: discord.Interaction, backup_id: str
    ) -> None:
        """Callback for the `/backup delete` slash command"""

        await interaction.response.defer()

        if not await check_dm_and_user_permissions(interaction):
            return

        guild_backup = self.bot.db.get_backup(backup_id)

        if guild_backup.id is None:
            await interaction.followup.send(
                f"I couldn't find a backup with that id",
                ephemeral=True
            )
            return

        self.bot.db.delete_backup(backup_id)
        self.bot.db.del_references_of_backup(backup_id)

        await interaction.followup.send(
            f'Successfully deleted backup with id "{backup_id}"',
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(BackupHandler(bot))
