/* eslint-disable react/prop-types */

import React, { FunctionComponent } from 'react';
// gettext is provided as a Wagtail runtime external.
// eslint-disable-next-line import/no-unresolved
import gettext from 'gettext';

// TypeScript resolves the directory's index module.
// eslint-disable-next-line import/extensions
import { fetchImageInfo, ImageAPI } from './api';

interface ImageChooserProps {
    adminBaseUrl: string;
    imageId: number | null;
}

const ImageChooser: FunctionComponent<ImageChooserProps> = ({
    adminBaseUrl,
    imageId,
}) => {
    const [imageInfo, setImageInfo] = React.useState<ImageAPI | null>(null);
    const [imageInfoUnavailable, setImageInfoUnavailable] =
        React.useState(false);

    React.useEffect(() => {
        let cancelled = false;

        setImageInfo(null);
        setImageInfoUnavailable(false);

        if (imageId) {
            fetchImageInfo(adminBaseUrl, imageId).then((image) => {
                if (!cancelled) {
                    setImageInfo(image);
                    setImageInfoUnavailable(image === null);
                }
            });
        }

        return () => {
            cancelled = true;
        };
    }, [adminBaseUrl, imageId]);

    // Render
    const classNames = ['chooser', 'image-chooser'];
    let inner;
    if (imageId) {
        if (imageInfoUnavailable) {
            inner = (
                <p>
                    {gettext('Image %s no longer exists.').replace(
                        '%s',
                        imageId.toString()
                    )}
                </p>
            );
        } else if (imageInfo) {
            inner = (
                <div className="chosen">
                    <div className="preview-image">
                        <img
                            alt={imageInfo.title}
                            className="show-transparency"
                            src={imageInfo.thumbnail.url}
                            title={imageInfo.title}
                            width={imageInfo.thumbnail.width}
                            height={imageInfo.thumbnail.height}
                        />
                    </div>

                    <ul className="actions" style={{ listStyleType: 'none' }}>
                        <li>
                            <a
                                href={`${adminBaseUrl}images/${imageInfo.id}/`}
                                className="edit-link button button-small button-secondary"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                {gettext('Edit this image')}
                            </a>
                        </li>
                    </ul>
                </div>
            );
        } else {
            inner = <p>{gettext('Fetching image information...')}</p>;
        }
    } else {
        classNames.push('blank');

        inner = (
            <div className="unchosen">
                <button
                    type="button"
                    className="button action-choose button-small button-secondary"
                >
                    {gettext('Choose an image')}
                </button>
            </div>
        );
    }

    return <div className={classNames.join(' ')}>{inner}</div>;
};

export default ImageChooser;
