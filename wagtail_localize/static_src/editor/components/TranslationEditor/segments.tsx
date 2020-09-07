import React, { FunctionComponent } from 'react';
import styled from 'styled-components';
import gettext from 'gettext';

import Icon from '../../../common/components/Icon';
import Avatar from '../../../common/components/Avatar';

import {
    EditorProps,
    StringSegment,
    StringTranslation,
    StringTranslationAPI,
    RelatedObjectSegment,
    Segment
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
        formData.append('value', value);

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
    onHitEnter?(): void;
    focusOnMount?: boolean;
}

const StyledTextArea = styled.textarea`
    border: none;
    border-radius: 0;
    resize: none;
    white-space: normal;
`;

const SingleLineTextArea: FunctionComponent<SingleLineTextAreaProps> = ({
    value,
    onChange,
    onHitEnter,
    focusOnMount
}) => {
    // Using a single line text area to get the wrapping behaviour we want. But it also allows the Grammarly plugin to work

    const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key == 'Enter' && onHitEnter) {
            e.preventDefault();
            onHitEnter();
        }
    };

    const onChangeValue = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        if (onChange) {
            // Since we only want the wrapping behaviour and not newlines, we need to strip them out
            onChange(e.target.value.replace(/(\r\n|\n|\r)/gm, ''));
        }
    };

    // Resize the textarea whenever the value is changed
    const textAreaElement = React.useRef<HTMLTextAreaElement>(null);
    React.useEffect(() => {
        if (textAreaElement.current) {
            textAreaElement.current.style.height = '';
            textAreaElement.current.style.height =
                textAreaElement.current.scrollHeight + 'px';
        }
    }, [value, textAreaElement]);

    // Focus the textarea when it is mounted
    React.useEffect(() => {
        if (focusOnMount && textAreaElement.current) {
            textAreaElement.current.focus();
        }
    }, [textAreaElement]);

    return (
        <StyledTextArea
            rows={1}
            ref={textAreaElement}
            onChange={onChangeValue}
            onKeyDown={onKeyDown}
            value={value}
        />
    );
};

export const BlockLabel = styled.h3`
    color: #007273;
    border: 1px solid #f5f5f5;
    padding-left: 11px;
    padding-right: 11px;
    padding-top: 7px;
    padding-bottom: 9px;
    display: inline-block;
    margin-bottom: 0;
    font-weight: bold;
`;

const BlockSegments = styled.ul`
    list-style-type: none;
    border: 1px solid #eeeeee;
    background-color: #f1f1f1;
    padding: 0;
    margin: 0;

    > li {
        &.errored {
            background-color: #fee7e8;
            // !important required to override the border-bottom rule just below
            border: 1px solid #cd3238 !important;
        }

        &:not(:last-child) {
            border-bottom: 1px solid #eaeaea;
        }

        &:after {
            content: '';
            display: table;
            clear: both;
        }
    }
`;

const SegmentFieldLabel = styled.h4`
    color: #007273;
    font-style: normal;
    font-weight: bold;
    padding-left: 20px;
`;

const SegmentSource = styled.p`
    padding: 15px 20px;
    font-style: italic;
`;

const SegmentValue = styled.div`
    > p,
    > ${StyledTextArea} {
        padding: 0.9em 1.2em;
        font-size: 1.2em;
        font-style: italic;
        line-height: 1.5em;
        font-style: italic;
        font-weight: 600;
    }
`;

const ActionButton = styled.button`
    text-transform: uppercase;
    font-size: 0.8em;
    font-weight: bold;
    color: #017373;
    background-color: #e5f1f1;
    border: 1px solid #6cafaf;
    border-radius: 2px;
    padding: 5px 10px;

    &:hover {
        background-color: darken(#e5f1f1, 10%);
    }
`;

const SegmentToolbar = styled.ul`
    box-sizing: border-box;
    width: 100%;
    text-align: right;
    padding: 10px;
    margin: 0;

    > li {
        display: inline-block;

        &:not(:first-child) {
            margin-left: 15px;
        }
    }

    .icon {
        width: 1.3em;
        height: 1.3em;
        vertical-align: text-bottom;
        margin-left: 10px;

        &--green {
            color: #15704d;
        }

        &--red {
            color: #cd3239;
        }
    }
`;

const SegmentList = styled.ul`
    list-style-type: none;
    padding-left: 50px;
    padding-right: 50px;
`;

interface EditorStringSegmentProps {
    segment: StringSegment;
    translation?: StringTranslation;
    isLocked: boolean;
    dispatch: React.Dispatch<EditorAction>;
    csrfToken: string;
}

const EditorStringSegment: FunctionComponent<EditorStringSegmentProps> = ({
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
    let buttons: React.ReactElement[] = [];
    let value: React.ReactFragment = <></>;

    if (isEditing && !isLocked) {
        const onClickSave = () => {
            setIsEditing(false);
            saveTranslation(segment, editingValue, csrfToken, dispatch);
        };

        const onClickCancel = () => {
            setIsEditing(false);
        };

        buttons = [
            <li key="cancel">
                <ActionButton onClick={onClickCancel}>
                    {gettext('Cancel')}
                </ActionButton>
            </li>,
            <li key="save">
                <ActionButton onClick={onClickSave}>
                    {gettext('Save')}
                </ActionButton>
            </li>
        ];

        value = (
            <SingleLineTextArea
                onChange={setEditingValue}
                onHitEnter={onClickSave}
                value={editingValue}
                focusOnMount={true}
            />
        );
    } else if (translation && translation.isSaving) {
        comment = (
            <>
                {gettext('Saving...')} <Icon name="spinner" />
            </>
        );
        value = <p>{translation && translation.value}</p>;
    } else {
        const onClickEdit = () => {
            setIsEditing(true);
            setEditingValue((translation && translation.value) || '');
        };

        if (translation && translation.comment) {
            comment = (
                <>
                    {translation.comment}
                    {translation.isErrored ? (
                        <Icon name="warning" className="icon--red" />
                    ) : (
                        <Icon name="tick" className="icon--green" />
                    )}
                </>
            );

            if (
                translation.translatedBy &&
                translation.translatedBy.avatar_url
            ) {
                comment = (
                    <>
                        <Avatar
                            username={translation.translatedBy.full_name}
                            avatarUrl={translation.translatedBy.avatar_url}
                        />
                        {comment}
                    </>
                );
            }
        }

        if (!isLocked) {
            buttons.push(
                <li key="edit">
                    <ActionButton onClick={onClickEdit}>
                        {translation ? gettext('Edit') : gettext('Translate')}
                    </ActionButton>
                </li>
            );
        }

        value = <p>{translation && translation.value}</p>;
    }

    return (
        <li className={translation && translation.isErrored ? 'errored' : ''}>
            {segment.location.subField && (
                <SegmentFieldLabel>
                    {segment.location.subField}
                </SegmentFieldLabel>
            )}
            <SegmentSource>{segment.source}</SegmentSource>
            <SegmentValue>{value}</SegmentValue>
            <SegmentToolbar>
                <li key="comment">{comment}</li>
                {buttons}
            </SegmentToolbar>
        </li>
    );
};

interface EditorRelatedObjectSegmentProps {
    segment: RelatedObjectSegment;
}

const EditorRelatedObjectSegment: FunctionComponent<
    EditorRelatedObjectSegmentProps
> = ({ segment }) => {
    const openEditUrl = () => {
        if (segment.dest) {
            window.open(segment.dest.editUrl);
        }
    };

    const openCreateTranslationRequestUrl = () => {
        if (!!segment.source && segment.source.createTranslationRequestUrl) {
            window.open(segment.source.createTranslationRequestUrl);
        }
    };

    return (
        <li>
            {segment.location.subField && (
                <SegmentFieldLabel>
                    {segment.location.subField}
                </SegmentFieldLabel>
            )}
            <SegmentValue>
                <p>
                    {segment.source
                        ? segment.source.title
                        : gettext('[DELETED]')}
                </p>
            </SegmentValue>
            <SegmentToolbar>
                <li>
                    {!!segment.dest ? (
                        <>
                            {segment.translationProgress.translatedSegments} /{' '}
                            {segment.translationProgress.totalSegments}{' '}
                            {gettext('segments translated')}
                            {segment.translationProgress.translatedSegments ==
                                segment.translationProgress.totalSegments && (
                                <Icon name="tick" className="icon--green" />
                            )}
                        </>
                    ) : (
                        <>
                            {gettext('Not translated')}{' '}
                            <Icon name="warning" className="icon--red" />
                        </>
                    )}
                </li>
                <li>
                    {segment.dest && segment.dest.editUrl && (
                        <ActionButton onClick={openEditUrl}>
                            {gettext('Edit')}
                        </ActionButton>
                    )}
                    {!segment.dest &&
                        !!segment.source &&
                        segment.source.createTranslationRequestUrl && (
                            <ActionButton
                                onClick={openCreateTranslationRequestUrl}
                            >
                                {gettext('Translate')}
                            </ActionButton>
                        )}
                </li>
            </SegmentToolbar>
        </li>
    );
};

interface EditorSegmentListProps extends EditorProps, EditorState {
    dispatch: React.Dispatch<EditorAction>;
    csrfToken: string;
}

const EditorSegmentList: FunctionComponent<EditorSegmentListProps> = ({
    object: { isLocked },
    segments,
    stringTranslations,
    dispatch,
    csrfToken
}) => {
    // Group segments by field/block
    const segmentsByFieldBlock: Map<string, Segment[]> = new Map();
    segments.forEach(segment => {
        const field = segment.location.field;
        const blockId = segment.location.blockId || 'null';
        const key = `${field}/${blockId}`;

        let list = segmentsByFieldBlock.get(key);
        if (!list) {
            list = [];
            segmentsByFieldBlock.set(key, list);
        }

        list.push(segment);
    });

    const segmentRendered = Array.from(segmentsByFieldBlock.entries()).map(
        ([fieldBlock, segments]) => {
            // Render segments in field/block
            const segmentsRendered = segments.map(segment => {
                switch (segment.type) {
                    case 'string': {
                        return (
                            <EditorStringSegment
                                key={segment.id}
                                segment={segment}
                                translation={stringTranslations.get(segment.id)}
                                isLocked={isLocked}
                                dispatch={dispatch}
                                csrfToken={csrfToken}
                            />
                        );
                    }
                    case 'related_object': {
                        return <EditorRelatedObjectSegment segment={segment} />;
                    }
                }
            });

            return (
                <li key={fieldBlock}>
                    <BlockLabel>{segments[0].location.field}</BlockLabel>
                    <BlockSegments>{segmentsRendered}</BlockSegments>
                </li>
            );
        }
    );

    return <SegmentList>{segmentRendered}</SegmentList>;
};

export default EditorSegmentList;
