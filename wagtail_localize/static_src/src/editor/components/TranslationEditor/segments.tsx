import React, { FunctionComponent } from 'react';
import gettext from 'gettext';

import Icon from '../../../common/components/Icon';
import Avatar from '../../../common/components/Avatar';

import {
    EditorProps,
    StringSegment,
    StringTranslation,
    StringTranslationAPI
} from '.';
import {
    EditorState,
    EditorAction,
    EDIT_STRING_TRANSLATION,
    TRANSLATION_SAVE_SERVER_ERROR,
    TRANSLATION_SAVED,
    TRANSLATION_DELETED
} from './reducer';

function saveTranslation(
    segment: StringSegment,
    value: string,
    csrfToken: string,
    dispatch: React.Dispatch<EditorAction>
) {
    dispatch({
        type: EDIT_STRING_TRANSLATION,
        segmentId: segment.id,
        value: value
    });
    if (value) {
        // Create/update the translation
        const formData = new FormData();
        formData.set('value', value);

        fetch(segment.editUrl, {
            credentials: 'same-origin',
            method: 'PUT',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken
            }
        })
            .then(response => {
                if (response.status == 200 || response.status == 201) {
                    return response.json();
                } else {
                    throw new Error('Unrecognised HTTP status returned');
                }
            })
            .then((translation: StringTranslationAPI) => {
                dispatch({
                    type: TRANSLATION_SAVED,
                    segmentId: segment.id,
                    translation
                });
            })
            .catch(() => {
                dispatch({
                    type: TRANSLATION_SAVE_SERVER_ERROR,
                    segmentId: segment.id
                });
            });
    } else {
        // Delete the translation
        fetch(segment.editUrl, {
            credentials: 'same-origin',
            method: 'DELETE',
            headers: {
                'X-CSRFToken': csrfToken
            }
        }).then(response => {
            if (response.status == 200 || response.status == 404) {
                dispatch({
                    type: TRANSLATION_DELETED,
                    segmentId: segment.id
                });
            } else {
                dispatch({
                    type: TRANSLATION_SAVE_SERVER_ERROR,
                    segmentId: segment.id
                });
            }
        });
    }
}

interface SingleLineTextAreaProps {
    value: string;
    onChange?(newValue: string): void;
}

const SingleLineTextArea: FunctionComponent<SingleLineTextAreaProps> = ({value, onChange}) => {
    // Using a single line text area to get the wrapping behaviour we want. But it also allows the Grammarly plugin to work

    const onChangeValue = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        if (onChange) {
            // Since we only want the wrapping behaviour and not newlines, we need to strip them out
            onChange(e.target.value.replace(/(\r\n|\n|\r)/gm, ""));
        }
    };

    // Resize the textarea whenever the value is changed
    const textAreaElement = React.useRef<HTMLTextAreaElement>();
    React.useEffect(() => {
        if (textAreaElement.current) {
            textAreaElement.current.style.height = "";
            textAreaElement.current.style.height = textAreaElement.current.scrollHeight + "px";
        }
    }, [value, textAreaElement]);

    return <textarea rows={1} ref={textAreaElement} onChange={onChangeValue} value={value} style={{resize: 'none', whiteSpace: 'normal'}} />;
}

interface EditorSegmentProps {
    segment: StringSegment;
    translation: StringTranslation | null;
    isLocked: boolean,
    dispatch: React.Dispatch<EditorAction>;
    csrfToken: string;
}

const EditorSegment: FunctionComponent<EditorSegmentProps> = ({
    segment,
    translation,
    isLocked,
    dispatch,
    csrfToken
}) => {
    const [isEditing, setIsEditing] = React.useState(false);
    const [editingValue, setEditingValue] = React.useState(
        (translation && translation.value) || ''
    );

    let comment = <></>;
    let buttons: (React.ReactFragment | string)[] = [];
    let value: React.ReactFragment | string = <></>;

    if (isEditing && !isLocked) {
        const onClickSave = () => {
            setIsEditing(false);
            saveTranslation(segment, editingValue, csrfToken, dispatch);
        };

        const onClickCancel = () => {
            setIsEditing(false);
        };

        buttons = [
            <button
                className="segments__button segments__button--cancel"
                onClick={onClickCancel}>
                {gettext('Cancel')}
            </button>,
            <button
                className="segments__button segments__button--save"
                onClick={onClickSave}>
                {gettext('Save')}
            </button>,
        ];

        value = <>
            <SingleLineTextArea onChange={setEditingValue} value={editingValue} />
            {segment.location.helpText && <p className="segments__segment-help">
                {segment.location.helpText}
            </p>}
        </>;
    } else if (translation && translation.isSaving) {
        comment = <>{gettext('Saving...')} <Icon name="spinner" /></>;
        value = <div className="segments__segment-value-inner">{translation && translation.value}</div>;
    } else {
        const onClickEdit = () => {
            setIsEditing(true);
            setEditingValue((translation && translation.value) || '');
        };

        if (translation && translation.comment) {
            comment = <>
                {translation.comment}
                {translation.isErrored ? <Icon name="warning" className="icon--red" /> : <Icon name="tick" className="icon--green" />}
            </>;

            if (translation.translatedBy) {
                comment = <>
                    <Avatar username={translation.translatedBy.full_name} avatarUrl={translation.translatedBy.avatar_url} />
                    {comment}
                </>;
            }
        }

        if (!isLocked) {
            buttons.push(
                <button
                    className="segments__button segments__button--edit"
                    onClick={onClickEdit}
                >
                    {translation ? gettext('Edit') : gettext('Translate')}
                </button>
            );
        }

        value = <div className="segments__segment-value-inner">{translation && translation.value}</div>;
    }

    return (
        <li className="segments__segment">
            {segment.location.subField && (
                <h4 className="segments__segment-field-label">
                    {segment.location.subField}
                </h4>
            )}
            <p className="segments__segment-source">{segment.source}</p>
            <div className="segments__segment-value">
                {value}
            </div>
            <div className="segments__segment-toolbar">
                <ul className="segments__segment-toolbar-buttons">
                    <li>{comment}</li>
                    {buttons.map(button => <li>{button}</li>)}
                </ul>
            </div>
        </li>
    );
};

interface EditorSegmentListProps extends EditorProps, EditorState {
    dispatch: React.Dispatch<EditorAction>;
    csrfToken: string;
}

const EditorSegmentList: FunctionComponent<EditorSegmentListProps> = ({
    object: {isLocked},
    segments,
    stringTranslations,
    dispatch,
    csrfToken
}) => {
    // Group segments by field/block
    const segmentsByFieldBlock: Map<string, StringSegment[]> = new Map();
    segments.forEach(segment => {
        const field = segment.location.field;
        const blockId = segment.location.blockId || 'null';
        const key = `${field}/${blockId}`;
        if (!segmentsByFieldBlock.has(key)) {
            segmentsByFieldBlock.set(key, []);
        }
        segmentsByFieldBlock.get(key).push(segment);
    });

    const segmentRendered = Array.from(segmentsByFieldBlock.entries()).map(
        ([, segments]) => {
            // Render segments in field/block
            const segmentsRendered = segments.map(segment => {
                return (
                    <EditorSegment
                        key={segment.id}
                        segment={segment}
                        translation={stringTranslations.get(segment.id)}
                        isLocked={isLocked}
                        dispatch={dispatch}
                        csrfToken={csrfToken}
                    />
                );
            });

            return (
                <li className="segments__block">
                    <h3 className="segments__block-label">{segments[0].location.field}</h3>
                    <div className="segments__block-content">
                        <ul>{segmentsRendered}</ul>
                    </div>
                </li>
            );
        }
    );

    return <ul className="segments">{segmentRendered}</ul>;
};

export default EditorSegmentList;
