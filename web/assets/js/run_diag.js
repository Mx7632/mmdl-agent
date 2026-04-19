const { execFile } = require('child_process');
const py = execFile('E:\\Anaconda3\\envs\\mmdl-agent\\python.exe',
    ['D:/Graduation_project/MMDL/diagnose_astream.py'],
    (e, stdout, stderr) => {
        console.log('STDOUT:', stdout);
        if(stderr) console.log('STDERR:', stderr);
        if(e) console.log('ERR:', e.message);
    }
);
