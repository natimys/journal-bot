import io
import zipfile

from aiogram import Bot

from app.logger import logger


async def create_homework_zip(bot: Bot, file_ids: list[str]) -> io.BytesIO:
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for i, file_id in enumerate(file_ids):
            try:
                file = await bot.get_file(file_id)

                file_content = await bot.download_file(file.file_path)

                extension = (
                    file.file_path.split(".")[-1] if "." in file.file_path else "dat"
                )
                filename = f"file_{i + 1}.{extension}"

                zip_file.writestr(filename, file_content.getvalue())
                logger.info(f"File {filename} added to archive.")

            except Exception as e:
                logger.error(f"Failed to add file {file_id} to zip: {e}")
                continue

    zip_buffer.seek(0)
    return zip_buffer
