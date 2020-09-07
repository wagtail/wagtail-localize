import React, { FunctionComponent } from 'react';
import Icon from '../Icon';
import gettext from 'gettext';

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
    icon
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
    icon
}) => {
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

interface HeaderMetaProps {
    name: string;
    value: string | React.ReactFragment;
    icon?: string;
}

export const HeaderMeta: FunctionComponent<HeaderMetaProps> = ({
    name,
    value,
    icon
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
    classes
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
    title: string;
    subtitle?: string;
    breadcrumb?: BreadcrumbItem[];
    icon?: string;
    merged?: boolean;
    tabbed?: boolean;
    actions?: React.ReactNode;
    meta?: React.ReactNode;
}

const Header: FunctionComponent<HeaderProps> = ({
    title,
    subtitle,
    breadcrumb,
    icon,
    merged,
    tabbed,
    actions,
    meta
}) => {
    let classNames = [];
    let rowClassNames = ['row'];

    if (merged) {
        classNames.push('merged');
    }

    if (tabbed) {
        classNames.push('tab-merged');
    } else {
        rowClassNames.push('nice-padding');
    }

    // Wrap subtitle with <span>
    let subtitleWrapped = <></>;
    if (subtitle) {
        subtitleWrapped = <span>{subtitle}</span>;
    }

    let breadcrumbRendered = <></>;
    if (breadcrumb && breadcrumb.length > 0) {
        let breadcrumbFirst = true;
        breadcrumbRendered = (
            <nav aria-label={gettext('Breadcrumb')}>
                <ul className="breadcrumb">
                    {breadcrumb.map(page => {
                        const isFirst = breadcrumbFirst;
                        breadcrumbFirst = false;

                        if (page.isRoot) {
                            // Root section is shown as a 'site' icon in place of the title
                            return (
                                <li key={page.id} className="home">
                                    <a
                                        href={page.exploreUrl}
                                        className="icon icon-site text-replace"
                                    >
                                        {page.title}
                                    </a>
                                </li>
                            );
                        } else if (isFirst) {
                            // For limited-permission users whose breadcrumb starts further down from the root, the first item displays as a 'home' icon in place of the title
                            return (
                                <li key={page.id} className="home">
                                    <a
                                        href={page.exploreUrl}
                                        className="icon icon-home text-replace"
                                    >
                                        {page.title}
                                    </a>
                                </li>
                            );
                        } else {
                            return (
                                <li key={page.id}>
                                    <a href={page.exploreUrl}>{page.title}</a>
                                </li>
                            );
                        }
                    })}
                </ul>
            </nav>
        );
    }

    return (
        <header className={classNames.join(' ')}>
            {breadcrumbRendered}
            <div className={rowClassNames.join(' ')}>
                <h1
                    className="left col header-title"
                    style={{ textTransform: 'none' }}
                >
                    {' '}
                    {/* TODO: Move style */}
                    {icon && <Icon name={icon} />}
                    {title} {subtitleWrapped}
                </h1>
                <div className="right">{actions}</div>
            </div>
            <ul className="row header-meta">{meta}</ul>
        </header>
    );
};

export default Header;
