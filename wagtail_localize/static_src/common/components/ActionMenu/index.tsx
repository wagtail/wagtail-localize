import React, { FunctionComponent } from 'react';
import gettext from 'gettext';

import Icon from '../Icon';

interface ActionMenuButtonActionProps {
    label: string;
    onClick: () => void;
    title?: string;
    classes?: string[];
    icon?: string;
}

export const ActionMenuButtonAction: FunctionComponent<
    ActionMenuButtonActionProps
> = ({ label, onClick, title, classes, icon }) => {
    let classNames = ['button'];

    if (classes) {
        classNames = classNames.concat(classes);
    }

    return (
        <button
            className={classNames.join(' ')}
            title={title}
            onClick={onClick}
        >
            {icon && <Icon name={icon} />} {label}
        </button>
    );
};

interface ActionMenuLinkActionProps {
    label: string;
    href: string;
    title?: string;
    classes?: string[];
    icon?: string;
}

export const ActionMenuLinkAction: FunctionComponent<
    ActionMenuLinkActionProps
> = ({ label, href, title, classes, icon }) => {
    let classNames = ['button'];

    if (classes) {
        classNames = classNames.concat(classes);
    }

    return (
        <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className={classNames.join(' ')}
            title={title}
        >
            {icon && <Icon name={icon} />} {label}
        </a>
    );
};

export interface PreviewMode {
    mode: string;
    label: string;
    url: string;
}

interface ActionMenuProps {
    defaultAction: React.ReactNode;
    actions: React.ReactNode[];
    previewModes?: PreviewMode[];
}

const ActionMenu: FunctionComponent<ActionMenuProps> = ({
    defaultAction,
    actions,
    previewModes,
}) => {
    return (
        <nav
            className="actions actions--primary footer__container"
            aria-label={gettext('Actions')}
        >
            <div className="w-dropdown-button">
                <button
                    type="submit"
                    className="button action-save button-longrunning "
                    data-controller="w-progress"
                    data-action="w-progress#activate"
                    data-w-progress-active-value="Saving…"
                >
                    <svg
                        className="icon icon-draft button-longrunning__icon"
                        aria-hidden="true"
                    >
                        <use href="#icon-draft"></use>
                    </svg>
                    <svg className="icon icon-spinner icon" aria-hidden="true">
                        <use href="#icon-spinner"></use>
                    </svg>
                    <em data-w-progress-target="label">{defaultAction}</em>
                </button>

                <div
                    data-controller="w-dropdown"
                    className="w-dropdown w-dropdown--dropdown-button"
                    data-w-dropdown-theme-value="dropdown-button"
                    data-w-dropdown-offset-value="[0, 0]"
                >
                    <button
                        type="button"
                        className="w-dropdown__toggle button"
                        data-w-dropdown-target="toggle"
                    >
                        <span className="w-sr-only">More actions</span>
                        <svg
                            className="icon icon-arrow-up w-dropdown__toggle-icon"
                            aria-hidden="true"
                        >
                            <use href="#icon-arrow-up"></use>
                        </svg>
                    </button>

                    <div
                        data-w-dropdown-target="content"
                        className="w-dropdown__content"
                        hidden
                    >
                        {actions}
                    </div>
                </div>
            </div>

            {/* Single-mode preview */}
            {previewModes && previewModes.length == 1 && (
                <div className="w-dropdown-button">
                    <a
                        className="button button--icon"
                        href={previewModes[0].url}
                        target="_blank"
                    >
                        <svg
                            className="icon icon-view"
                            aria-hidden="true"
                            focusable="false"
                        >
                            <use href="#icon-view"></use>
                        </svg>
                        {gettext('Preview')}
                    </a>
                </div>
            )}
            {/* Multi-mode preview */}
            {previewModes && previewModes.length > 1 && (
                <div className="w-dropdown-button">
                    <a
                        className="button button--icon"
                        href={previewModes[0].url}
                        target="_blank"
                    >
                        <svg
                            className="icon icon-view"
                            aria-hidden="true"
                            focusable="false"
                        >
                            <use href="#icon-view"></use>
                        </svg>
                        {gettext('Preview')}
                    </a>
                    <div
                        data-controller="w-dropdown"
                        className="w-dropdown w-dropdown--dropdown-button"
                        data-w-dropdown-theme-value="dropdown-button"
                        data-w-dropdown-offset-value="[0, 0]"
                    >
                        <button
                            type="button"
                            className="w-dropdown__toggle button"
                            data-w-dropdown-target="toggle"
                        >
                            <span className="w-sr-only">More actions</span>
                            <svg
                                className="icon icon-arrow-up w-dropdown__toggle-icon"
                                aria-hidden="true"
                            >
                                <use href="#icon-arrow-up"></use>
                            </svg>
                        </button>

                        <div
                            data-w-dropdown-target="content"
                            className="w-dropdown__content"
                            hidden
                        >
                            {previewModes.map(({ label, url }) => {
                                return (
                                    <a
                                        className="button"
                                        href={url}
                                        target="_blank"
                                    >
                                        {label}
                                    </a>
                                );
                            })}
                        </div>
                    </div>
                </div>
            )}
        </nav>
    );
};

export default ActionMenu;
