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

export const Tabs: FunctionComponent<TabsProps> = ({ tabs, children }) => {
    const [currentTab, setCurrentTab] = React.useState(tabs[0].slug);

    return (
        <div className="w-tabs">
            <div className="w-tabs__wrapper">
                <div className="w-tabs__list" role="tablist">
                    {tabs.map((tab) => {
                        const onClick = (
                            e: React.MouseEvent<HTMLAnchorElement>,
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
                            <a
                                data-count={tab.numErrors || 0}
                                onClick={onClick}
                                aria-selected={tab.slug == currentTab}
                                className="w-tabs__tab"
                                href={`#tab-${tab.slug}`}
                                id={`tab-label-${tab.slug}`}
                                role="tab"
                                aria-controls={`tab-${tab.slug}`}
                            >
                                {tab.label}
                            </a>
                        );
                    })}
                </div>
            </div>
            <div className="tab-content">
                <CurrentTabContext.Provider value={currentTab}>
                    <section
                        aria-labelledby={`tab-label-${currentTab}`}
                        id={`tab-${currentTab}`}
                        role="tabpanel"
                    >
                        {children}
                    </section>
                </CurrentTabContext.Provider>
            </div>
        </div>
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
