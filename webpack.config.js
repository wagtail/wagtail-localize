/* eslint @typescript-eslint/no-var-requires: "off" */
const path = require('path');

module.exports = {
    entry: './wagtail_localize/static_src/main.tsx',
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: 'ts-loader',
                exclude: /node_modules/
            },
            {
                test: /\.css$/,
                use: ['style-loader', 'css-loader']
            },
            {
                test: /\.svg$/,
                use: ['@svgr/webpack']
            },
            {
                test: /\.(png|jpg|gif)$/,
                use: ['file-loader']
            }
        ]
    },
    resolve: {
        extensions: ['.tsx', '.ts', '.js']
    },
    externals: {
        /* These are provided by Wagtail */
        react: 'React',
        'react-dom': 'ReactDOM',
        gettext: 'gettext'
    },
    output: {
        path: path.resolve(
            __dirname,
            'wagtail_localize/static/wagtail_localize/js'
        ),
        filename: 'wagtail-localize.js'
    }
};
