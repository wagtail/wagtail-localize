import React, { FunctionComponent } from 'react';

const CurrentTabContext = React.createContext<string>('');

export interface TabsProps {
    tabs: string[];
}

export const Tabs: FunctionComponent<TabsProps> = ({tabs, children}) => {
    const [currentTab, setCurrentTab] = React.useState(tabs[0])

    return <>
        <ul className="tab-nav merged" role="tablist">
            {tabs.map(tab => {
                const onClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
                    e.preventDefault();
                    setCurrentTab(tab);
                };

                return <li className={tab == currentTab ? 'active' : ''} role="tab" aria-controls={`tab-${tab.toLowerCase()}`}>
                    <a href={`#tab-${tab.toLowerCase()}`} onClick={onClick} className={tab == currentTab ? 'active' : ''}>{tab}</a>
                </li>
            })}
        </ul>
        <div className="tab-content">
            <CurrentTabContext.Provider value={currentTab}>
                {children}
            </CurrentTabContext.Provider>
        </div>
    </>;
}

export interface TabContentProps {
    tab: string,
}

export const TabContent: FunctionComponent<TabContentProps> = ({tab, children}) => {
    const currentTab = React.useContext(CurrentTabContext);

    return <section id={`tab-${tab.toLowerCase()}`} className={tab == currentTab ? 'active' : ''}>
        {children}
    </section>
}
