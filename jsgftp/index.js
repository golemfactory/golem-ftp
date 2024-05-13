import {Gftp} from "./jsgftp/gftp.js";
import {checkIfFilesIdentical, generateRandomFileSync, getRandomChars} from "./jsgftp/utils.js";
import path from 'path';
import process from 'process';
import {fileURLToPath} from 'url';
import fs from 'fs';

async function main() {
    let gftp = new Gftp();
    // Accessing environment variable GFTP_BIN_PATH
    let gftp_bin = process.env.GFTP_BIN_PATH;
    if (!gftp_bin) {
        const __filename = fileURLToPath(import.meta.url);

        // Get current file directory
        const currentFileDir = path.dirname(__filename);

        // If GFTP_BIN_PATH is not set, construct the default path
        gftp_bin = path.join(currentFileDir, '..', 'target', 'release', 'gftp');
    }
    await gftp.init(gftp_bin);

    console.log(`gftp object successfully created with gftp version: ${gftp.getVersion()}`);

    console.log("Generating test file");
    const randomFileName = "random_" + getRandomChars(6);
    const randomFileSrc = randomFileName + "_src.bin";
    const randomFileDst = randomFileName + "_dst.bin";

    await generateRandomFileSync(randomFileSrc, 1000000000);

    let context = await gftp.publishFile(randomFileSrc);

    let downloadContext = gftp.startDownloadFile(context["url"], randomFileDst);

    await gftp.waitForDownloadFinished(downloadContext);

    await gftp.unpublishFile(context);

    console.log("Check if files are identical");

    checkIfFilesIdentical(randomFileSrc, randomFileDst);

    console.log("Cleanup test files");
    fs.unlinkSync(randomFileSrc);
    fs.unlinkSync(randomFileDst);
}

main().then(_ => {
    // console.log("done");
}).catch(error => {
    console.error(error);
    throw error;
})




