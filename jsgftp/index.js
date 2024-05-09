import fs from 'fs';
import { spawnProcessBlocking } from './jsgftp/proc.js';

class Gftp {
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

async function spawn_gftp(gftp_bin, args) {

    await spawnProcessBlocking(gftp_bin, args);
}

async function main() {
    let gftp = new Gftp();
    await gftp.init("../target/release/gftp.exe")
    console.log(`gftp object successfully created with gftp version: ${gftp.getVersion()}`);
}

main().then(_ => {
    // console.log("done");
}).catch(error => {
    console.error(error);
    throw error;
})




