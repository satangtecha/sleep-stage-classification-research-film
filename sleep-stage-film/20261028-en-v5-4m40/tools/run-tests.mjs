import {spawnSync} from 'node:child_process';
const r=spawnSync('node',['--expose-gc','--test','tests/film.test.mjs'],{stdio:'inherit',cwd:new URL('..',import.meta.url).pathname});process.exit(r.status??1)
