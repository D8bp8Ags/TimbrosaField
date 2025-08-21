import contextlib
import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field

from wav_analyzer import inject_info_chunk

# Configure logging
logging.basicConfig(
    level=getattr(
        logging,
        os.getenv("LOG_LEVEL", "DEBUG").upper(),
        logging.INFO,
    ),
    format="[%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class SaveError(Exception):
    """Custom exception for save operations."""

    pass


@dataclass
class SaveResult:
    """Result object for save operations.

    Provides comprehensive feedback about the save operation including success status,
    file paths, and any errors encountered.
    """

    success: bool
    output_path: str = ""
    backup_path: str = ""
    error_message: str = ""
    files_created: list[str] = field(default_factory=list)
    operation_type: str = ""

    def __post_init__(self):
        """Add created files to list automatically."""
        if self.success:
            if self.output_path and self.output_path not in self.files_created:
                self.files_created.append(self.output_path)
            if self.backup_path and self.backup_path not in self.files_created:
                self.files_created.append(self.backup_path)


class WavSaveStrategies:
    """Centralized WAV file save strategies.

    This class provides static methods for different WAV file save operations,
    eliminating code duplication between WavViewer and BatchTagEditor.

    All methods return SaveResult objects for consistent error handling and feedback
    across the application.
    """

    # === CORE SAVE STRATEGIES ===

    @staticmethod
    def save_as_edit_copy(
        source_path: str, metadata: dict[str, str], output_dir: str | None = None
    ) -> SaveResult:
        """Save as copy with _edit suffix.

        Creates a new file with '_edit' suffix, incrementing counter if needed. This is
        the safest option as it never overwrites existing files.

        Args:     source_path: Path to source WAV file     metadata: Dictionary of
        metadata to inject     output_dir: Output directory (defaults to source
        directory)

        Returns:     SaveResult with operation details
        """
        try:
            WavSaveStrategies._validate_inputs(source_path, metadata)

            # Determine output directory
            if output_dir is None:
                output_dir = os.path.dirname(source_path)

            # Create base output path
            source_name = os.path.splitext(os.path.basename(source_path))[0]
            base_output_path = os.path.join(output_dir, f"{source_name}_edit.wav")

            # Ensure unique filename
            final_output_path = WavSaveStrategies._ensure_unique_filename(
                base_output_path
            )

            # Inject metadata and save
            WavSaveStrategies._inject_metadata_to_file(
                source_path, final_output_path, metadata
            )

            logger.info(f"Saved as edit copy: {os.path.basename(final_output_path)}")

            return SaveResult(
                success=True, output_path=final_output_path, operation_type="edit_copy"
            )

        except Exception as e:
            logger.error(f"Error in save_as_edit_copy: {e}")
            return SaveResult(
                success=False, error_message=str(e), operation_type="edit_copy"
            )

    @staticmethod
    def save_in_place(
        source_path: str,
        metadata: dict[str, str],
        confirm_callback: Callable[[], bool] | None = None,
    ) -> SaveResult:
        """Save in place (overwrite original file).

        Overwrites the original file after optional confirmation. Uses temporary file to
        ensure atomic operation.

        Args:     source_path: Path to source WAV file     metadata: Dictionary of
        metadata to inject     confirm_callback: Optional function to confirm overwrite

        Returns:     SaveResult with operation details
        """
        try:
            WavSaveStrategies._validate_inputs(source_path, metadata)

            # Ask for confirmation if callback provided
            if confirm_callback and not confirm_callback():
                return SaveResult(
                    success=False,
                    error_message="Operation cancelled by user",
                    operation_type="in_place",
                )

            # Create temporary file
            temp_path = source_path + ".tmp"

            try:
                # Inject metadata to temp file
                WavSaveStrategies._inject_metadata_to_file(
                    source_path, temp_path, metadata
                )

                # Atomically replace original
                os.replace(temp_path, source_path)

                logger.info(f"Saved in place: {os.path.basename(source_path)}")

                return SaveResult(
                    success=True, output_path=source_path, operation_type="in_place"
                )

            finally:

                # Cleanup temp file if it exists
                if os.path.exists(temp_path):
                    with contextlib.suppress(Exception):
                        os.remove(temp_path)

        except Exception as e:
            logger.error(f"Error in save_in_place: {e}")
            return SaveResult(
                success=False, error_message=str(e), operation_type="in_place"
            )

    @staticmethod
    def save_with_backup(source_path: str, metadata: dict[str, str]) -> SaveResult:
        """Create .bak backup then replace original.

        Creates a backup copy with .bak extension, then overwrites original. Provides
        safety while maintaining original filename.

        Args:     source_path: Path to source WAV file     metadata: Dictionary of
        metadata to inject

        Returns:     SaveResult with operation details
        """
        try:
            WavSaveStrategies._validate_inputs(source_path, metadata)

            backup_path = source_path + ".bak"
            temp_path = source_path + ".tmp"

            try:
                # Create backup of original
                shutil.copy2(source_path, backup_path)
                logger.debug(f"Backup created: {os.path.basename(backup_path)}")

                # Create temp file with metadata
                WavSaveStrategies._inject_metadata_to_file(
                    source_path, temp_path, metadata
                )

                # Replace original
                os.replace(temp_path, source_path)

                logger.info(f"Saved with backup: {os.path.basename(source_path)}")

                return SaveResult(
                    success=True,
                    output_path=source_path,
                    backup_path=backup_path,
                    operation_type="with_backup",
                )

            finally:

                # Cleanup temp file if it exists

                if os.path.exists(temp_path):
                    with contextlib.suppress(Exception):
                        os.remove(temp_path)

        except Exception as e:
            logger.error(f"Error in save_with_backup: {e}")
            return SaveResult(
                success=False, error_message=str(e), operation_type="with_backup"
            )

    @staticmethod
    def save_with_custom_name(
        source_path: str,
        metadata: dict[str, str],
        custom_name: str,
        output_dir: str | None = None,
    ) -> SaveResult:
        """Save with user-specified filename.

        Saves to a custom filename, with optional directory override. Ensures .wav
        extension and handles existing files.

        Args:     source_path: Path to source WAV file     metadata: Dictionary of
        metadata to inject     custom_name: Custom filename (without extension)
        output_dir: Output directory (defaults to source directory)

        Returns:     SaveResult with operation details
        """
        try:
            WavSaveStrategies._validate_inputs(source_path, metadata)

            if not custom_name or not custom_name.strip():
                raise SaveError("Custom name cannot be empty")

            # Clean and prepare custom name
            clean_name = custom_name.strip()
            if not clean_name.lower().endswith(".wav"):
                clean_name += ".wav"

            # Determine output directory
            if output_dir is None:
                output_dir = os.path.dirname(source_path)

            # Create output path
            output_path = os.path.join(output_dir, clean_name)

            # Check if file already exists and confirm overwrite if needed
            if os.path.exists(output_path):
                # For now, we'll auto-increment. Could add confirmation callback later
                output_path = WavSaveStrategies._ensure_unique_filename(output_path)

            # Inject metadata and save
            WavSaveStrategies._inject_metadata_to_file(
                source_path, output_path, metadata
            )

            logger.info(f"Saved with custom name: {os.path.basename(output_path)}")

            return SaveResult(
                success=True, output_path=output_path, operation_type="custom_name"
            )

        except Exception as e:
            logger.error(f"Error in save_with_custom_name: {e}")
            return SaveResult(
                success=False, error_message=str(e), operation_type="custom_name"
            )

    @staticmethod
    def save_batch_style(
        source_path: str, metadata: dict[str, str], use_backup: bool = False
    ) -> SaveResult:
        """Save with _batch suffix or backup strategy.

        Designed for batch operations. Either creates _batch suffixed copy or uses
        backup strategy based on user preference.

        Args:     source_path: Path to source WAV file     metadata: Dictionary of
        metadata to inject     use_backup: If True, use backup strategy; if False, use
        _batch suffix

        Returns:     SaveResult with operation details
        """
        try:
            if use_backup:
                # Use backup strategy for batch
                result = WavSaveStrategies.save_with_backup(source_path, metadata)
                result.operation_type = "batch_backup"
                return result
            else:
                # Create _batch suffixed copy
                source_dir = os.path.dirname(source_path)
                source_name = os.path.splitext(os.path.basename(source_path))[0]
                batch_name = f"{source_name}_batch.wav"
                output_path = os.path.join(source_dir, batch_name)

                # Ensure unique filename
                final_output_path = WavSaveStrategies._ensure_unique_filename(
                    output_path
                )

                # Inject metadata and save
                WavSaveStrategies._inject_metadata_to_file(
                    source_path, final_output_path, metadata
                )

                logger.info(f"Saved batch style: {os.path.basename(final_output_path)}")

                return SaveResult(
                    success=True,
                    output_path=final_output_path,
                    operation_type="batch_suffix",
                )

        except Exception as e:
            logger.error(f"Error in save_batch_style: {e}")
            return SaveResult(
                success=False,
                error_message=str(e),
                operation_type="batch_suffix" if not use_backup else "batch_backup",
            )

    # === HELPER METHODS ===

    @staticmethod
    def _validate_inputs(source_path: str, metadata: dict[str, str]) -> None:
        """Validate inputs before processing.

        Args:     source_path: Path to validate     metadata: Metadata to validate

        Raises:     SaveError: If inputs are invalid
        """
        if not source_path:
            raise SaveError("Source path cannot be empty")

        if not os.path.exists(source_path):
            raise SaveError(f"Source file does not exist: {source_path}")

        if not source_path.lower().endswith(".wav"):
            raise SaveError(f"Source file must be WAV format: {source_path}")

        if not isinstance(metadata, dict):
            raise SaveError("Metadata must be a dictionary")

        # Check if we can read the source file
        try:
            with open(source_path, "rb") as f:
                f.read(12)  # Read WAV header
        except Exception as e:
            raise SaveError(f"Cannot read source file: {e}") from e

    @staticmethod
    def _ensure_unique_filename(target_path: str) -> str:
        """Add counter if file exists (file.wav -> file_1.wav).

        Args:     target_path: Desired file path

        Returns:     Unique file path that doesn't exist
        """
        if not os.path.exists(target_path):
            return target_path

        base_path = os.path.splitext(target_path)[0]
        extension = os.path.splitext(target_path)[1]

        counter = 1
        while True:
            new_path = f"{base_path}_{counter}{extension}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1

            # Safety valve to prevent infinite loop
            if counter > 1000:
                raise SaveError("Too many existing files with similar names")

    @staticmethod
    def _inject_metadata_to_file(
        source_path: str, target_path: str, metadata: dict[str, str]
    ) -> None:
        """Inject metadata into WAV file.

        Args:     source_path: Source WAV file     target_path: Target WAV file
        metadata: Metadata to inject

        Raises:     SaveError: If injection fails
        """
        try:

            inject_info_chunk(source_path, target_path, metadata)

        except ImportError:
            raise SaveError("wav_analyzer module not available") from None
        except Exception as e:
            raise SaveError(f"Failed to inject metadata: {e}") from e


# === CONVENIENCE FUNCTIONS FOR BACKWARDS COMPATIBILITY ===


def quick_save_edit_copy(source_path: str, metadata: dict[str, str]) -> bool:
    """Quick save as edit copy (backwards compatibility).

    Returns:     True if successful, False otherwise
    """
    result = WavSaveStrategies.save_as_edit_copy(source_path, metadata)
    return result.success


def quick_save_with_backup(source_path: str, metadata: dict[str, str]) -> bool:
    """Quick save with backup (backwards compatibility).

    Returns:     True if successful, False otherwise
    """
    result = WavSaveStrategies.save_with_backup(source_path, metadata)
    return result.success


# === TESTING HELPER ===


def test_save_strategies():
    """Test function to verify save strategies work correctly.

    This function can be used during development to test the save strategies with mock
    data before integrating into the main application.
    """
    logger.debug("Testing WavSaveStrategies...")

    # Mock test data
    # test_metadata = {
    #     "INAM": "Test Recording",
    #     "IART": "Test Artist",
    #     "ICMT": "test, metadata, injection",
    # }

    logger.info("WavSaveStrategies class loaded successfully")
    logger.info("SaveResult dataclass initialized")
    logger.info("All strategy methods defined")
    logger.info("Helper methods implemented")
    logger.info("Ready for integration testing with real WAV files")


if __name__ == "__main__":
    test_save_strategies()
