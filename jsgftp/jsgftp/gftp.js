import fs from 'fs';
import {runGftpStart, spawnProcessBlocking} from './proc.js';

export class Gftp {
    constructor() {
        this.gftp_bin = null;
        this.version = null;
    }

    async init(gftp_bin) {
        if (!fs.existsSync(gftp_bin)) {
            throw new Error(`Gftp binary not found in location ${gftp_bin}`);
        }
        this.gftp_bin = gftp_bin;
        this.version = await this._checkVersion();
    }

    async _checkVersion() {
        let vString = await spawnProcessBlocking(this.gftp_bin, ["--version"]);

        // trim, split by spaces and extract second element
        vString = vString.trim().split(" ")[1];
        return vString;
    }

    getVersion() {
        return this.version;
    }

    async publishFile(filePath) {
        console.log(`Publishing file: ${filePath}`);
        if (!fs.existsSync(filePath)) {
            throw new Error(`Cannot publish file because not found: ${filePath}`);
        }

        let context = runGftpStart(this.gftp_bin, ["publish", filePath]);

        while (true) {
            if ("url" in context) {
                break;
            }
            if ("exitCode" in context) {
                break;
            }
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        if ("error" in context) {
            throw new Error(context["error"]);
        }

        if (context["url"]) {
            console.log(`File published: ${context["file"]} with URL: ${context["url"]}`);
        }
        return context
    }

    startDownloadFile(url, filePath) {
        let context = runGftpStart(this.gftp_bin, ["download", url, filePath])
        return context;
    }

    async waitForDownloadFinished(context) {
        while (true) {
            if ("exitCode" in context) {
                break;
            }
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        if ("error" in context) {
            throw new Error(context["error"]);
        };
        if (context["exitCode"] != 0) {
            throw new Error(`Download failed with exit code ${context["exitCode"]}`);
        }
    }

    async unpublishFile(context) {
        context["child"].kill('SIGINT');

        while (true) {
            if ("exitCode" in context) {
                break;
            }
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    }
}