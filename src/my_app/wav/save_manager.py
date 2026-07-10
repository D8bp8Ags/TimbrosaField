"""WAV Save Manager Module.

Pure save orchestration: no dialogs, no message boxes, no user interaction.
Takes explicit save choices (already collected by UI code) and executes the
chosen save strategy via wav_save_strategies.py, returning a SaveResult.

UI code (e.g. WavViewer) is responsible for:
    1. Opening ui.dialogs.wav_save_dialog.WavSaveOptionsDialog to collect
       the user's save method / custom name / tag-merge choice.
    2. Confirming destructive operations (e.g. in-place overwrite) via its
       own QMessageBox before calling this manager.
    3. Interpreting the returned SaveResult and showing success/error
       messages.

Usage:
    from wav_save_manager import WavSaveManager

    manager = WavSaveManager()
    result = manager.execute_save(
        save_method=1,
        filename=self.filename,
        metadata=metadata,
        new_tags=['nature', 'birds'],
        existing_tags='forest, morning',
        merge_tags=True,
        user_config=self.user_config,
    )

    if result and result.success:
        self.load_wav_files(select_path=result.output_path)
"""

import logging
import struct
from typing import Any, Optional

from my_app.wav.analyzer import wav_analyze
from my_app.wav.save_strategies import SaveError, SaveResult, WavSaveStrategies

logger = logging.getLogger(__name__)


class WavSaveManager:
    """Pure save orchestration for WAV file save operations.

    Given an already-chosen save method (and any UI-collected inputs like
    custom filename, tag-merge preference, and an overwrite-confirmation
    callback), executes the corresponding WavSaveStrategies operation.
    Contains no Qt widget classes and shows no dialogs itself.
    """

    def execute_save(
        self,
        save_method: int,
        filename: str,
        metadata: dict[str, str],
        new_tags: list[str] = None,
        existing_tags: str = "",
        merge_tags: bool = False,
        custom_name: str = "",
        user_config: dict[str, Any] = None,
        gps_data: dict[str, float] | None = None,
        confirm_overwrite: Optional[callable] = None,
    ) -> Optional["SaveResult"]:
        """Execute the chosen save operation with already-collected user input.

        Args:
            save_method: Chosen save method (1=edit copy, 2=in-place,
                3=backup, 4=custom name), as returned by
                WavSaveOptionsDialog.get_save_method().
            filename: Path to current WAV file.
            metadata: Metadata dictionary to save.
            new_tags: List of new tags to add.
            existing_tags: String of existing tags.
            merge_tags: Whether to merge new tags with existing_tags
                (True) or replace them (False), as chosen by the user.
            custom_name: Custom filename, used only when save_method == 4.
            user_config: User configuration dictionary (used to resolve
                the output directory).
            gps_data: GPS data to inject (non-empty dict), remove (empty
                dict {}), or leave unchanged (None).
            confirm_overwrite: Optional callable returning True/False,
                used only for save_method == 2 (in-place). UI code should
                supply this to show its own confirmation dialog; if
                omitted, in-place overwrite proceeds without confirmation.

        Returns:
            SaveResult describing success/failure, or None if inputs were
            invalid (missing file, no metadata to save) or the save method
            is unrecognized. On success or failure the underlying
            SaveResult always carries the outcome; None is only returned
            for validation failures that occur before a strategy is even
            attempted.
        """
        if not filename:
            logger.warning("execute_save called without a filename")
            return None

        new_tags_string = ", ".join(new_tags) if new_tags else ""

        if new_tags_string:
            metadata = self._merge_tags_if_needed(
                metadata, new_tags_string, existing_tags, merge_tags
            )

        return self._execute_save_strategy(
            save_method=save_method,
            filename=filename,
            metadata=metadata,
            custom_name=custom_name,
            user_config=user_config,
            gps_data=gps_data,
            confirm_overwrite=confirm_overwrite,
        )

    def has_anything_to_save(
        self,
        filename: str,
        metadata: dict[str, str],
        new_tags: list[str],
        gps_info: str,
    ) -> bool:
        """Check whether there is anything meaningful to save.

        Args:
            filename: Path to current WAV file.
            metadata: Metadata dictionary to save.
            new_tags: List of new tags to add.
            gps_info: Non-empty string when GPS data will be
                added/changed/removed.

        Returns:
            True if there are tag changes, metadata changes, or GPS
            changes; False otherwise.
        """
        new_tags_string = ", ".join(new_tags) if new_tags else ""
        has_metadata_changes = self._check_metadata_changes(filename, metadata)
        return bool(new_tags_string or has_metadata_changes or gps_info)

    def check_metadata_changes(self, filename: str, metadata: dict[str, str]) -> bool:
        """Public wrapper for _check_metadata_changes (used by UI success messages)."""
        return self._check_metadata_changes(filename, metadata)

    def _check_metadata_changes(self, filename: str, metadata: dict[str, str]) -> bool:
        """Check if metadata has changes compared to original file.

        Args:     filename: Path to WAV file     metadata: Current metadata dictionary

        Returns:     True if there are changes, False otherwise
        """
        try:

            result = wav_analyze(filename)
            original_info = result.get("info", {})

            return any(
                metadata.get(key, "") != original_info.get(key, "")
                for key in metadata.keys()
                if key in original_info or metadata.get(key, "").strip()
            )
        except (KeyError, TypeError) as e:
            logger.warning(f"Could not check metadata changes: {e}")
            return True  # Assume changes if we can't check

    def _merge_tags_if_needed(
        self,
        metadata: dict[str, str],
        new_tags_string: str,
        existing_tags: str,
        merge_tags: bool,
    ) -> dict[str, str]:
        """Merge or replace tags based on user choice.

        Args:     metadata: Current metadata dictionary     new_tags_string: New tags as
        comma-separated string     existing_tags: Existing tags as comma-separated
        string     merge_tags: Whether to merge (True) or replace (False)

        Returns:     Updated metadata dictionary
        """
        if merge_tags and existing_tags.strip():
            # Merge tags without duplicates
            existing_list = [
                tag.strip() for tag in existing_tags.split(",") if tag.strip()
            ]
            new_list = [
                tag.strip() for tag in new_tags_string.split(",") if tag.strip()
            ]

            combined = existing_list.copy()
            for tag in new_list:
                if tag not in combined:
                    combined.append(tag)

            metadata["ICMT"] = ", ".join(combined)
            logger.debug(f"Tags merged: '{metadata['ICMT']}'")
        else:
            # Replace tags
            metadata["ICMT"] = new_tags_string
            logger.debug(f"Tags replaced: '{metadata['ICMT']}'")

        return metadata

    def _execute_save_strategy(
        self,
        save_method: int,
        filename: str,
        metadata: dict[str, str],
        custom_name: str,
        user_config: dict[str, Any],
        gps_data: dict[str, float] | None = None,
        confirm_overwrite: Optional[callable] = None,
    ) -> Optional["SaveResult"]:
        """Execute the chosen save strategy.

        Args:     save_method: Chosen save method (1-4)     filename: Source file path
        metadata: Metadata to save     custom_name: Custom filename (if method 4)
        user_config: User configuration

        Returns:     SaveResult object or None if failed
        """
        try:

            # Get output directory from config
            output_dir = None
            if user_config and "paths" in user_config:
                output_dir = user_config["paths"].get("fieldrecording_dir")

            # Create strategy mapping
            strategies = {
                1: lambda: WavSaveStrategies.save_as_edit_copy(
                    filename, metadata, gps_data, output_dir
                ),
                2: lambda: WavSaveStrategies.save_in_place(
                    filename, metadata, gps_data, confirm_overwrite
                ),
                3: lambda: WavSaveStrategies.save_with_backup(filename, metadata, gps_data),
                4: lambda: WavSaveStrategies.save_with_custom_name(
                    filename, metadata, custom_name, output_dir, gps_data
                ),
            }

            if save_method not in strategies:
                logger.error(f"Unknown save method: {save_method}")
                return None

            return strategies[save_method]()

        except (OSError, struct.error, SaveError) as e:
            logger.error(f"Error executing save strategy: {e}")
            return None
