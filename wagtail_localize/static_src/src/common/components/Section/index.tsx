import React, { FunctionComponent } from 'react';

import './style.scss';

interface SectionProps {
    title: string;
}

const Section: FunctionComponent<SectionProps> = ({ title, children }) => {
    return (
        <section className="section">
            <div className="section__title">
                <h3>{title}</h3>
            </div>
            {children}
        </section>
    );
};

export default Section;
