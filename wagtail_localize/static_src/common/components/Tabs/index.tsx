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
const ULWithoutMargin = styled.ul`
    margin-bottom: 0;
`;

export const Tabs: FunctionComponent<TabsProps> = ({ tabs, children }) => {
    const [currentTab, setCurrentTab] = React.useState(tabs[0].slug);

    return (
        <>
            <ULWithoutMargin className="tab-nav merged" role="tablist">
                {tabs.map(tab => {
                    const onClick = (
                        e: React.MouseEvent<HTMLAnchorElement>
                    ) => {
                        e.preventDefault();
                        setCurrentTab(tab.slug);
                    };

                    const classNames = [];

                    if (tab.slug == currentTab) {
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
            </ULWithoutMargin>
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
            className={slug == currentTab ? 'active' : ''}
        >
            {children}
        </SectionWithoutPadding>
    );
};
