import asyncio
import json
import os.path
import platform
import subprocess
import threading
import logging

logger = logging.getLogger(__name__)


def read_stream_stdout(stream, context):
    for line in stream:
        try:
            response = json.loads(line)
            logger.debug(json.dumps(response, indent=4, sort_keys=True))
            if 'error' in response:
                if 'code' in response['error']:
                    if response['error']['code'] == -32000:
                        context["error"] = ("Cannot connect to running yagna. "
                                            "Check if yagna service is running and proper GSB_URL is set")
                    else:
                        context["error"] = response['error']['message']
            elif 'result' in response:
                if isinstance(response['result'], list):
                    array = response['result']
                    for item in array:
                        if "file" in item and "url" in item:
                            context["file"] = item["file"]
                            context["url"] = item["url"]
                        else:
                            context["error"] = "Invalid response from GFTP"
                            raise Exception(context["error"])
                else:
                    item = response['result']
                    if "file" in item and "url" in item:
                        context["file"] = item["file"]
                        context["url"] = item["url"]
                    else:
                        context["error"] = "Invalid response from GFTP"
                        raise Exception(context["error"])
            elif 'cur' in response:
                context["current"] = response["cur"]
                context["total"] = response["tot"]
                context["speedCurrent"] = response["spc"]
                context["speedTotal"] = response["spt"]
                context["elapsed"] = response["elp"]

        except json.JSONDecodeError:
            logger.info(f"Cannot parse line: {line}")

    logger.debug("EOF")

def read_stream_stderr(stream, context):
    for line in stream:
        print("ERR: ", line.decode().strip())


def run_gftp_start(args):
    context = {}
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    context["current"] = 0
    context["total"] = 0
    context["speedCurrent"] = 0
    context["speedTotal"] = 0
    context["elapsed"] = 0
    context["process"] = process
    # Create threads to read stdout and stderr concurrently
    stdout_thread = threading.Thread(target=read_stream_stdout, args=(process.stdout, context))
    stderr_thread = threading.Thread(target=read_stream_stderr, args=(process.stderr, context))

    # Start the threads
    stdout_thread.start()
    stderr_thread.start()

    context["stdout_thread"] = stdout_thread
    context["stderr_thread"] = stderr_thread

    return context


def run_gftp_blocking(args):
    context = run_gftp_start(args)

    # Wait for the process to finish
    context["process"].wait()

    # Wait for threads to complete
    context["stdout_thread"].join()
    context["stderr_thread"].join()


async def run_gftp_async(args):
    context = run_gftp_start(args)

    while context["process"].poll() is None:
        await asyncio.sleep(1)

    # Wait for threads to complete
    context["stdout_thread"].join()
    context["stderr_thread"].join()

    logger.info("GFTP process finished with return code: {}".format(context["process"].returncode))
    if "error" in context:
        raise Exception(context["error"])

    return context["process"].returncode


def run_simple(args):
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for the process to finish and get the output
    stdout, stderr = process.communicate()

    return stdout


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
        context = run_gftp_start([self.gftp_bin, "publish", file_path])

        while context["process"].poll() is None:
            if "url" in context:
                break
            await asyncio.sleep(0.1)

        if context["url"]:
            logger.info(f"File published: {context['file']} with URL: {context['url']}")
        return context

    async def download_file(self, url, file_path):
        logger.info(f"Downloading file: {url}")
        context = run_gftp_start([self.gftp_bin, "download", url, file_path])

        while context["process"].poll() is None:
            await asyncio.sleep(0.1)

        # Wait for threads to complete
        context["stdout_thread"].join()
        context["stderr_thread"].join()

        if context["process"].returncode == 0:
            logger.info(f"File downloaded: {file_path}")
        else:
            logger.error(f"Error downloading file: {file_path}")

        return context

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


async def show_progress(context):
    while True:
        await asyncio.sleep(1)
        ff = context['current'] / context['total']
        print(f"Progress: {context['current']}/{context['total']} - {ff:.2%}")



async def example():
    logging.basicConfig(level=logging.INFO)
    if platform.system() == 'Windows':
        gftp_bin = r"..\..\target\release\golem-ftp.exe"
    else:
        gftp_bin = "../../target/release/golem-ftp"

    api = GftpApi(gftp_bin)

    context = await api.publish_file("../../tensors")

    fut2 = asyncio.create_task(show_progress(context))

    await api.download_file(context["url"], "../../tensors2")

    fut2.cancel()

    await api.unpublish_file(context)


if __name__ == "__main__":
    asyncio.run(example())