import asyncio
import json
import subprocess
import threading
import logging

logger = logging.getLogger(__name__)


def read_stream_stdout(stream, context):
    for line in stream:
        try:
            response = json.loads(line)
            logger.debug(json.dumps(response, indent=4, sort_keys=True))
            if "error" in response:
                context["error"] = response["error"]["message"]
                if "`/local/identity/Get` is unavailable" in context["error"]:
                    raise Exception("Cannot connect to yagna service. "
                                    "Check if yagna is running and proper GSB_URL is set")
            elif "result" in response:
                if isinstance(response["result"], list):
                    array = response["result"]
                    for item in array:
                        if "file" in item and "url" in item:
                            context["file"] = item["file"]
                            context["url"] = item["url"]
                        else:
                            context["error"] = "Invalid response from GFTP"
                            raise Exception(context["error"])
                else:
                    item = response["result"]
                    if "file" in item and "url" in item:
                        context["file"] = item["file"]
                        context["url"] = item["url"]
                    else:
                        context["error"] = "Invalid response from GFTP"
                        raise Exception(context["error"])
            elif "cur" in response:
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
    stdout_thread = threading.Thread(
        target=read_stream_stdout, args=(process.stdout, context)
    )
    stderr_thread = threading.Thread(
        target=read_stream_stderr, args=(process.stderr, context)
    )

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

    logger.info(
        "GFTP process finished with return code: {}".format(
            context["process"].returncode
        )
    )
    if "error" in context:
        raise Exception(context["error"])

    return context["process"].returncode


def run_simple(args):
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for the process to finish and get the output
    stdout, stderr = process.communicate()

    return stdout
