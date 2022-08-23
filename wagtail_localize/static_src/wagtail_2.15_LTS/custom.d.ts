declare module '*.svg' {
    const content: any;
    export default content;
}

declare module 'gettext' {
    export default function gettext(text: string): string;
}
