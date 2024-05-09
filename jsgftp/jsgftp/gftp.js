import fs from 'fs';
import { spawnProcessBlocking } from './proc.js';

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
}