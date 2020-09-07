import gettext from 'gettext';

import { StringTranslationAPI, StringTranslation } from '.';

export interface EditorState {
    stringTranslations: Map<number, StringTranslation>;
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

export type EditorAction =
    | EditStringTranslationAction
    | TranslationSavedAction
    | TranslationDeletedAction
    | TranslationSaveServerErrorAction;

export function reducer(state: EditorState, action: EditorAction) {
    let stringTranslations = new Map(state.stringTranslations);

    switch (action.type) {
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
    }

    return Object.assign({}, state, { stringTranslations });
}
