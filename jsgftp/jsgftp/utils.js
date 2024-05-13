import fs from 'fs';
import crypto from 'crypto';
import buffer from 'buffer';


export async function generateRandomFileSync(file_path, file_size) {
    const max_chunk_size = 20000000;
    const chunk_count = Math.floor(file_size / max_chunk_size) + 1;
    // Define the file size in bytes
    const chunk_size = Math.floor(file_size / chunk_count);

    console.debug(`Generating random file: ${file_path} with chunk size: ${chunk_size}`);
    // Generate random content for the file
    const random_content = crypto.randomBytes(chunk_size);

    let total_size_written = 0;
    const file = fs.createWriteStream(file_path, {flags: 'w'});

    for (let i = 0; i < chunk_count + 1; i++) {
        if (total_size_written + chunk_size > file_size) {
            const remaining_size = file_size - total_size_written;
            file.write(random_content.slice(0, remaining_size));
            break;
        }
        file.write(random_content);
        total_size_written += chunk_size;
    }

    // block until stream finished flushing
    await new Promise((resolve, reject) => {
        file.end(() => {
            resolve();
        });
    });
}

export function getRandomChars(length) {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

export function checkIfFilesIdentical(file1Path, file2Path) {
    if (!fs.existsSync(file1Path)) {
        throw new Error("File not found: " + file1Path);
    }
    if (!fs.existsSync(file2Path)) {
        throw new Error("File not found: " + file2Path);
    }

    const stats1 = fs.statSync(file1Path);
    const stats2 = fs.statSync(file2Path);
    if (stats1.size !== stats2.size) {
        throw new Error("Files are not identical. Size mismatch.");
    }

    const bufferSize = 20000000;
    const buffer1 = buffer.Buffer.alloc(bufferSize);
    const buffer2 = buffer.Buffer.alloc(bufferSize);
    const file1 = fs.openSync(file1Path, 'r');
    const file2 = fs.openSync(file2Path, 'r');

    let bytesRead1, bytesRead2;
    let offset = 0;
    do {
        bytesRead1 = fs.readSync(file1, buffer1, 0, bufferSize, offset);
        bytesRead2 = fs.readSync(file2, buffer2, 0, bufferSize, offset);
        if (bytesRead1 !== bytesRead2 || !buffer1.equals(buffer2)) {
            fs.closeSync(file1);
            fs.closeSync(file2);
            throw new Error("Files are not identical. Content mismatch.");
        }
        offset += bytesRead1;
    } while (bytesRead1 > 0 && bytesRead2 > 0);

    fs.closeSync(file1);
    fs.closeSync(file2);
}
