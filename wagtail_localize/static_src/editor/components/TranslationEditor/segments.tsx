import React, { FunctionComponent } from 'react';
import styled from 'styled-components';
import gettext from 'gettext';

import Icon from '../../../common/components/Icon';
import Avatar from '../../../common/components/Avatar';

import PageChooser from '../../../common/components/PageChooser';
import ImageChooser from '../../../common/components/ImageChooser';
import DocumentChooser from '../../../common/components/DocumentChooser';
import SnippetChooser from '../../../common/components/SnippetChooser';

import {
    EditorProps,
    StringSegment,
    SynchronisedValueSegment,
    Segment,
    StringTranslation,
    StringTranslationAPI,
    SegmentOverride,
    SegmentOverrideAPI,
    Locale,
    RelatedObjectSegment
} from '.';
import {
    EditorState,
    EditorAction,
    EDIT_STRING_TRANSLATION,
    TRANSLATION_SAVE_SERVER_ERROR,
    TRANSLATION_SAVED,
    TRANSLATION_DELETED,
    EDIT_OVERRIDE,
    OVERRIDE_SAVED,
    OVERRIDE_SAVE_SERVER_ERROR,
    DELETE_OVERRIDE,
    OVERRIDE_DELETED
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

function saveOverride(
    segment: SynchronisedValueSegment,
    value: any,
    csrfToken: string,
    dispatch: React.Dispatch<EditorAction>
) {
    dispatch({
        type: EDIT_OVERRIDE,
        segmentId: segment.id,
        value: value
    });

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
        .then((override: SegmentOverrideAPI) => {
            dispatch({
                type: OVERRIDE_SAVED,
                segmentId: segment.id,
                override
            });
        })
        .catch(() => {
            dispatch({
                type: OVERRIDE_SAVE_SERVER_ERROR,
                segmentId: segment.id
            });
        });
}

function deleteOverride(
    segment: SynchronisedValueSegment,
    csrfToken: string,
    dispatch: React.Dispatch<EditorAction>
) {
    dispatch({
        type: DELETE_OVERRIDE,
        segmentId: segment.id
    });

    // Delete the override
    fetch(segment.editUrl, {
        credentials: 'same-origin',
        method: 'DELETE',
        headers: {
            'X-CSRFToken': csrfToken
        }
    }).then(response => {
        if (response.status == 200 || response.status == 404) {
            dispatch({
                type: OVERRIDE_DELETED,
                segmentId: segment.id
            });
        } else {
            dispatch({
                type: OVERRIDE_SAVE_SERVER_ERROR,
                segmentId: segment.id
            });
        }
    });
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

        &.incomplete {
            // !important required to override the border-bottom rule just below
            border-left: 5px solid #f37e77 !important;
        }

        &.complete {
            // !important required to override the border-bottom rule just below
            border-left: 5px solid #007d7e !important;
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
    margin: 0;
    padding: 15px 20px;
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
    padding: 0.9em 1.2em;

    > p,
    > ${StyledTextArea} {
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
    isEditing: boolean;
    setIsEditing(editing: boolean): void;
    dispatch: React.Dispatch<EditorAction>;
    csrfToken: string;
}

const EditorStringSegment: FunctionComponent<EditorStringSegmentProps> = ({
    segment,
    translation,
    isLocked,
    isEditing,
    setIsEditing,
    dispatch,
    csrfToken
}) => {
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

    let className = 'complete';
    if (!translation) {
        className = 'incomplete';
    } else if (translation.isErrored) {
        className = 'errored';
    }

    return (
        <li className={className}>
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

interface EditorSynchronisedValueSegmentProps {
    adminBaseUrl: string;
    segment: SynchronisedValueSegment;
    override?: SegmentOverride;
    sourceLocale: Locale;
    isLocked: boolean;
    isEditing: boolean;
    setIsEditing(editing: boolean): void;
    dispatch: React.Dispatch<EditorAction>;
    csrfToken: string;
}

const EditorSynchronisedValueSegment: FunctionComponent<
    EditorSynchronisedValueSegmentProps
> = ({
    adminBaseUrl,
    segment,
    override,
    sourceLocale,
    isLocked,
    isEditing,
    setIsEditing,
    dispatch,
    csrfToken
}) => {
    let comment = <></>;
    let buttons: React.ReactFragment[] = [];
    let value: React.ReactFragment = <></>;

    if (override) {
        comment = (
            <>
                {override.comment}
                {override.isErrored ? (
                    <Icon name="warning" className="icon--red" />
                ) : (
                    <Icon name="tick" className="icon--green" />
                )}
            </>
        );
    } else {
        comment = (
            <>
                {gettext('Uses %s version').replace(
                    '%s',
                    sourceLocale.displayName
                )}{' '}
                <Icon name="tick" className="icon--green" />
            </>
        );
    }

    const widget = segment.location.widget;
    if (widget.type == 'text') {
        const [editingValue, setEditingValue] = React.useState(
            (override && override.value) || segment.value
        );

        if (isEditing && !isLocked) {
            const onClickSave = () => {
                setIsEditing(false);
                saveOverride(segment, editingValue, csrfToken, dispatch);
            };

            const onClickCancel = () => {
                setIsEditing(false);
            };

            buttons = [
                <ActionButton onClick={onClickCancel}>
                    {gettext('Cancel')}
                </ActionButton>,
                <ActionButton onClick={onClickSave}>
                    {gettext('Save')}
                </ActionButton>
            ];

            value = (
                <SingleLineTextArea
                    onChange={setEditingValue}
                    onHitEnter={onClickSave}
                    value={editingValue}
                    focusOnMount={true}
                />
            );
        } else {
            const onClickEdit = () => {
                setIsEditing(true);
                setEditingValue((override && override.value) || segment.value);
            };

            if (!isLocked) {
                buttons.push(
                    <ActionButton onClick={onClickEdit}>
                        {gettext('Edit')}
                    </ActionButton>
                );
            }

            value = <p>{(override && override.value) || segment.value}</p>;
        }
    } else if (widget.type == 'page_chooser') {
        const onClickChangePage = () => {
            (window as any).ModalWorkflow({
                url: (window as any).chooserUrls.pageChooser,
                urlParams: {
                    page_type: widget.allowed_page_types.join(',')
                },
                onload: (window as any).PAGE_CHOOSER_MODAL_ONLOAD_HANDLERS,
                responses: {
                    pageChosen: function(pageData: any) {
                        saveOverride(segment, pageData.id, csrfToken, dispatch);
                    }
                }
            });
        };
        if (!isLocked) {
            buttons.push(
                <ActionButton onClick={onClickChangePage}>
                    {gettext('Change page')}
                </ActionButton>
            );
        }

        value = (
            <PageChooser
                adminBaseUrl={adminBaseUrl}
                pageId={(override && override.value) || segment.value}
            />
        );
    } else if (widget.type == 'image_chooser') {
        const onClickChangeImage = () => {
            (window as any).ModalWorkflow({
                url: (window as any).chooserUrls.imageChooser,
                onload: (window as any).IMAGE_CHOOSER_MODAL_ONLOAD_HANDLERS,
                responses: {
                    imageChosen: function(imageData: any) {
                        saveOverride(
                            segment,
                            imageData.id,
                            csrfToken,
                            dispatch
                        );
                    }
                }
            });
        };
        if (!isLocked) {
            buttons.push(
                <ActionButton onClick={onClickChangeImage}>
                    {gettext('Change image')}
                </ActionButton>
            );
        }

        value = (
            <ImageChooser
                adminBaseUrl={adminBaseUrl}
                imageId={(override && override.value) || segment.value}
            />
        );
    } else if (widget.type == 'document_chooser') {
        const onClickChangeDocument = () => {
            (window as any).ModalWorkflow({
                url: (window as any).chooserUrls.documentChooser,
                onload: (window as any).DOCUMENT_CHOOSER_MODAL_ONLOAD_HANDLERS,
                responses: {
                    documentChosen: function(documentData: any) {
                        saveOverride(
                            segment,
                            documentData.id,
                            csrfToken,
                            dispatch
                        );
                    }
                }
            });
        };
        if (!isLocked) {
            buttons.push(
                <ActionButton onClick={onClickChangeDocument}>
                    {gettext('Change document')}
                </ActionButton>
            );
        }

        value = (
            <DocumentChooser
                adminBaseUrl={adminBaseUrl}
                documentId={(override && override.value) || segment.value}
            />
        );
    } else if (widget.type == 'snippet_chooser') {
        const onClickChangeSnippet = () => {
            (window as any).ModalWorkflow({
                url: widget.chooser_url,
                onload: (window as any).SNIPPET_CHOOSER_MODAL_ONLOAD_HANDLERS,
                responses: {
                    snippetChosen: function(snippetData: any) {
                        saveOverride(
                            segment,
                            snippetData.id,
                            csrfToken,
                            dispatch
                        );
                    }
                }
            });
        };
        if (!isLocked) {
            buttons.push(
                <ActionButton onClick={onClickChangeSnippet}>
                    {gettext('Change %s').replace(
                        '%s',
                        widget.snippet_model.verbose_name
                    )}
                </ActionButton>
            );
        }

        value = (
            <SnippetChooser
                adminBaseUrl={adminBaseUrl}
                snippetModel={widget.snippet_model}
                snippetId={(override && override.value) || segment.value}
            />
        );
    } else {
        value = <p>{segment.value}</p>;
    }

    if (override) {
        const onClickUseEnglishVersion = () => {
            deleteOverride(segment, csrfToken, dispatch);
        };
        buttons.push(
            <ActionButton onClick={onClickUseEnglishVersion}>
                {gettext('Revert to %s version').replace(
                    '%s',
                    sourceLocale.displayName
                )}
            </ActionButton>
        );
    }

    let className = '';
    if (override && override.isErrored) {
        className = 'errored';
    }

    return (
        <li className={className}>
            {segment.location.subField && (
                <SegmentFieldLabel>
                    {segment.location.subField}
                </SegmentFieldLabel>
            )}
            <SegmentValue>{value}</SegmentValue>
            <SegmentToolbar>
                <li>{comment}</li>
                {buttons.map(button => (
                    <li>{button}</li>
                ))}
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

    let message = <></>;

    if (segment.dest) {
        if (segment.translationProgress !== null) {
            // Translated with Wagtail localize. Show progress
            message = (
                <>
                    {segment.translationProgress.translatedSegments} /{' '}
                    {segment.translationProgress.totalSegments}{' '}
                    {gettext('segments translated')}
                    {segment.translationProgress.translatedSegments ==
                        segment.translationProgress.totalSegments && (
                        <Icon name="tick" className="icon--green" />
                    )}
                </>
            );
        } else {
            // Segment translated without Wagtail localize. Just show a tick
            message = <Icon name="tick" className="icon--green" />;
        }
    } else {
        // Not translated
        message = (
            <>
                {gettext('Not translated')}{' '}
                <Icon name="warning" className="icon--red" />
            </>
        );
    }

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
                <li>{message}</li>
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
    adminBaseUrl,
    object: { isLocked },
    sourceLocale,
    segments,
    stringTranslations,
    segmentOverrides,
    editingSegments,
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
            const setEditingMode = (segmentId: number, editing: boolean) => {
                dispatch({
                    type: 'set-editing-mode',
                    segmentId,
                    editing
                });
            };

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
                                isEditing={editingSegments.has(segment.id)}
                                setIsEditing={(editing: boolean) =>
                                    setEditingMode(segment.id, editing)
                                }
                                dispatch={dispatch}
                                csrfToken={csrfToken}
                            />
                        );
                    }
                    case 'synchronised_value': {
                        return (
                            <EditorSynchronisedValueSegment
                                adminBaseUrl={adminBaseUrl}
                                segment={segment}
                                override={segmentOverrides.get(segment.id)}
                                sourceLocale={sourceLocale}
                                isLocked={isLocked}
                                isEditing={editingSegments.has(segment.id)}
                                setIsEditing={(editing: boolean) =>
                                    setEditingMode(segment.id, editing)
                                }
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
