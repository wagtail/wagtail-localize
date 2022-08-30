import React, { FunctionComponent } from 'react';

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
}

const ActionMenu: FunctionComponent<ActionMenuProps> = ({
    defaultAction,
    actions
}) => {
    const wrappedActions = actions.map(action => <li>{action}</li>);

    return (
        <nav aria-label="Actions">
            <ul>
                <li className="actions actions--primary">
                    <div className="dropdown dropup dropdown-button match-width ">
                        {defaultAction}

                        <div className="dropdown-toggle">
                            <svg
                                className="icon icon-arrow-up icon"
                                aria-hidden="true"
                                focusable="false"
                            >
                                <use href="#icon-arrow-up"></use>
                            </svg>
                        </div>
                        <ul>{wrappedActions}</ul>
                    </div>
                </li>
            </ul>
        </nav>
    );
};

export default ActionMenu;
