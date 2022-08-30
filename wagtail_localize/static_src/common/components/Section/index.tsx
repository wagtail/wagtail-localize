import React, { FunctionComponent } from 'react';
import styled from 'styled-components';

const Title = styled.div`
    box-sizing: border-box;
    height: 40px;
    -webkit-font-smoothing: auto;
    background-color: var(--w-color-secondary-50);
    color: var(--w-color-secondary);
    text-transform: uppercase;
    padding: 0.9em 0 0.9em 95px;
    font-size: 0.95em;
    margin: 0;
    line-height: 1.5em;
    font-weight: 400;
    overflow: hidden;
    position: relative;

    > h3 {
        display: inline;
        text-transform: inherit;
        font-weight: inherit;
        float: none;
        color: inherit;
        font-size: inherit;
    }
`;

interface SectionProps {
    title: string;
}

const Section: FunctionComponent<SectionProps> = ({ title, children }) => {
    return (
        <section>
            <Title>
                <h3>{title}</h3>
            </Title>
            {children}
        </section>
    );
};

export default Section;
