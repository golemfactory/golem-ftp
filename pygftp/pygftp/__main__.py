import os
import asyncio
import logging
import random

from gftp import GftpApi
from proc import run_simple

logger = logging.getLogger(__name__)


def check_if_files_identical(file1_path, file2_path):
    if not os.path.isfile(file1_path):
        raise Exception("File not found: " + file1_path)
    if not os.path.isfile(file2_path):
        raise Exception("File not found: " + file2_path)

    if os.stat(file1_path).st_size != os.stat(file2_path).st_size:
        raise Exception("Files are not identical. Size mismatch.")

    with open(file1_path, "rb") as file1, open(file2_path, "rb") as file2:
        while True:
            byte1 = file1.read(1000000)
            byte2 = file2.read(1000000)

            if byte1 != byte2:
                raise Exception("Files are not identical. Content mismatch.")

            if not byte1:
                break


async def show_progress(prefix, context):
    while True:
        await asyncio.sleep(1)
        ff = context["current"] / context["total"]
        print(f"{prefix}: {context['current']}/{context['total']} - {ff:.2%}")


async def example():
    logging.basicConfig(level=logging.INFO)

    logger.info("Building Golem FTP release binary")
    run_simple(["cargo", "build", "--release"])

    logger.info("Generating test file")

    # Define the file size in bytes
    file_size = 10000000

    # Generate random content for the file
    random_content = bytearray(random.getrandbits(8) for _ in range(file_size))

    # Write the content to a file
    with open("random_file.bin", "wb") as file:
        for i in range(100):
            file.write(random_content)

    # get current file dircectory
    current_file_dir = os.path.dirname(os.path.realpath(__file__))

    gftp_bin = os.path.join(
        current_file_dir, "..", "..", "target", "release", "gftp.exe"
    )

    api = GftpApi(gftp_bin)

    context = await api.publish_file("random_file.bin")

    fut2 = asyncio.create_task(show_progress("Upload progress:", context))

    async for context2 in api.download_file(context["url"], "random_file2.bin"):
        fut3 = asyncio.create_task(show_progress("Download progress:", context2))
        pass

    fut2.cancel()
    fut3.cancel()

    await api.unpublish_file(context)

    logger.info("Comparing files if they are identical:")
    check_if_files_identical("random_file.bin", "random_file2.bin")

    logger.info("Cleaning up test files")
    os.remove("random_file.bin")
    os.remove("random_file2.bin")


asyncio.run(example())
