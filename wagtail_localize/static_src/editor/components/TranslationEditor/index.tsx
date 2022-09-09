import React, { FunctionComponent, useEffect } from 'react';

import Section from '../../../common/components/Section';
import { Tabs, TabContent } from '../../../common/components/Tabs';

import { EditorState, reducer } from './reducer';
import EditorHeader from './header';
import EditorFooter from './footer';
import EditorSegmentList from './segments';
import EditorToolbox from './toolbox';
import gettext from 'gettext';

export interface User {
    full_name: string;
    avatar_url: string | null;
}

export interface Tab {
    label: string;
    slug: string;
}

export interface Locale {
    code: string;
    displayName: string;
}

export interface BreadcrumbItem {
    id: number;
    isRoot: boolean;
    title: string;
    exploreUrl: string;
}

export interface Translation {
    title: string;
    locale: Locale;
    editUrl?: string;
}

export interface PreviewMode {
    mode: string;
    label: string;
    url: string;
}

export interface PageChooserWidget {
    type: 'page_chooser';
    allowed_page_types: string[];
}

export interface SnippetChooserWidget {
    type: 'snippet_chooser';
    snippet_model: {
        app_label: string;
        model_name: string;
        verbose_name: string;
        verbose_name_plural: string;
    };
    chooser_url: string;
}

export interface OtherWidgets {
    type: 'text' | 'image_chooser' | 'document_chooser' | 'unknown';
}

export interface SegmentCommon {
    id: number;
    contentPath: string;
    location: {
        tab: string;
        field: string;
        blockId: string | null;
        subField: string | null;
        helpText: string;
        widget: PageChooserWidget | SnippetChooserWidget | OtherWidgets;
    };
}

export interface StringSegment extends SegmentCommon {
    type: 'string';
    source: string;
    editUrl: string;
}

export interface SynchronisedValueSegment extends SegmentCommon {
    type: 'synchronised_value';
    value: any;
    editUrl: string;
}

export interface RelatedObjectSegment extends SegmentCommon {
    type: 'related_object';
    source: {
        title: string;
        isLive: boolean;
        liveUrl?: string;
        editUrl?: string;
        createTranslationRequestUrl?: string;
    } | null;
    dest: {
        title: string;
        isLive: boolean;
        liveUrl?: string;
        editUrl?: string;
    } | null;
    translationProgress: {
        totalSegments: number;
        translatedSegments: number;
    } | null; // Null if translated without wagtail-localize
}

export type Segment =
    | StringSegment
    | SynchronisedValueSegment
    | RelatedObjectSegment;

export interface StringTranslationAPI {
    string_id: number;
    segment_id: number;
    data: string;
    error: string;
    comment: string;
    last_translated_by: User | null;
}

export interface StringTranslation {
    value: string;
    isSaving: boolean;
    isErrored: boolean;
    comment: string;
    translatedBy: User | null;
}

export interface SegmentOverrideAPI {
    segment_id: number;
    data: any;
    error: string;
}

export interface SegmentOverride {
    value: any;
    isSaving: boolean;
    isErrored: boolean;
    comment: string;
}

export interface EditorProps {
    adminBaseUrl: string;
    csrfToken: string;
    object: {
        title: string;
        titleSegmentId: number | null;
        isLive: boolean;
        isLocked: boolean;
        lastPublishedDate: string | null;
        lastPublishedBy: User | null;
        liveUrl?: string;
    };
    breadcrumb: BreadcrumbItem[];
    tabs: Tab[];
    sourceLocale: Locale;
    locale: Locale;
    translations: Translation[];
    perms: {
        canSaveDraft: boolean;
        canPublish: boolean;
        canUnpublish: boolean;
        canLock: boolean;
        canUnlock: boolean;
        canDelete: boolean;
    };
    links: {
        downloadPofile: string;
        uploadPofile: string;
        unpublishUrl: string;
        lockUrl: string;
        unlockUrl: string;
        deleteUrl: string;
        stopTranslationUrl: string;
        convertToAliasUrl: string;
    };
    previewModes: PreviewMode[];
    machineTranslator: {
        name: string;
        url: string;
    } | null;
    segments: Segment[];
    initialStringTranslations: StringTranslationAPI[];
    initialOverrides: SegmentOverrideAPI[];
}

const TranslationEditor: FunctionComponent<EditorProps> = props => {
    // Convert initialStringTranslations into a Map that maps segment ID to translation info
    const stringTranslations: Map<number, StringTranslation> = new Map();
    props.initialStringTranslations.forEach(translation => {
        stringTranslations.set(translation.segment_id, {
            value: translation.data,
            isSaving: false,
            isErrored: !!translation.error,
            comment: translation.error
                ? translation.error
                : translation.comment,
            translatedBy: translation.last_translated_by
        });
    });

    // Same with initialSegmentOverrides
    const segmentOverrides: Map<number, SegmentOverride> = new Map();
    props.initialOverrides.forEach(override => {
        segmentOverrides.set(override.segment_id, {
            value: override.data,
            isSaving: false,
            isErrored: !!override.error,
            comment: override.error || gettext('Changed')
        });
    });

    // Set up initial state
    const initialState: EditorState = {
        stringTranslations,
        segmentOverrides,
        editingSegments: new Set()
    };

    const [state, dispatch] = React.useReducer(reducer, initialState);

    // Catch user trying to navigate away with unsaved segments
    useEffect(() => {
        if (state.editingSegments.size > 0) {
            const onUnload = (event: BeforeUnloadEvent) => {
                const confirmationMessage = gettext(
                    'There are unsaved segments. Please save or cancel them before leaving.'
                );

                // eslint-disable-next-line no-param-reassign
                event.returnValue = confirmationMessage;
                return confirmationMessage;
            };

            window.addEventListener('beforeunload', onUnload);
            return () => {
                window.removeEventListener('beforeunload', onUnload);
            };
        }
    }, [state.editingSegments]);

    const tabData = props.tabs
        .map(tab => {
            const segments = props.segments.filter(
                segment => segment.location.tab == tab.slug
            );
            const translations = segments.map(
                segment =>
                    segment.type == 'string' &&
                    state.stringTranslations.get(segment.id)
            );

            return {
                numErrors: translations.filter(
                    translation => translation && translation.isErrored
                ).length,
                segments,
                ...tab
            };
        })
        .filter(tab => tab.segments.length > 0);

    let tabs = <></>;
    if (tabData.length > 1) {
        tabs = (
            <Tabs tabs={tabData}>
                {tabData.map(tab => {
                    return (
                        <TabContent key={tab.slug} {...tab}>
                            <EditorToolbox
                                {...props}
                                {...state}
                                dispatch={dispatch}
                            />
                            <Section
                                title={`${props.sourceLocale.displayName} to ${props.locale.displayName} translation`}
                            >
                                <EditorSegmentList
                                    {...props}
                                    segments={tab.segments}
                                    {...state}
                                    dispatch={dispatch}
                                />
                            </Section>
                        </TabContent>
                    );
                })}
            </Tabs>
        );
    } else {
        tabs = (
            <>
                <EditorToolbox {...props} {...state} dispatch={dispatch} />
                <Section
                    title={`${props.sourceLocale.displayName} to ${props.locale.displayName} translation`}
                >
                    <EditorSegmentList
                        {...props}
                        {...state}
                        dispatch={dispatch}
                    />
                </Section>
            </>
        );
    }

    return (
        <>
            <EditorHeader {...props} {...state} />
            {tabs}
            <EditorFooter {...props} />
        </>
    );
};

export default TranslationEditor;
