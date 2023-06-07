import React, { FunctionComponent } from 'react';

import { EditorProps, Locale, Translation } from '.';
import { EditorState } from './reducer';
import Icon from '../../../common/components/Icon';

interface LocaleMetaProps {
    name: string;
    sourceLocale: Locale;
    targetLocale: Locale;
    translations: Translation[];
}

const LocaleMeta: FunctionComponent<LocaleMetaProps> = ({
    name,
    translations,
    sourceLocale,
    targetLocale,
}) => {
    // Render source
    const sourceTranslation = translations
        .filter(({ locale }) => locale.code == sourceLocale.code)
        .pop();
    let sourceRendered =
        sourceTranslation && sourceTranslation.editUrl ? (
            <a
                href={sourceTranslation.editUrl}
                // className="page-status-tag u-text-uppercase w-inline-flex w-items-center w-justify-center w-whitespace-nowrap w-px-1 w-ml-3 w-text-[0.6875rem] w-rounded-sm w-bg-transparent w-text-grey-400 w-border w-border-grey-100 w-no-underline w-font-semibold hover:w-border-primary hover:w-text-primary w-transition"
            >
                {sourceLocale.displayName}
            </a>
        ) : (
            <>{sourceLocale.displayName}</>
        );

    // Render target
    let targetRendered = <></>;

    let translationOptions = translations
        .filter(({ locale }) => locale.code != sourceLocale.code)
        .map(({ locale, editUrl }) => {
            return {
                label: locale.displayName,
                href: editUrl,
            };
        });

    if (translationOptions.length > 0) {
        let items = translationOptions.map(({ label, href }) => {
            return (
                <li className="c-dropdown__item ">
                    <a href={href} aria-label="" className="u-link is-live">
                        {label}
                    </a>
                </li>
            );
        });

        targetRendered = (
            <div
                className="c-dropdown t-inverted"
                data-dropdown=""
                style={{ display: 'inline-block' }}
            >
                <a
                    href="javascript:void(0)"
                    className="c-dropdown__button u-btn-current button button-small button-nobg text-notransform"
                >
                    {targetLocale.displayName}
                    <div
                        data-dropdown-toggle=""
                        className="o-icon c-dropdown__toggle c-dropdown__togle--icon [ icon icon-arrow-down ]"
                        style={{ paddingLeft: '5px' }}
                    >
                        <Icon name="arrow-down" />
                        <Icon name="arrow-up" />
                    </div>
                </a>
                <div className="t-dark">
                    <ul className="c-dropdown__menu u-toggle  u-arrow u-arrow--tl u-background">
                        {items}
                    </ul>
                </div>
            </div>
        );
    } else {
        targetRendered = <>{targetLocale.displayName}</>;
    }

    return (
        <div
            className={`w-p-4 header-meta--${name} w-flex w-flex-row w-items-center`}
        >
            {sourceRendered}
            <svg
                aria-hidden="true"
                className="icon icon-arrow-right w-w-4 w-h-4"
            >
                <use href="#icon-arrow-right"></use>
            </svg>
            {targetRendered}
        </div>
    );
};

interface EditorHeaderProps extends EditorProps, EditorState {}

const EditorHeader: FunctionComponent<EditorHeaderProps> = ({
    sourceLocale,
    locale,
    translations,
}) => {
    return (
        <header className="w-flex w-flex-col sm:w-flex-row w-items-center w-justify-between w-border-b w-border-grey-100 w-px-0 w-py-0 w-mb-0 w-relative w-top-0 sm:w-sticky w-min-h-slim-header">
            <div className="w-pl-slim-header w-min-h-slim-header sm:w-pl-5 sm:w-pr-2 w-w-full w-flex-1 w-overflow-x-auto w-box-border">
                <div className="w-flex w-flex-1 w-items-center w-overflow-hidden w-h-slim-header">
                    <LocaleMeta
                        key="locales"
                        name="locales"
                        translations={translations}
                        sourceLocale={sourceLocale}
                        targetLocale={locale}
                    />
                </div>
            </div>
        </header>
    );
};

export default EditorHeader;
