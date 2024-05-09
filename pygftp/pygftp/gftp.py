import asyncio
import os.path
import logging
from proc import run_simple, run_gftp_start

logger = logging.getLogger(__name__)


class GftpApi:
    def __init__(self, gftp_bin):
        if not os.path.isfile(gftp_bin):
            raise Exception("gftp binary not found: " + gftp_bin)
        self.gftp_bin = gftp_bin
        self.gftp_version = self._get_version()
        logger.info("GFTP binary accepted with version: " + self.gftp_version)

    def _get_version(self):
        version = run_simple([self.gftp_bin, "--version"])
        version = version.decode().strip()
        ver = version.split(" ")
        if len(ver) <= 1:
            raise Exception("Invalid version string: " + version)
        return ver[1]

    def get_version(self):
        return self.gftp_version

    async def publish_file(self, file_path):
        logger.info(f"Publishing file: {file_path}")
        if not os.path.isfile(file_path):
            raise Exception("Cannot publish file because not found: " + file_path)
        context = run_gftp_start([self.gftp_bin, "publish", file_path])

        while context["process"].poll() is None:
            if "url" in context:
                break
            await asyncio.sleep(0.1)

        if "error" in context:
            raise Exception(context["error"])

        if context["url"]:
            logger.info(f"File published: {context['file']} with URL: {context['url']}")
        return context

    async def download_file(self, url, file_path):
        logger.info(f"Downloading file: {url}")
        context = run_gftp_start([self.gftp_bin, "download", url, file_path])

        yield context

        while context["process"].poll() is None:
            await asyncio.sleep(0.1)

        # Wait for threads to complete
        context["stdout_thread"].join()
        context["stderr_thread"].join()

        if context["process"].returncode == 0:
            logger.info(f"File downloaded: {file_path}")
        else:
            logger.error(f"Error downloading file: {file_path}")

    async def unpublish_file(self, context):
        if context["process"].poll() is None:
            context["process"].terminate()

        while context["process"].poll() is None:
            await asyncio.sleep(1)

        # Wait for threads to complete
        context["stdout_thread"].join()
        context["stderr_thread"].join()

        logger.info("GFTP process stopped successfully")
        if "error" in context:
            raise Exception(context["error"])

        return context["process"].returncode
