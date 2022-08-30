import React, { FunctionComponent } from 'react';
import gettext from 'gettext';

interface PageAPI {
    id: number;
    title: string;
}

interface PageChooserProps {
    adminBaseUrl: string;
    pageId: number | null;
}

const PageChooser: FunctionComponent<PageChooserProps> = ({
    adminBaseUrl,
    pageId
}) => {
    const [pageInfo, setPageInfo] = React.useState<PageAPI | null>(null);

    React.useEffect(() => {
        setPageInfo(null);

        if (pageId) {
            fetch(`${adminBaseUrl}api/main/pages/${pageId}/`)
                .then(response => response.json())
                .then(setPageInfo);
        }
    }, [pageId]);

    // Render
    let classNames = ['chooser', 'page-chooser'];
    let inner;
    if (pageId) {
        if (pageInfo) {
            inner = (
                <div className="chosen">
                    <span className="title">{pageInfo.title}</span>

                    <ul className="actions" style={{ listStyleType: 'none' }}>
                        <li>
                            <a
                                href={`${adminBaseUrl}pages/${pageInfo.id}/edit/`}
                                className="edit-link button button-small button-secondary"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                {gettext('Edit this page')}
                            </a>
                        </li>
                    </ul>
                </div>
            );
        } else {
            inner = <p>{gettext('Fetching page information...')}</p>;
        }
    } else {
        classNames.push('blank');

        inner = (
            <div className="unchosen">
                <button
                    type="button"
                    className="button action-choose button-small button-secondary"
                >
                    {gettext('Choose a page')}
                </button>
            </div>
        );
    }

    return <div className={classNames.join(' ')}>{inner}</div>;
};

export default PageChooser;
