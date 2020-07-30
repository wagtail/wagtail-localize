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
    switch (action.type) {
        case EDIT_STRING_TRANSLATION: {
            let stringTranslations = new Map(state.stringTranslations);
            stringTranslations.set(action.segmentId, {
                value: action.value,
                isSaving: true,
                isErrored: false,
                comment: gettext('Saving...')
            });
            state = Object.assign({}, state, { stringTranslations });
            break;
        }
        case TRANSLATION_SAVED: {
            let stringTranslations = new Map(state.stringTranslations);
            stringTranslations.set(action.segmentId, {
                value: action.translation.data,
                isSaving: false,
                isErrored: false,
                comment: action.translation.comment
            });

            state = Object.assign({}, state, { stringTranslations });
            break;
        }
        case TRANSLATION_DELETED: {
            let stringTranslations = new Map(state.stringTranslations);
            stringTranslations.delete(action.segmentId);
            state = Object.assign({}, state, { stringTranslations });
            break;
        }
        case TRANSLATION_SAVE_SERVER_ERROR: {
            let stringTranslations = new Map(state.stringTranslations);
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

            state = Object.assign({}, state, { stringTranslations });
            break;
        }
    }
    return state;
}
