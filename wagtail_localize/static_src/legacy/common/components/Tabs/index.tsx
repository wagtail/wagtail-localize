import React, { FunctionComponent } from 'react';
import styled from 'styled-components';

const CurrentTabContext = React.createContext<string>('');

export interface Tab {
    label: string;
    slug: string;
    numErrors?: number;
}

export interface TabsProps {
    tabs: Tab[];
}

// Remove bottom margin that Wagtail adds by default
// This makes it tricky to align the toolbox consistently when there are both tabs and no tabs
const StyledTabs = styled.ul`
    margin-bottom: 0;
    margin-top: 0;
    background-color: var(--color-primary);

    > li {
        list-style-type: none;
        width: 33%;
        float: left;
        padding: 0;
        position: relative;
        margin-right: 2px;

        @media screen and (min-width: 50em) {
            width: auto;
            padding: 0;
        }

        &:first-of-type {
            margin-left: 0;
        }

        > a {
            background-color: var(--color-primary-darker);
            text-transform: uppercase;
            font-weight: 600;
            text-decoration: none;
            display: block;
            padding: 0.6em 0.7em 0.8em;
            color: #fff;
            border-top: 0.3em solid var(--color-primary-darker);
            max-height: 1.44em;
            overflow: hidden;

            @media screen and (min-width: 50em) {
                padding-left: 20px;
                padding-right: 20px;
            }
        }

        &.active > a {
            box-shadow: none;
            color: #333;
            background-color: #fff;
            border-top: 0.3em solid #333;
        }
    }

    &:before,
    &:after {
        content: ' ';
        display: table;
    }

    &:after {
        clear: both;
    }
`;

export const Tabs: FunctionComponent<TabsProps> = ({ tabs, children }) => {
    const [currentTab, setCurrentTab] = React.useState(tabs[0].slug);

    return (
        <>
            <StyledTabs className="tab-nav merged" role="tablist">
                {tabs.map(tab => {
                    const onClick = (
                        e: React.MouseEvent<HTMLAnchorElement>
                    ) => {
                        e.preventDefault();
                        setCurrentTab(tab.slug);
                    };

                    const classNames = [];

                    if (tab.slug === currentTab) {
                        classNames.push('active');
                    }

                    if (tab.numErrors) {
                        classNames.push('errors');
                    }

                    return (
                        <li
                            key={tab.slug}
                            className={tab.slug == currentTab ? 'active' : ''}
                            role="tab"
                            aria-controls={`tab-${tab.slug}`}
                        >
                            <a
                                href={`#tab-${tab.slug}`}
                                onClick={onClick}
                                className={classNames.join(' ')}
                                data-count={tab.numErrors || 0}
                            >
                                {tab.label}
                            </a>
                        </li>
                    );
                })}
            </StyledTabs>
            <div className="tab-content">
                <CurrentTabContext.Provider value={currentTab}>
                    {children}
                </CurrentTabContext.Provider>
            </div>
        </>
    );
};

// Remove top padding that Wagtail adds by default
// This makes it tricky to align the toolbox consistently when there are both tabs and no tabs
const SectionWithoutPadding = styled.section`
    padding-top: 0 !important;
`;

export const TabContent: FunctionComponent<Tab> = ({ slug, children }) => {
    const currentTab = React.useContext(CurrentTabContext);

    return (
        <SectionWithoutPadding
            id={`tab-${slug}`}
            className={slug === currentTab ? 'active' : ''}
            hidden={slug !== currentTab}
        >
            {children}
        </SectionWithoutPadding>
    );
};
