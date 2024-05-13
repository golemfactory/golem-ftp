import os
import random
import logging
import string

logger = logging.getLogger(__name__)


def human_bytes(size):
    if size >= 1_000_000_000:
        gibs = size / (1024 * 1024 * 1024)
        if gibs >= 100:
            return f"{gibs:.0f} GiB"
        if gibs >= 10:
            return f"{gibs:.1f} GiB"
        if gibs >= 1:
            return f"{gibs:.2f} GiB"
        return f"{gibs:.3f} GiB"
    if size >= 1_000_000:
        mibs = size / (1024 * 1024)
        if mibs >= 100:
            return f"{mibs:.0f} MiB"
        if mibs >= 10:
            return f"{mibs:.1f} MiB"
        if mibs >= 1:
            return f"{mibs:.2f} MiB"
        return f"{mibs:.3f} MiB"
    if size >= 1000:
        kibs = size / 1024
        if kibs >= 100:
            return f"{kibs:.0f} KiB"
        if kibs >= 10:
            return f"{kibs:.1f} KiB"
        if kibs >= 1:
            return f"{kibs:.2f} KiB"
        return f"{kibs:.3f} KiB"
    return f"{size} B"


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


def generate_random_file(file_path, file_size):
    max_chunk_size = 20000000
    chunk_count = file_size // max_chunk_size + 1
    # Define the file size in bytes
    chunk_size = file_size // chunk_count

    logger.debug(f"Generating random file: {file_path} with chunk size: {chunk_size}")
    # Generate random content for the file
    random_content = bytearray(random.getrandbits(8) for _ in range(chunk_size))

    total_size_written = 0
    with open(file_path, "wb") as file:
        for i in range(chunk_count + 1):
            if total_size_written + chunk_size > file_size:
                chunk_size = file_size - total_size_written
                file.write(random_content[:chunk_size])
                break
            file.write(random_content)
            total_size_written += chunk_size


def get_random_chars(length):
    return ''.join(random.choices(
        string.ascii_lowercase + string.digits + string.ascii_uppercase, k=length))
