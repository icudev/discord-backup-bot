import discord
import logging
import json
import random
import string

from .path import get_path
from typing import Any, Callable, Dict, List, Optional, Union


BACKUP_ID_LENGTH = 6

assert BACKUP_ID_LENGTH > 1, "Backup ID length has to be greater than 1"

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

LETTERS = string.ascii_letters + "0123456789"


def generate_unique_id() -> str:
    """Generates a unique id

    Returns
    -------
    str
        The unique id
    """

    def generate_random_id() -> str:
        """Generates a random id

        Returns
        -------
        str
            The random id
        """

        return "".join(
            [
                random.choice(LETTERS)
                for _ in range(BACKUP_ID_LENGTH)
            ]
        )

    _id = generate_random_id()

    while BackupCache.v.get(_id):
        _id = generate_random_id()

    return _id


class BackupCache:
    """
    A class used to save all backups in cache

    Attributes
    ----------
    v: dict
        The value of the current cache
    old: dict
        A copy of `v` to look for changes
    """

    v: Dict = {}
    old: Dict = {}


class Backup:
    """
    A class used to represent a backup

    Attributes
    ----------
    _id: str
        The unique backup id
    channels: Optional[List[Dict]]
        An optional list of all guild channels in a backup
    """

    def __init__(
        self, _id: Optional[str] = None, channels: Optional[List[Dict]] = None
    ) -> None:
        self._id: str = _id or generate_unique_id()
        self.channels: Optional[List[Dict]] = channels

        if self._id == "0":
            return

        self.insert_self_to_cache()

    @property
    def id(self) -> str:
        return self._id

    @staticmethod
    def setup_cache() -> None:
        """Loads up the cache using data stored in a file"""

        with open(get_path("backup.json"), "r", encoding="utf-8") as backup_file_reader:
            BackupCache.v = json.load(backup_file_reader)
            BackupCache.old = BackupCache.v.copy()

        logging.info("Loaded file into cache")

    @staticmethod
    def write_to_file() -> bool:
        """Writes the cache into a file

        Returns
        -------
        bool
            Wether or not the cache was written into the file
        """

        if BackupCache.v == BackupCache.old:
            return False

        with open(get_path("backup.json"), "w", encoding="utf-8") as backup_file_writer:
            json.dump(BackupCache.v, backup_file_writer)
            BackupCache.old = BackupCache.v.copy()

        return True

    @classmethod
    def create(cls, guild: discord.Guild) -> "Backup":
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

        channels: List[Dict] = []

        for guild_channel in guild.channels:
            channel_info = extract_attributes_from_class(
                attributes=CHANNEL_ATTRIBUTE_NAMES,
                _class=guild_channel,
                convert={
                    "type": lambda type_value: type_value[1],
                    "overwrites": lambda overwrites: convert_permissionoverwrite_to_list(
                        overwrites
                    ),
                    "video_quality_mode": lambda video_quality_mode: video_quality_mode[
                        1
                    ],
                },
            )

            channels.append(channel_info)

        return cls(channels=channels)

    @classmethod
    def from_id(cls, _id: str) -> "Backup":
        """Loads a backup from cache with the given id

        Parameters
        ----------
        _id: str
            The id of the backup that you want to load

        Returns
        -------
        Backup
            The backup
        """

        if not BackupCache.v.get(_id):
            return cls(_id="0")

        return cls(**BackupCache.v.get(_id))

    def insert_self_to_cache(self) -> None:
        """Inserts self as a json object into the cache"""

        BackupCache.v[self.id] = self.to_json()

    def to_json(self) -> dict:
        """Converts self into a dict object"""

        return self.__dict__

    def delete(self) -> bool:
        """Deletes self from the cache

        Returns
        -------
        bool
            Wether or not the deletion was succesful
        """

        if not BackupCache.v.get(self.id):
            return False

        BackupCache.v.pop(self.id)

        logging.info(f'Deleted backup with id "{self.id}"')

        return True


class BackupChannel:
    def __init__(self, *args, **kwargs) -> None:
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
        Union[discord.Role, discord.Member, discord.Object], discord.PermissionOverwrite
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
    attributes: List[str], _class: Any, convert: Optional[Dict[str, Callable]] = None
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
        if attribute not in attributes:
            continue

        value = getattr(_class, attribute)

        if convert:
            attribute_converter = convert.get(attribute)

            if callable(attribute_converter):
                value = attribute_converter(value)

        result.update({attribute: value})

    return result
