import React, { FunctionComponent } from 'react';
import styled from 'styled-components';

const Title = styled.div`
    box-sizing: border-box;
    height: 40px;
    -webkit-font-smoothing: auto;
    background: #fcf2f2;
    color: #200200;
    text-transform: uppercase;
    padding: 0.9em 0 0.9em 5em;
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

    &::before {
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        text-shadow: none;
        font-family: wagtail;
        text-transform: none;
        content: '';
        text-align: center;
        display: block;
        position: absolute;
        z-index: 2;
        font-size: 2em;
        top: 0;
        line-height: 1.8em;
        left: 0;
        width: 50px;
        color: #fff;
        padding: 0;
        margin: 0;
        background-color: #f37e77;
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
