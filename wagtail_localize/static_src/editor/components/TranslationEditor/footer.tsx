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
    locale
}) => {
    let actions = [
        <form method="POST" action={links.stopTranslationUrl}>
            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
            <input type="hidden" name="next" value={window.location.href} />

            <button
                type="submit"
                className="button action-secondary"
                aria-label={gettext('Stop Synced translation')}
            >
                <Icon name="cross" />
                {gettext('Stop Synced translation')}
            </button>
        </form>
    ];

    if (links.convertToAliasUrl) {
        actions.push(
            <form method="GET" action={links.convertToAliasUrl}>
                <input type="hidden" name="next" value={window.location.href} />

                <button
                    type="submit"
                    className="button action-secondary"
                    aria-label={gettext('Convert to alias page')}
                >
                    <Icon name="wagtail-localize-convert" />
                    {gettext('Convert to alias page')}
                </button>
            </form>
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
            <form method="POST" action={links.lockUrl}>
                <input
                    type="hidden"
                    name="csrfmiddlewaretoken"
                    value={csrfToken}
                />
                <input type="hidden" name="next" value={window.location.href} />

                <button
                    type="submit"
                    className="button action-secondary"
                    aria-label={gettext('Apply editor lock')}
                >
                    <Icon name="lock" />
                    {gettext('Lock')}
                </button>
            </form>
        );
    }

    if (perms.canUnlock && isLocked) {
        actions.push(
            <form method="POST" action={links.unlockUrl}>
                <input
                    type="hidden"
                    name="csrfmiddlewaretoken"
                    value={csrfToken}
                />
                <input type="hidden" name="next" value={window.location.href} />

                <button
                    type="submit"
                    className="button action-secondary"
                    aria-label={gettext('Remove editor lock')}
                >
                    <Icon name="lock-open" />
                    {gettext('Unlock')}
                </button>
            </form>
        );
    }

    if (perms.canUnpublish) {
        actions.push(
            <a className="button action-secondary" href={links.unpublishUrl}>
                <Icon name="download-alt" />
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
                    className="button button-longrunning "
                    data-clicked-text={gettext('Publishing...')}
                >
                    <Icon
                        name="upload"
                        className={'button-longrunning__icon'}
                    />
                    <Icon name="spinner" />
                    <em>{gettext('Publish in ') + locale.displayName}</em>
                </button>
            </form>
        );
    }

    // Make last action the default
    const defaultAction = actions.pop();

    // The markup for footers is slightly different when running Wagtail 2.13+
    if ((window as any).comments) {
        // Running Wagtail 2.13
        return (
            <footer className="footer">
                <ul>
                    <li className="footer__container">
                        <ActionMenu
                            defaultAction={defaultAction}
                            actions={actions}
                            previewModes={previewModes}
                        />
                    </li>
                </ul>
            </footer>
        );
    } else {
        return (
            <footer>
                <ActionMenu
                    defaultAction={defaultAction}
                    actions={actions}
                    previewModes={previewModes}
                />
            </footer>
        );
    }
};

export default EditorFooter;
