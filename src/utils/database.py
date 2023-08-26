import json
import os
import sqlite3

from .backup import CHANNEL_ATTRIBUTE_NAMES, ROLE_ATTRIBUTE_NAMES, Backup
from .path import get_path
from typing import Optional


class Database:
    def __init__(self) -> None:
        setup = False

        if not os.path.exists(get_path("database.db")):
            with open(get_path("database.db"), "w"):
                setup = True
                pass

        self._conn: sqlite3.Connection = sqlite3.connect(
            database=get_path("database.db"),
            check_same_thread=False
        )

        if setup:
            self._setup()
    
    def _get_cursor(self) -> sqlite3.Cursor:
        return self._conn.cursor()
    
    def _setup(self) -> None:
        cursor = self._get_cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reference_ids (
                old_id INTEGER NOT NULL,
                new_id INTEGER NOT NULL,
                backup_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL
            );
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX ref_index
            ON reference_ids
            (old_id, backup_id);
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backups (
                id VARCHAR(10) PRIMARY KEY,
                guild_channels TEXT NOT NULL,
                guild_roles TEXT NOT NULL,
                guild_rules_channel INTEGER NULL,
                guild_public_updates_channel INTEGER NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_channels (
                id INTEGER NOT NULL,
                backup_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                nsfw INTEGER NOT NULL,
                position INTEGER NOT NULL,
                type INTEGER NOT NULL,
                overwrites TEXT NOT NULL,
                permissions_synced INTEGER NOT NULL,
                category_id INTEGER NULL,
                default_auto_archive_duration INTEGER NULL,
                default_thread_slowmode_delay INTEGER NULL,
                slowmode_delay INTEGER NULL,
                bitrate INTEGER NULL,
                user_limit INTEGER NULL,
                rtc_region TEXT NULL,
                video_quality_mode INTEGER NULL
            );
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX channel_index
            ON guild_channels
            (id, backup_id);
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_roles (
                id INTEGER NOT NULL,
                backup_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                permissions INTEGER NOT NULL,
                colour TEXT NULL,
                hoist INTEGER NOT NULL,
                display_icon TEXT NULL,
                mentionable INTEGER NOT NULL,
                position INTEGER NOT NULL
            );
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX roles_index
            ON guild_roles
            (id, backup_id);
        """)

        self._conn.commit()

        cursor.close()
    
    def insert_backup(self, backup: Backup) -> None:
        cursor = self._get_cursor()

        cursor.execute("""
                INSERT INTO backups
                VALUES (?, ?, ?, ?, ?);
            """,
            (
                backup.id,
                json.dumps([c.get("id") for c in backup.channels]),
                json.dumps([r.get("id") for r in backup.roles]),
                backup.rules_channel,
                backup.public_updates_channel
            )
        )

        for channel in backup.channels:
            channel.update({
                "overwrites": json.dumps(channel.get("overwrites"))
            })

            cursor.execute(f"""
                    INSERT INTO guild_channels
                    (backup_id, {', '.join(channel.keys())})
                    VALUES ({', '.join(['?' for _ in range(len(channel.keys()) + 1)])});
                """,
                [backup.id, *list(channel.values())]
            )

        for role in backup.roles:
            role.update({
                "colour": json.dumps(role.get("colour"))
            })

            cursor.execute(f"""
                    INSERT INTO guild_roles
                    (backup_id, {', '.join(role.keys())})
                    VALUES ({', '.join(['?' for _ in range(len(role.keys()) + 1)])});
                """,
                [backup.id, *list(role.values())]
            )

        self._conn.commit()

        cursor.close()
    
    def get_backup(self, backup_id: str) -> Optional[Backup]:
        cursor = self._get_cursor()

        cursor.execute("""
                SELECT * FROM backups
                WHERE id = ?;
            """,
            [backup_id,]
        )

        if result := cursor.fetchone():
            channels = []
            roles = []

            channel_ids = json.loads(result[1])
            role_ids = json.loads(result[2])

            for c_id in channel_ids:
                cursor.execute(f"""
                        SELECT {', '.join(CHANNEL_ATTRIBUTE_NAMES)} 
                        FROM guild_channels
                        WHERE id = ? AND backup_id = ?
                    """,
                    [c_id, backup_id]
                )

                if channel_data := cursor.fetchone():
                    channel = {}

                    attributes = [
                        "name",
                        "id",
                        "nsfw",
                        "position",
                        "type",
                        "overwrites",
                        "permissions_synced"
                    ]

                    if channel_data[4] in [0, 5, 10, 11, 12, 15]:
                        attributes.extend([
                            "category_id",
                            "default_auto_archive_duration",
                            "default_thread_slowmode_delay",
                            "slowmode_delay"
                        ])
                    
                    elif channel_data[4] in [2, 13]:
                        attributes.extend([
                            "category_id",
                            "bitrate",
                            "user_limit",
                            "rtc_region",
                            "video_quality_mode",
                            "slowmode_delay"
                        ])

                    for i, value in enumerate(attributes):
                        if value in ["overwrites",]:
                            channel.update({value: json.loads(channel_data[CHANNEL_ATTRIBUTE_NAMES.index(value)])})
                        
                        else:
                            channel.update({value: channel_data[CHANNEL_ATTRIBUTE_NAMES.index(value)]})
                    
                    channels.append(channel)
            
            for r_id in role_ids:
                cursor.execute(f"""
                        SELECT {', '.join(ROLE_ATTRIBUTE_NAMES)} 
                        FROM guild_roles
                        WHERE id = ? AND backup_id = ?
                    """,
                    [r_id, backup_id]
                )

                if role_data := cursor.fetchone():
                    role = {}

                    for i, value in enumerate(ROLE_ATTRIBUTE_NAMES):
                        if value in ["colour", ]:
                            role.update({value: json.loads(role_data[i])})
                        
                        else:
                            role.update({value: role_data[i]})
                    
                    roles.append(role)
            
            cursor.close()
            
            return Backup(
                backup_id,
                channels=channels,
                roles=roles,
                rules_channel=result[3],
                public_updates_channel=result[4]
            )
    
    def delete_backup(self, backup_id: str) -> None:
        cursor = self._get_cursor()

        cursor.execute("""
                DELETE FROM backups
                WHERE id = ?
            """,
            [backup_id,]
        )

        cursor.close()
    
    def get_reference_id(self, backup_id: str, guild_id: int, reference_id: int) -> int:
        cursor = self._get_cursor()

        cursor.execute("""
                SELECT new_id FROM reference_ids
                where backup_id = ? AND old_id = ? AND guild_id = ?
            """,
            [backup_id, reference_id, guild_id]
        )

        ref = reference_id

        if result := cursor.fetchone():
            ref = result[0]
        
        cursor.close()

        return ref
    
    def set_reference_id(self, backup_id: str, guild_id: int, old_id: int, new_id: int) -> None:
        if old_id == new_id:
            return

        cursor = self._get_cursor()

        cursor.execute("""
                SELECT * FROM reference_ids
                WHERE backup_id = ? AND old_id = ? AND guild_id = ?
            """,
            [backup_id, old_id, guild_id]
        )

        if cursor.fetchone():
            cursor.execute("""
                    UPDATE reference_ids
                    SET old_id = ?, new_id = ?
                    WHERE backup_id = ? AND old_id = ? AND guild_id = ?
                """,
                [old_id, new_id, backup_id, old_id, guild_id]
            )
        
        else:
            cursor.execute("""
                    INSERT INTO reference_ids
                    VALUES (?, ?, ?, ?)
                """,
                [old_id, new_id, backup_id, guild_id]
            )
        
        self._conn.commit()

        cursor.close()
    
    def del_reference_id(self, backup_id: str, guild_id: int, old_id: int) -> None:
        cursor = self._get_cursor()

        cursor.execute("""
                SELECT * FROM reference_ids
                WHERE backup_id = ? AND old_id = ? AND guild_id = ?
            """,
            [backup_id, old_id, guild_id]
        )

        if cursor.fetchone():
            cursor.execute("""
                    DELETE FROM reference_ids
                    WHERE backup_id = ? AND old_id = ? AND guild_id = ?
                """,
                [backup_id, old_id, guild_id]
            )
        
        self._conn.commit()

        cursor.close()
    
    def del_references_of_backup(self, backup_id: str) -> None:
        cursor = self._get_cursor()

        cursor.execute("""
                SELECT * FROM reference_ids
                WHERE backup_id = ?
            """,
            [backup_id]
        )

        if cursor.fetchall():
            cursor.execute("""
                    DELETE FROM reference_ids
                    WHERE backup_id = ?
                """,
                [backup_id]
            )
        
        self._conn.commit()

        cursor.close()
