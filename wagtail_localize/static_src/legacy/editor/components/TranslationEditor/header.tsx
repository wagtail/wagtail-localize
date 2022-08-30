import React, { FunctionComponent } from 'react';
import gettext from 'gettext';

import Avatar from '../../../common/components/Avatar';

import Header, {
    HeaderLinkAction,
    HeaderMeta
} from '../../../common/components/Header';

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
    targetLocale
}) => {
    // Render source
    const sourceTranslation = translations
        .filter(({ locale }) => locale.code == sourceLocale.code)
        .pop();
    let sourceRendered =
        sourceTranslation && sourceTranslation.editUrl ? (
            <a
                href={sourceTranslation.editUrl}
                className="button button-small button-nobg text-notransform"
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
                href: editUrl
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
        <li className={`header-meta--${name}`}>
            {sourceRendered}
            <Icon name="arrow-right" />
            {targetRendered}
        </li>
    );
};

interface EditorHeaderProps extends EditorProps, EditorState {}

const EditorHeader: FunctionComponent<EditorHeaderProps> = ({
    object,
    breadcrumb,
    sourceLocale,
    locale,
    translations,
    stringTranslations
}) => {
    // Build actions
    let actions = [];
    if (object.isLive && object.liveUrl) {
        actions.push(
            <HeaderLinkAction
                key="live"
                label={gettext('Live')}
                href={object.liveUrl}
                classes={['button-nostroke button--live']}
                icon="link-external"
            />
        );
    }

    let status = <></>;
    if (object.isLive) {
        if (object.lastPublishedDate) {
            status = <>{gettext('Published on ') + object.lastPublishedDate}</>;
        } else {
            status = <>{gettext('Published')}</>;
        }

        if (object.lastPublishedBy && object.lastPublishedBy.avatar_url) {
            status = (
                <>
                    <Avatar
                        username={object.lastPublishedBy.full_name}
                        avatarUrl={object.lastPublishedBy.avatar_url}
                    />
                    {status}
                </>
            );
        }
    } else {
        status = <>{gettext('Draft')}</>;
    }

    // Meta
    let meta = [
        <HeaderMeta key="status" name="status" value={status} />,
        <LocaleMeta
            key="locales"
            name="locales"
            translations={translations}
            sourceLocale={sourceLocale}
            targetLocale={locale}
        />
    ];

    // Title
    // Allow the title to be overridden by the segment that represents the "title" field on Pages.
    let title = object.title;
    if (object.titleSegmentId) {
        Array.from(stringTranslations.entries()).forEach(
            ([segmentId, stringTranslation]) => {
                if (segmentId == object.titleSegmentId) {
                    title = stringTranslation.value;
                }
            }
        );
    }

    return (
        <Header
            title={title}
            breadcrumb={breadcrumb}
            actions={actions}
            meta={meta}
            merged={true}
            tabbed={true}
        />
    );
};

export default EditorHeader;
