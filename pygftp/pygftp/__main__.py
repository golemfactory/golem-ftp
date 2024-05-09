import asyncio
import platform
import logging
import random

from gftp import GftpApi
from proc import run_simple

logger = logging.getLogger(__name__)


async def show_progress(context):
    while True:
        await asyncio.sleep(1)
        ff = context['current'] / context['total']
        print(f"Progress: {context['current']}/{context['total']} - {ff:.2%}")


async def example():
    logging.basicConfig(level=logging.DEBUG)

    logger.info("Building Golem FTP release binary")
    run_simple(["cargo", "build", "--release"])

    logger.info("Generating test file")

    # Define the file size in bytes
    file_size = 10000000

    # Generate random content for the file
    random_content = bytearray(random.getrandbits(8) for _ in range(file_size))

    # Write the content to a file
    with open('random_file.bin', 'wb') as file:
        for i in range(100):
            file.write(random_content)

    if platform.system() == 'Windows':
        gftp_bin = r"..\target\release\golem-ftp.exe"
    else:
        gftp_bin = "../target/release/golem-ftp"

    api = GftpApi(gftp_bin)

    context = await api.publish_file("random_file.bin")

    fut2 = asyncio.create_task(show_progress(context))

    await api.download_file(context["url"], "random_file2.bin")

    fut2.cancel()

    await api.unpublish_file(context)


if __name__ == "__main__":
    asyncio.run(example())