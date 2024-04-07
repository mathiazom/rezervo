import math
from pathlib import Path
from typing import Optional
from uuid import UUID

import PIL
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps
from starlette import status

from rezervo.consts import (
    AVATAR_FILENAME,
    AVATAR_THUMBNAIL_SIZES,
)
from rezervo.schemas.config.config import read_app_config
from rezervo.utils.logging_utils import log


def save_upload_file(
    upload_file: UploadFile, destination: Path, max_bytes: int
) -> None:
    try:
        total_bytes_read = 0
        with destination.open("wb") as buffer:
            for chunk in upload_file.file:
                total_bytes_read += len(chunk)
                if total_bytes_read > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                    )
                buffer.write(chunk)
        log.debug(
            f"Saved uploaded avatar file '{upload_file.filename}' (size: {total_bytes_read})"
        )
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        upload_file.file.close()


def build_user_avatars_dir(user_id: UUID) -> Optional[Path]:
    content = read_app_config().content
    avatars_dir_str = content.avatars_dir if content is not None else None
    if avatars_dir_str is None:
        log.warning("Avatars directory is not configured")
        return None
    return Path(avatars_dir_str) / str(user_id)


def get_user_avatar_file_by_id(user_id: UUID, size_name: str):
    size = AVATAR_THUMBNAIL_SIZES.get(size_name)
    if size is None:
        log.warning(f"Invalid avatar size '{size_name}'")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    user_avatar_dir = build_user_avatars_dir(user_id)
    if user_avatar_dir is None or not user_avatar_dir.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    avatar_size_dirs = list(user_avatar_dir.iterdir())
    if len(avatar_size_dirs) == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    file = None
    for d in avatar_size_dirs:
        if d.is_dir() and d.name == size_name:
            file = next(d.iterdir(), None)
            break
    return file


def resize_image_to_square(image: PIL.Image.Image, length: int) -> PIL.Image.Image:
    """
    Resize image (preserving ratio) so that the smallest side matches the given length,
    then crop the other side to match the same length.
    """
    width, height = image.size
    resized_dim = int(max(width, height) * (length / min(width, height)))
    required_crop = (resized_dim - length) / 2.0
    crop_from = math.floor(required_crop)
    crop_to = resized_dim - math.ceil(required_crop)
    if width < height:
        return image.resize((length, resized_dim)).crop(
            box=(0, crop_from, length, crop_to)
        )
    return image.resize((resized_dim, length)).crop(box=(crop_from, 0, crop_to, length))


def generate_avatar_thumbnails(avatar_path: Path):
    try:
        with Image.open(avatar_path) as raw_image:
            image = ImageOps.exif_transpose(raw_image)
            for key, size in AVATAR_THUMBNAIL_SIZES.items():
                thumb = resize_image_to_square(image, size)
                thumb_dir = avatar_path.parent / key
                thumb_dir.mkdir(parents=False, exist_ok=True)
                thumb.save(thumb_dir / AVATAR_FILENAME, optimize=True)
                log.debug(f"Generated thumbnail ({size} x {size})")
    except PIL.UnidentifiedImageError as e:
        log.warning(f"Failed to open avatar image: {e}")
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        ) from None
