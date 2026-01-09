import React, { FunctionComponent } from 'react';
import gettext from 'gettext';

import Icon from '../../../common/components/Icon';
import ActionMenu from '../../../common/components/ActionMenu';

import { EditorProps } from '.';

const EditorFooter: FunctionComponent<EditorProps> = ({
    csrfToken,
    object: { isLocked },
    perms,
    links,
    previewModes,
    locale,
}) => {
    let actions = [
        <button
            type="submit"
            className="button button-longrunning action-secondary"
            data-controller="w-progress w-action"
            data-action="w-progress#activate w-action#post"
            data-w-progress-active-value={gettext(
                'Stopping Synced translation'
            )}
            data-w-action-url-value={links.stopTranslationUrl}
        >
            <Icon name="cross" />
            <em data-w-progress-target="label">
                {gettext('Stop Synced translation')}
            </em>
        </button>,
    ];

    if (links.convertToAliasUrl) {
        actions.push(
            <a
                className="button action-secondary"
                href={`${links.convertToAliasUrl}?next=${window.location.href}`}
            >
                <Icon name="wagtail-localize-convert" />
                {gettext('Convert to alias page')}
            </a>
        );
    }

    if (perms.canDelete) {
        actions.push(
            <a className="button action-secondary" href={links.deleteUrl}>
                <Icon name="bin" />
                {gettext('Delete')}
            </a>
        );
    }

    if (perms.canLock && !isLocked) {
        actions.push(
            <button
                type="submit"
                className="button button-longrunning action-secondary"
                data-controller="w-progress w-action"
                data-action="w-progress#activate w-action#post"
                data-w-progress-active-value={gettext('Applying editor lock')}
                data-w-action-url-value={links.lockUrl}
            >
                <Icon name="lock" />
                <em data-w-progress-target="label">{gettext('Lock')}</em>
            </button>
        );
    }

    if (perms.canUnlock && isLocked) {
        actions.push(
            <button
                type="submit"
                className="button button-longrunning action-secondary"
                data-controller="w-progress w-action"
                data-action="w-progress#activate w-action#post"
                data-w-progress-active-value={gettext('Removing editor lock')}
                data-w-action-url-value={links.unlockUrl}
            >
                <Icon name="lock-open" />
                <em data-w-progress-target="label">{gettext('Unlock')}</em>
            </button>
        );
    }

    if (perms.canUnpublish) {
        actions.push(
            <a className="button action-secondary" href={links.unpublishUrl}>
                <Icon name="download" />
                {gettext('Unpublish')}
            </a>
        );
    }

    if (perms.canPublish) {
        actions.push(
            <form method="POST">
                <input
                    type="hidden"
                    name="csrfmiddlewaretoken"
                    value={csrfToken}
                />
                <input type="hidden" name="next" value={window.location.href} />

                <button
                    type="submit"
                    name="action"
                    value="publish"
                    className="button button-longrunning"
                    data-clicked-text={gettext('Publishing...')}
                    data-controller="w-progress"
                    data-action="w-progress#activate"
                    data-w-progress-active-value={gettext('Publishing...')}
                >
                    <Icon
                        name="upload"
                        className={'button-longrunning__icon'}
                    />
                    <Icon name="spinner" />
                    <em data-w-progress-target="label">
                        {gettext('Publish in ') + locale.displayName}
                    </em>
                </button>
            </form>
        );
    }

    // Make last action the default
    const defaultAction = actions.pop();

    return (
        <footer className="footer w-grid md:w-grid-flow-col">
            <ActionMenu
                defaultAction={defaultAction}
                actions={actions}
                previewModes={previewModes}
            />
        </footer>
    );
};

export default EditorFooter;
