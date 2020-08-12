import React, { FunctionComponent } from 'react';
import gettext from 'gettext';

import Avatar from '../../../common/components/Avatar';

import Header, {
    HeaderLinkAction,
    HeaderMeta,
    HeaderMetaDropdown
} from '../../../common/components/Header';

import { EditorProps } from '.';
import { EditorState } from './reducer';

interface EditorHeaderProps extends EditorProps, EditorState {}

const EditorHeader: FunctionComponent<EditorHeaderProps> = ({
    object,
    breadcrumb,
    sourceLocale,
    locale,
    translations
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

        if (object.lastPublishedBy) {
            status = <>
                <Avatar username={object.lastPublishedBy.full_name} avatarUrl={object.lastPublishedBy.avatar_url} />
                {status}
            </>;
        }
    } else {
        status = <>{gettext('Draft')}</>;
    }

    // Build meta
    let meta = [
        <HeaderMeta key="status" value={status} />,
        <HeaderMeta key="source-locale" value={sourceLocale.displayName} />
    ];

    let translationOptions = translations
        .filter(({ locale }) => locale.code != sourceLocale.code)
        .map(({ locale, editUrl }) => {
            return {
                label: locale.displayName,
                href: editUrl
            };
        });

    if (translationOptions.length > 0) {
        meta.push(
            <HeaderMetaDropdown
                key="target-locale"
                label={locale.displayName}
                icon="arrow-right"
                options={translationOptions}
            />
        );
    } else {
        meta.push(
            <HeaderMeta
                key="target-locale"
                icon="arrow-right"
                value={locale.displayName}
            />
        );
    }

    return (
        <Header
            title={object.title}
            breadcrumb={breadcrumb}
            actions={actions}
            meta={meta}
            merged={true}
            tabbed={true}
        />
    );
};

export default EditorHeader;
