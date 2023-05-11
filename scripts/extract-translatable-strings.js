// eslint-disable-next-line import/no-extraneous-dependencies
const { GettextExtractor, JsExtractors } = require('gettext-extractor');

const extractor = new GettextExtractor();

extractor
    .createJsParser([
        JsExtractors.callExpression('gettext', {
            arguments: {
                text: 0,
                context: 1,
            },
        }),
        JsExtractors.callExpression('ngettext', {
            arguments: {
                text: 1,
                textPlural: 2,
                context: 3,
            },
        }),
    ])
    .parseFilesGlob('./wagtail_localize/static_src/**/*.@(ts|js|tsx|jsx)');

extractor.savePotFile('wagtail_localize/locale/en/LC_MESSAGES/djangojs.po');

extractor.printStats();
