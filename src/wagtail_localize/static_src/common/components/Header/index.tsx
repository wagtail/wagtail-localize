import React, { FunctionComponent } from 'react';
import Icon from '../Icon';
import styled from 'styled-components';

const StyledButtonLink = styled.a`
    &.button--live {
        background-color: #fff;
        color: var(--w-color--primary);
        border-radius: 2px;
        font-size: 14px;
        font-weight: 600;
        line-height: 2.3em;
        padding: 0 0.75em;

        .icon {
            width: 1.25em;
            height: 1.25em;
            vertical-align: text-top;
            margin-right: 0.25em;
        }
    }
`;

interface HeaderButtonActionProps {
    label: string;
    onClick: () => void;
    title?: string;
    classes?: string[];
    icon?: string;
}

export const HeaderButtonAction: FunctionComponent<HeaderButtonActionProps> = ({
    label,
    onClick,
    title,
    classes,
    icon,
}) => {
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

interface HeaderLinkActionProps {
    label: string;
    href: string;
    title?: string;
    classes?: string[];
    icon?: string;
}

export const HeaderLinkAction: FunctionComponent<HeaderLinkActionProps> = ({
    label,
    href,
    title,
    classes,
    icon,
}) => {
    let classNames = ['button'];

    if (classes) {
        classNames = classNames.concat(classes);
    }

    return (
        <StyledButtonLink
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className={classNames.join(' ')}
            title={title}
        >
            {icon && <Icon name={icon} />} {label}
        </StyledButtonLink>
    );
};

interface HeaderMetaProps {
    name: string;
    value: string | React.ReactFragment;
    icon?: string;
}

export const HeaderMeta: FunctionComponent<HeaderMetaProps> = ({
    name,
    value,
    icon,
}) => {
    return (
        <li className={`header-meta--${name}`}>
            {icon && <Icon name={icon} />} {value}
        </li>
    );
};

interface HeaderDropdownLinkOption {
    label: string;
    href: string;
}

interface HeaderMetaDropdownProps {
    name: string;
    label: string;
    options: HeaderDropdownLinkOption[];
    icon?: string;
    title?: string;
    classes?: string[];
}

export const HeaderMetaDropdown: FunctionComponent<HeaderMetaDropdownProps> = ({
    name,
    label,
    options,
    icon,
    title,
    classes,
}) => {
    let classNames = ['c-dropdown', 't-inverted'];

    if (classes) {
        classNames = classNames.concat(classes);
    }

    let items = options.map(({ label, href }) => {
        return (
            <li key={href} className="c-dropdown__item ">
                <a href={href} aria-label="" className="u-link is-live">
                    {label}
                </a>
            </li>
        );
    });

    return (
        <HeaderMeta
            name={name}
            icon={icon}
            value={
                <div
                    className={classNames.join(' ')}
                    data-dropdown=""
                    style={{ display: 'inline-block' }}
                >
                    <a
                        href="javascript:void(0)"
                        aria-label={title}
                        className="c-dropdown__button u-btn-current"
                    >
                        {label}
                        <div
                            data-dropdown-toggle=""
                            className="o-icon c-dropdown__toggle c-dropdown__togle--icon [ icon icon-arrow-down ]"
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
            }
        />
    );
};

export interface BreadcrumbItem {
    id: number;
    isRoot: boolean;
    title: string;
    exploreUrl: string;
}

interface HeaderProps {
    meta?: React.ReactNode;
}

const Header: FunctionComponent<HeaderProps> = ({ meta }) => {
    return (
        <div>
            <ul className="row header-meta w-list-none">{meta}</ul>
        </div>
    );
};

export default Header;
