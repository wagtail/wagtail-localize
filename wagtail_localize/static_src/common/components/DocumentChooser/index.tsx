import React, { FunctionComponent } from 'react';
import gettext from 'gettext';

interface DocumentAPI {
    id: number;
    title: string;
}

interface DocumentChooserProps {
    documentId: number | null;
}

const DocumentChooser: FunctionComponent<DocumentChooserProps> = ({
    documentId
}) => {
    const [documentInfo, setDocumentInfo] = React.useState<DocumentAPI | null>(
        null
    );

    React.useEffect(() => {
        setDocumentInfo(null);

        if (documentId) {
            fetch(`/admin/api/main/documents/${documentId}/`)
                .then(response => response.json())
                .then(setDocumentInfo);
        }
    }, [documentId]);

    // Render
    let classNames = ['chooser', 'document-chooser'];
    let inner;
    if (documentId) {
        if (documentInfo) {
            inner = (
                <div className="chosen">
                    <span className="title">{documentInfo.title}</span>

                    <ul className="actions" style={{ listStyleType: 'none' }}>
                        <li>
                            <a
                                href={`/admin/documents/edit/${documentInfo.id}/`}
                                className="edit-link button button-small button-secondary"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                {gettext('Edit this document')}
                            </a>
                        </li>
                    </ul>
                </div>
            );
        } else {
            inner = <p>{gettext('Fetching document information...')}</p>;
        }
    } else {
        classNames.push('blank');

        inner = (
            <div className="unchosen">
                <button
                    type="button"
                    className="button action-choose button-small button-secondary"
                >
                    {gettext('Choose a document')}
                </button>
            </div>
        );
    }

    return <div className={classNames.join(' ')}>{inner}</div>;
};

export default DocumentChooser;
