import React, { FunctionComponent } from 'react';

interface AvatarProps {
    username: string;
    avatarUrl: string;
}

const Avatar: FunctionComponent<AvatarProps> = ({username, avatarUrl}) => {
    return <span className="avatar small" data-wagtail-tooltip={username}>
        <img src={avatarUrl} alt={username} />
    </span>;
}

export default Avatar;
