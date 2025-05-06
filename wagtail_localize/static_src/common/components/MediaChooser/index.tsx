import React, { FunctionComponent } from 'react';
import gettext from 'gettext';

interface MediaAPI {
    result: {
        id: number
        title: string;
        edit_url: string;
    };
}

interface MediaChooserProps {
    adminBaseUrl: string;
    mediaId: number | null;
}

const MediaChooser: FunctionComponent<MediaChooserProps> = ({
    adminBaseUrl,
    mediaId,
}) => {
    const [mediaInfo, setMediaInfo] = React.useState<MediaAPI | null>(null);

    React.useEffect(() => {
        setMediaInfo(null);
        if (mediaId) {
            fetch(`${adminBaseUrl}media/chooser/${mediaId}/`)
                .then((response) => response.json())
                .then(setMediaInfo);
        }
    }, [mediaId]);

    // Render
    let classNames = ['chooser', 'media-chooser'];
    let inner;
    if (mediaId) {
        if (mediaInfo) {
            inner = (
                <div className="chosen">
                    <div className="preview-media">
                        <strong>{mediaInfo.result.title} (ID: {mediaInfo.result.id})</strong>
                    </div>

                    <ul className="actions" style={{ listStyleType: 'none' }}>
                        <li>
                            <a
                                href={`${mediaInfo.result.edit_url}`}
                                className="edit-link button button-small button-secondary"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                {gettext('Edit this media')}
                            </a>
                        </li>
                    </ul>
                </div>
            );
        } else {
            inner = <p>{gettext('Fetching media information...')}</p>;
        }
    } else {
        classNames.push('blank');

        inner = (
            <div className="unchosen">
                <button
                    type="button"
                    className="button action-choose button-small button-secondary"
                >
                    {gettext('Choose a media')}
                </button>
            </div>
        );
    }

    return <div className={classNames.join(' ')}>{inner}</div>;
};

export default MediaChooser;
