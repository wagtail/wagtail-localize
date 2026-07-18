/* eslint-env node */
/* eslint-disable @typescript-eslint/no-var-requires, import/no-extraneous-dependencies, import/no-unresolved */

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const ts = require('typescript');
const vm = require('vm');

const sourcePath = path.resolve(
    __dirname,
    '../wagtail_localize/static_src/common/components/ImageChooser/api/index.ts'
);
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
    compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2018,
    },
});
const testModule = { exports: {} };

vm.runInNewContext(compiled.outputText, {
    module: testModule,
    exports: testModule.exports,
    fetch: (...args) => global.fetch(...args),
});

const { fetchImageInfo } = testModule.exports;
const originalFetch = global.fetch;

const validImage = {
    id: 42,
    title: 'Landscape',
    thumbnail: {
        url: '/media/images/landscape.max-165x165.jpg',
        width: 165,
        height: 110,
    },
};

const run = async () => {
    global.fetch = async () => ({
        ok: true,
        json: async () => validImage,
    });
    assert.deepStrictEqual(await fetchImageInfo('/admin/', 42), validImage);

    let parsedNotFoundResponse = false;
    global.fetch = async () => ({
        ok: false,
        json: async () => {
            parsedNotFoundResponse = true;
            return { message: 'Not found' };
        },
    });
    assert.strictEqual(await fetchImageInfo('/admin/', 42), null);
    assert.strictEqual(parsedNotFoundResponse, false);

    global.fetch = async () => ({
        ok: true,
        json: async () => ({ message: 'Unexpected response' }),
    });
    assert.strictEqual(await fetchImageInfo('/admin/', 42), null);

    global.fetch = async () => {
        throw new Error('Network failure');
    };
    assert.strictEqual(await fetchImageInfo('/admin/', 42), null);
};

run()
    .finally(() => {
        global.fetch = originalFetch;
    })
    .catch((error) => {
        process.stderr.write(`${error.stack || error}\n`);
        process.exitCode = 1;
    });
