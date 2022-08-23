import React, { FunctionComponent } from 'react';
import gettext from 'gettext';

interface SnippetAPI {
    id: string | number;
    title: string;
    edit_url: string;
}

interface SnippetChooserProps {
    adminBaseUrl: string;
    snippetModel: {
        app_label: string;
        model_name: string;
        verbose_name: string;
        verbose_name_plural: string;
    };
    snippetId: string | number | null;
}

const SnippetChooser: FunctionComponent<SnippetChooserProps> = ({
    adminBaseUrl,
    snippetModel,
    snippetId
}) => {
    const [snippetInfo, setSnippetInfo] = React.useState<SnippetAPI | null>(
        null
    );

    React.useEffect(() => {
        setSnippetInfo(null);

        if (snippetId) {
            fetch(
                `${adminBaseUrl}localize/api/snippets/${snippetModel.app_label}/${snippetModel.model_name}/${snippetId}/`
            )
                .then(response => response.json())
                .then(setSnippetInfo);
        }
    }, [snippetId]);

    // Render
    let classNames = ['chooser', 'snippet-chooser'];
    let inner;
    if (snippetId) {
        if (snippetInfo) {
            inner = (
                <div className="chosen">
                    <span className="title">{snippetInfo.title}</span>

                    <ul className="actions" style={{ listStyleType: 'none' }}>
                        <li>
                            <a
                                href={snippetInfo.edit_url}
                                className="edit-link button button-small button-secondary"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                {gettext('Edit this %s').replace(
                                    '%s',
                                    snippetModel.verbose_name
                                )}
                            </a>
                        </li>
                    </ul>
                </div>
            );
        } else {
            inner = (
                <p>
                    {gettext('Fetching %s information...').replace(
                        '%s',
                        snippetModel.verbose_name
                    )}
                </p>
            );
        }
    } else {
        classNames.push('blank');

        inner = (
            <div className="unchosen">
                <button
                    type="button"
                    className="button action-choose button-small button-secondary"
                >
                    {gettext('Choose a %s').replace(
                        '%s',
                        snippetModel.verbose_name
                    )}
                </button>
            </div>
        );
    }

    return <div className={classNames.join(' ')}>{inner}</div>;
};

export default SnippetChooser;
