import discord
import os

from .path import get_path
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union


CHANNEL_ATTRIBUTE_NAMES = [
    "name",
    "id",
    "nsfw",
    "position",
    "type",
    "overwrites",
    "category_id",
    "permissions_synced",
    "default_auto_archive_duration",
    "default_thread_slowmode_delay",
    "slowmode_delay",
    "bitrate",
    "user_limit",
    "rtc_region",
    "video_quality_mode",
]

ROLE_ATTRIBUTE_NAMES = [
    "name",
    "id",
    "permissions",
    "colour",
    "hoist",
    "display_icon",
    "mentionable",
    "position",
]


def generate_unique_id() -> str:
    """Generates a unique id based off of the current timestamp

    Returns
    -------
    str
        The unique id
    """

    return hex(int(datetime.now().timestamp() * 1000 - datetime.fromisoformat("2020-01-01").timestamp() * 1000))[2:].upper()


class Backup:
    """
    A class used to represent a backup

    Attributes
    ----------
    _id: str
        The unique backup id
    channels: Optional[List[Dict]]
        An optional list of all guild channels in a backup
    rules_channel: Optional[int]
        Optional rules channel id of community guilds
    public_updates_channel: Optional[int]
        Optional updates channel id of community guilds
    roles: Optional[List[Dict]]
        An optional list of all guild roles in a backup
    """

    def __init__(
        self,
        _id: Optional[str] = None,
        channels: Optional[List[Dict]] = None,
        rules_channel: Optional[int] = None,
        public_updates_channel: Optional[int] = None,
        roles: Optional[List[Dict]] = None,
    ) -> None:
        self._id: str = _id or generate_unique_id()
        self.channels: Optional[List[Dict]] = channels
        self.rules_channel: Optional[int] = rules_channel
        self.public_updates_channel: Optional[int] = public_updates_channel
        self.roles: Optional[List[Dict]] = roles

    @property
    def id(self) -> str:
        return self._id

    @classmethod
    async def create(cls, guild: discord.Guild) -> "Backup":
        """Creates a backup of a guild

        Parameters
        ----------
        guild: discord.Guild
            The guild that you want to create a backup of

        Returns
        -------
        Backup
            The backup
        """

        roles = [
            await convert_guild_role_to_json(role)
            for role in guild.roles
            if not role.is_bot_managed()
        ]

        for i, role in enumerate(sorted(roles, key=lambda r: r.get("position"))):
            role.update({"position": i})

        return cls(
            channels=[
                convert_guild_channel_to_json(channel) for channel in guild.channels
            ],
            rules_channel=guild.rules_channel.id if guild.rules_channel else None,
            public_updates_channel=guild.public_updates_channel.id
            if guild.public_updates_channel
            else None,
            roles=roles,
        )

    def to_json(self) -> dict:
        """Converts self into a dict object"""

        return self.__dict__


class BackupChannel:
    def __init__(self, **kwargs) -> None:
        self.name = kwargs.get("name")
        self.id = kwargs.get("id")
        self.nsfw = kwargs.get("nsfw")
        self.position = kwargs.get("position")
        self.type = kwargs.get("type")
        self.overwrites = kwargs.get("overwrites")

        self.category_id = kwargs.get("category_id")
        self.permissions_synced = kwargs.get("permissions_synced")

        self.default_auto_archive_duration = kwargs.get("default_auto_archive_duration")
        self.default_thread_slowmode_delay = kwargs.get("default_thread_slowmode_delay")
        self.slowmode_delay = kwargs.get("slowmode_delay")

        self.bitrate = kwargs.get("bitrate")
        self.user_limit = kwargs.get("user_limit")
        self.rtc_region = kwargs.get("rtc_region")
        self.video_quality_mode = kwargs.get("video_quality_mode")

    def to_json(self) -> Dict:
        data = {
            "name": self.name,
            "id": self.id,
            "nsfw": self.nsfw,
            "position": self.position,
            "type": self.type,
            "overwrites": self.overwrites,
            "permissions_synced": self.permissions_synced,
        }

        if self.type in [0, 5, 10, 11, 12, 15]:
            data.update(
                {
                    "category_id": self.category_id,
                    "default_auto_archive_duration": self.default_auto_archive_duration,
                    "default_thread_slowmode_delay": self.default_thread_slowmode_delay,
                    "slowmode_delay": self.slowmode_delay,
                }
            )

        elif self.type in [2, 13]:
            data.update(
                {
                    "category_id": self.category_id,
                    "slowmode_delay": self.slowmode_delay,
                    "bitrate": self.bitrate,
                    "user_limit": self.user_limit,
                    "rtc_region": self.rtc_region,
                    "video_quality_mode": self.video_quality_mode,
                }
            )

        return data


def convert_permissionoverwrite_to_list(
    overwrites: Dict[
        Union[discord.Role,discord.Member, discord.Object],
        discord.PermissionOverwrite
    ],
) -> List[Dict]:
    """Converts a discord.PermissionOverwrite object to a list

    Parameters
    ----------
    overwrites: discord.PermissionOverwrite
        The overwrites which should be converted

    Returns
    -------
    list
        A list containing dicts for each overwrite
    """

    return [
        {
            "target_id": target.id,
            "overwrites": overwrite._values,
        }
        for target, overwrite in overwrites.items()
    ]


def extract_attributes_from_class(
    attributes: List[str],
    _class: Any,
    convert: Optional[Dict[str, Callable]] = None
) -> Dict:
    """Extracts the values of the attributes given in `attributes` from the `_class` object

    Parameters
    ----------
    attributes: List[str]
        The list of attribute names you want to extract
    _class: Any
        The class instance of which the attributes should be extracted
    convert: Dict[str, Callable]
        Allows to convert the attribute value to something else e.g. {"attribute1": lambda value: value + 1}

    Returns
    -------
    dict
        The attributes with their values
    """

    result = {}

    if _class is None:
        return result

    for attribute in dir(_class):
        if str(attribute) not in attributes:
            continue

        value = getattr(_class, attribute)

        if convert:
            attribute_converter = convert.get(attribute)

            if callable(attribute_converter):
                value = attribute_converter(value)

        result.update({attribute: value})

    return result


def convert_guild_channel_to_json(guild_channel: discord.abc.GuildChannel) -> Dict:
    return extract_attributes_from_class(
        attributes=CHANNEL_ATTRIBUTE_NAMES,
        _class=guild_channel,
        convert={
            "type": lambda type_value: type_value[1],
            "overwrites": lambda overwrites: convert_permissionoverwrite_to_list(
                overwrites
            ),
            "video_quality_mode": lambda video_quality_mode: video_quality_mode[1],
        },
    )


async def convert_guild_role_to_json(guild_role: discord.Role) -> Dict:
    raw_guild_role = extract_attributes_from_class(
        attributes=ROLE_ATTRIBUTE_NAMES,
        _class=guild_role,
        convert={
            "colour": lambda colour: list(colour.to_rgb()),
            "permissions": lambda permissions: permissions.value,
        },
    )

    # Poor implementation of image saving, but it works (somehow)
    if (dis_icon := raw_guild_role.get("display_icon")) is not None:
        if not os.path.exists(get_path("assets")):
            os.mkdir(get_path("assets"))

        with open(get_path(f"assets/{dis_icon.key}.png"), "wb") as role_image_file:
            role_image_file.write(await dis_icon.read())

        raw_guild_role.update({"display_icon": dis_icon.key})

    return raw_guild_role
