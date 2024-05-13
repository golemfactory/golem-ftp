import os
import asyncio
import logging

from gftp import GftpApi
from proc import run_simple
from utils import check_if_files_identical, generate_random_file, get_random_chars, human_bytes

logger = logging.getLogger(__name__)


async def show_progress(prefix, context):
    while True:
        await asyncio.sleep(0.5)
        ff = context["current"] / context["total"]
        human_1 = human_bytes(context["speedCurrent"])
        print(f"{prefix}: {context['current']}/{context['total']} - {ff:.2%} - {human_1}/s - {context['elapsed']}s")


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

    gsb_url_1 = os.getenv("GSB_URL_1", None)
    gsb_url_2 = os.getenv("GSB_URL_2", None)

    if os.getenv("GSB_URL", None):
        logger.info("Using commonn gsb url: {}", os.getenv("GSB_URL"))
        gsb_url_1 = os.getenv("GSB_URL")
        gsb_url_2 = os.getenv("GSB_URL")

    if gsb_url_1:
        logger.info(f"Api1 using gsb_url: {gsb_url_1}")
    else:
        logger.info("Api1 using default gsb_url")
    if gsb_url_2:
        logger.info(f"Api2 using gsb_url: {gsb_url_2}")
    else:
        logger.info("Api2 using default gsb_url")
    api1 = GftpApi(gftp_bin, gsb_url=gsb_url_1)
    api2 = GftpApi(gftp_bin, gsb_url=gsb_url_2)

    context = await api1.publish_file(random_file_src)

    fut2 = asyncio.create_task(show_progress("Upload progress:", context))

    async for context2 in api2.download_file(context["url"], random_file_dst):
        fut3 = asyncio.create_task(show_progress("Download progress:", context2))
        pass

    fut2.cancel()
    fut3.cancel()

    await api1.unpublish_file(context)

    logger.info("Comparing files if they are identical:")
    check_if_files_identical(random_file_src, random_file_dst)

    logger.info("Cleaning up test files")
    os.remove(random_file_src)
    os.remove(random_file_dst)


asyncio.run(example())
