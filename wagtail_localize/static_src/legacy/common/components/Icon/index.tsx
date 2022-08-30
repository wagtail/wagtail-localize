import React, { FunctionComponent } from 'react';

interface IconProps {
    name: string;
    className?: string;
    title?: string;
}

const Icon: FunctionComponent<IconProps> = ({ name, className, title }) => {
    return (
        <>
            <svg
                className={`icon icon-${name} ${className || ''}`}
                aria-hidden="true"
            >
                <use href={`#icon-${name}`}></use>
            </svg>
            {title ? <span className="visuallyhidden">{title}</span> : null}
        </>
    );
};

export default Icon;
