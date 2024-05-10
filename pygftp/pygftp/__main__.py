import os
import asyncio
import logging

from gftp import GftpApi
from proc import run_simple
from utils import check_if_files_identical, generate_random_file, get_random_chars

logger = logging.getLogger(__name__)


async def show_progress(prefix, context):
    while True:
        await asyncio.sleep(0.5)
        ff = context["current"] / context["total"]
        print(f"{prefix}: {context['current']}/{context['total']} - {ff:.2%}")


async def example():
    logging.basicConfig(level=logging.INFO)

    # get current file directory
    current_file_dir = os.path.dirname(os.path.realpath(__file__))

    gftp_bin = os.getenv("GFTP_BIN_PATH", None)

    exe_ext = ".exe" if os.name == "nt" else ""
    if gftp_bin is None:
        logger.info("Building Golem FTP release binary")
        run_simple(["cargo", "build", "--release"])
        gftp_bin = os.path.join(
            current_file_dir, "..", "..", "target", "release", "gftp" + exe_ext
        )

    logger.info("Generating test file")

    # Write the content to a file
    random_file_name = "random_" + get_random_chars(6)
    random_file_src = random_file_name + "_src.bin"
    random_file_dst = random_file_name + "_dst.bin"
    generate_random_file(random_file_src, 1000000000)

    if not os.path.isfile(gftp_bin):
        raise Exception("gftp binary not found: " + gftp_bin)

    api = GftpApi(gftp_bin)

    context = await api.publish_file(random_file_src)

    fut2 = asyncio.create_task(show_progress("Upload progress:", context))

    async for context2 in api.download_file(context["url"], random_file_dst):
        fut3 = asyncio.create_task(show_progress("Download progress:", context2))
        pass

    fut2.cancel()
    fut3.cancel()

    await api.unpublish_file(context)

    logger.info("Comparing files if they are identical:")
    check_if_files_identical(random_file_src, random_file_dst)

    logger.info("Cleaning up test files")
    os.remove(random_file_src)
    os.remove(random_file_dst)


asyncio.run(example())
