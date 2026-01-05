/* eslint @typescript-eslint/no-var-requires: "off" */
const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');

module.exports = {
    entry: {
        main: './wagtail_localize/static_src/main.tsx',
        'component-form':
            './wagtail_localize/static_src/component_form/main.tsx',
    },
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: 'ts-loader',
                exclude: /node_modules/,
            },
            {
                test: /\.css$/,
                use: ['style-loader', 'css-loader'],
            },
            {
                test: /\.svg$/,
                use: ['@svgr/webpack'],
            },
            {
                test: /\.(png|jpg|gif)$/,
                use: ['file-loader'],
            },
        ],
    },
    resolve: {
        extensions: ['.tsx', '.ts', '.js'],
    },
    plugins: [
        new CopyPlugin({
            patterns: [
                {
                    from: path.resolve(
                        __dirname,
                        'wagtail_localize/static_src/component_form',
                        'main.css',
                    ),
                    to: path.resolve(
                        __dirname,
                        'wagtail_localize/static/wagtail_localize/css',
                        'wagtail-localize-component-form.css',
                    ),
                },
                {
                    from: path.resolve(
                        __dirname,
                        'wagtail_localize/static_src/editor',
                        'main.css',
                    ),
                    to: path.resolve(
                        __dirname,
                        'wagtail_localize/static/wagtail_localize/css',
                        'wagtail-localize-editor-form.css',
                    ),
                },
            ],
        }),
    ],
    externals: {
        /* These are provided by Wagtail */
        react: 'React',
        'react-dom': 'ReactDOM',
        gettext: 'gettext',
    },
    output: {
        path: path.resolve(
            __dirname,
            'wagtail_localize/static/wagtail_localize/js',
        ),
        filename: (pathData) => {
            return pathData.chunk.name === 'main'
                ? 'wagtail-localize.js'
                : 'wagtail-localize-[name].js';
        },
    },
};
