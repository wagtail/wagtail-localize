import gettext from 'gettext';

import {
    StringTranslationAPI,
    StringTranslation,
    SegmentOverride,
    SegmentOverrideAPI
} from '.';

export interface EditorState {
    stringTranslations: Map<number, StringTranslation>;
    segmentOverrides: Map<number, SegmentOverride>;
    editingSegments: Set<number>;
}

export const SET_EDITING_MODE = 'set-editing-mode';
export interface SetEditingModeAction {
    type: typeof SET_EDITING_MODE;
    segmentId: number;
    editing: boolean;
}

export const EDIT_STRING_TRANSLATION = 'edit-string-translation';
export interface EditStringTranslationAction {
    type: typeof EDIT_STRING_TRANSLATION;
    segmentId: number;
    value: string;
}

export const TRANSLATION_SAVED = 'translation-saved';
export interface TranslationSavedAction {
    type: typeof TRANSLATION_SAVED;
    segmentId: number;
    translation: StringTranslationAPI;
}

export const TRANSLATION_DELETED = 'translation-deleted';
export interface TranslationDeletedAction {
    type: typeof TRANSLATION_DELETED;
    segmentId: number;
}

export const TRANSLATION_SAVE_SERVER_ERROR = 'translation-save-server-error';
export interface TranslationSaveServerErrorAction {
    type: typeof TRANSLATION_SAVE_SERVER_ERROR;
    segmentId: number;
}

export const EDIT_OVERRIDE = 'edit-override';
export interface EditOverrideAction {
    type: typeof EDIT_OVERRIDE;
    segmentId: number;
    value: any;
}

export const DELETE_OVERRIDE = 'delete-override';
export interface DeleteOverrideAction {
    type: typeof DELETE_OVERRIDE;
    segmentId: number;
}

export const OVERRIDE_SAVED = 'override-saved';
export interface OverrideSavedAction {
    type: typeof OVERRIDE_SAVED;
    segmentId: number;
    override: SegmentOverrideAPI;
}

export const OVERRIDE_DELETED = 'override-deleted';
export interface OverrideDeletedAction {
    type: typeof OVERRIDE_DELETED;
    segmentId: number;
}

export const OVERRIDE_SAVE_SERVER_ERROR = 'override-save-server-error';
export interface OverrideSaveServerErrorAction {
    type: typeof OVERRIDE_SAVE_SERVER_ERROR;
    segmentId: number;
}

export type EditorAction =
    | SetEditingModeAction
    | EditStringTranslationAction
    | TranslationSavedAction
    | TranslationDeletedAction
    | TranslationSaveServerErrorAction
    | EditOverrideAction
    | DeleteOverrideAction
    | OverrideSavedAction
    | OverrideDeletedAction
    | OverrideSaveServerErrorAction;

export function reducer(state: EditorState, action: EditorAction) {
    let stringTranslations = new Map(state.stringTranslations);
    let segmentOverrides = new Map(state.segmentOverrides);
    let editingSegments = new Set(state.editingSegments);

    switch (action.type) {
        // Editing mode
        case SET_EDITING_MODE: {
            if (action.editing) {
                editingSegments.add(action.segmentId);
            } else {
                editingSegments.delete(action.segmentId);
            }
            break;
        }

        // Translation actions
        case EDIT_STRING_TRANSLATION: {
            stringTranslations.set(action.segmentId, {
                value: action.value,
                isSaving: true,
                isErrored: false,
                comment: gettext('Saving...'),
                translatedBy: null
            });
            break;
        }
        case TRANSLATION_SAVED: {
            stringTranslations.set(action.segmentId, {
                value: action.translation.data,
                isSaving: false,
                isErrored: !!action.translation.error,
                comment: action.translation.error
                    ? action.translation.error
                    : action.translation.comment,
                translatedBy: action.translation.last_translated_by
            });
            break;
        }
        case TRANSLATION_DELETED: {
            stringTranslations.delete(action.segmentId);
            break;
        }
        case TRANSLATION_SAVE_SERVER_ERROR: {
            const translation = stringTranslations.get(action.segmentId);

            if (translation) {
                stringTranslations.set(
                    action.segmentId,
                    Object.assign({}, translation, {
                        isSaving: false,
                        isErrored: true,
                        comment: gettext('Server error')
                    })
                );
            }
            break;
        }

        // Override actions

        case EDIT_OVERRIDE: {
            segmentOverrides.set(action.segmentId, {
                value: action.value,
                isSaving: true,
                isErrored: false,
                comment: gettext('Changed')
            });
            break;
        }
        case DELETE_OVERRIDE: {
            const override = segmentOverrides.get(action.segmentId);

            if (override) {
                segmentOverrides.set(
                    action.segmentId,
                    Object.assign({}, override, {
                        isSaving: true
                    })
                );
            }
            break;
        }
        case OVERRIDE_SAVED: {
            segmentOverrides.set(action.segmentId, {
                value: action.override.data,
                isSaving: false,
                isErrored: !!action.override.error,
                comment: action.override.error || gettext('Changed')
            });
            break;
        }
        case OVERRIDE_DELETED: {
            segmentOverrides.delete(action.segmentId);
            break;
        }
        case OVERRIDE_SAVE_SERVER_ERROR: {
            const override = segmentOverrides.get(action.segmentId);

            if (override) {
                segmentOverrides.set(
                    action.segmentId,
                    Object.assign({}, override, {
                        isSaving: false
                    })
                );
            }
            break;
        }
    }

    return Object.assign({}, state, {
        stringTranslations,
        segmentOverrides,
        editingSegments
    });
}
