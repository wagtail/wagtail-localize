import React, { FunctionComponent } from 'react';

declare var $: any;

interface AvatarProps {
    username: string;
    avatarUrl: string;
}

const Avatar: FunctionComponent<AvatarProps> = ({ username, avatarUrl }) => {
    const ref = React.useRef<HTMLSpanElement>(null);

    React.useEffect(() => {
        // Activate tooltip
        if (ref.current) {
            $(ref.current).tooltip({
                animation: false,
                title: function() {
                    return username;
                },
                trigger: 'hover',
                placement: 'bottom'
            });
        }
    }, [ref]);

    return (
        <span ref={ref} className="avatar small">
            <img src={avatarUrl} alt={username} />
        </span>
    );
};

export default Avatar;
