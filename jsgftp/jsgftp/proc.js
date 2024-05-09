import { spawn } from 'child_process';
import fs from 'fs';


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