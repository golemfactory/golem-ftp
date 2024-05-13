import { spawn } from 'child_process';
import fs from 'fs';


function tryParseLine(line, context) {
    try {
        let response = JSON.parse(line);
        console.debug(JSON.stringify(response, null, 4));

        if ("error" in response) {
            let errMsg = response["error"]["message"];
            if (errMsg.includes("`/local/identity/Get` is unavailable")) {
                context["error"] = "Cannot connect to yagna service - check if yagna is running and proper GSB_URL is set.";
            } else {
                context["error"] = errMsg;
            }
        } else if ("result" in response) {
            if (Array.isArray(response["result"])) {
                let array = response["result"];
                for (let item of array) {
                    if ("file" in item && "url" in item) {
                        context["file"] = item["file"];
                        context["url"] = item["url"];
                    } else {
                        context["error"] = "Invalid response from GFTP";
                    }
                }
            } else {
                let item = response["result"];
                if ("file" in item && "url" in item) {
                    context["file"] = item["file"];
                    context["url"] = item["url"];
                } else {
                    context["error"] = "Invalid response from GFTP";
                }
            }
        } else if ("cur" in response) {
            context["current"] = response["cur"];
            context["total"] = response["tot"];
            context["speedCurrent"] = response["spc"];
            context["speedTotal"] = response["spt"];
            context["elapsed"] = response["elp"];
        }
    } catch (error) {
        console.info(`Cannot parse line: ${line}`);
    }
}

export function runGftpStart(command, args) {
    const child = spawn(command, args);

    // You can also use a variable to save the output
    // for when the script closes later
    let scriptOutput = "";
    let context = {};
    context["child"] = child;

    child.stdout.setEncoding('utf8');
    child.stdout.on('data', function (data) {
        try {
            tryParseLine(data, context);
        } catch (error) {
            console.error(error);
        }


        data = data.toString();
        scriptOutput += data;
    });

    child.stderr.setEncoding('utf8');
    child.stderr.on('data', function (data) {
        //Here is where the error output goes

        //console.log('stderr: ' + data);

        data = data.toString();
        scriptOutput += data;
    });

    child.on('close', (code) => {
        context["exitCode"] = code;
    });
    return context;
}

export async function spawnProcessBlocking(command, args) {
    const child = spawn(command, args);

    // You can also use a variable to save the output
    // for when the script closes later
    let scriptOutput = "";

    child.stdout.setEncoding('utf8');
    child.stdout.on('data', function (data) {
        //Here is where the output goes

        //console.log('stdout: ' + data);

        data = data.toString();
        scriptOutput += data;
    });

    child.stderr.setEncoding('utf8');
    child.stderr.on('data', function (data) {
        //Here is where the error output goes

        //console.log('stderr: ' + data);

        data = data.toString();
        scriptOutput += data;
    });

    await new Promise((resolve, reject) => {
        child.on('close', (code) => {
            if (code === 0) {
                resolve();
            } else {
                reject(new Error(`Exit code ${code}`));
            }
        });
    });
    return scriptOutput;
}