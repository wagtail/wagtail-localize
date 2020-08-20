import React, { FunctionComponent } from 'react';

const CurrentTabContext = React.createContext<string>('');

export interface Tab {
    label: string;
    numErrors?: number;
}

export interface TabsProps {
    tabs: Tab[];
}

export const Tabs: FunctionComponent<TabsProps> = ({tabs, children}) => {
    const [currentTab, setCurrentTab] = React.useState(tabs[0].label)

    return <>
        <ul className="tab-nav merged" role="tablist">
            {tabs.map(tab => {
                const onClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
                    e.preventDefault();
                    setCurrentTab(tab.label);
                };

                const classNames = [];

                if (tab.label == currentTab) {
                    classNames.push('active');
                }

                if (tab.numErrors) {
                    classNames.push('errors');
                }

                return <li className={tab.label == currentTab ? 'active' : ''} role="tab" aria-controls={`tab-${tab.label.toLowerCase()}`}>
                    <a href={`#tab-${tab.label.toLowerCase()}`} onClick={onClick} className={classNames.join(' ')} data-count={tab.numErrors || 0}>{tab.label}</a>
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

export const TabContent: FunctionComponent<Tab> = ({label, children}) => {
    const currentTab = React.useContext(CurrentTabContext);

    return <section id={`tab-${label.toLowerCase()}`} className={label == currentTab ? 'active' : ''}>
        {children}
    </section>
}
