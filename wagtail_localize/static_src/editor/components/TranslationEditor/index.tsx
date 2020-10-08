import React, { FunctionComponent } from 'react';

import Section from '../../../common/components/Section';
import { Tabs, TabContent } from '../../../common/components/Tabs';

import { EditorState, reducer } from './reducer';
import EditorHeader from './header';
import EditorFooter from './footer';
import EditorSegmentList from './segments';
import EditorToolbox from './toolbox';

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

export interface StringSegment {
    id: number;
    contentPath: string;
    source: string;
    location: {
        tab: string;
        field: string;
        blockId: string | null;
        subField: string | null;
        helpText: string;
    };
    editUrl: string;
}

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

export interface EditorProps {
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
    };
    previewModes: PreviewMode[];
    machineTranslator: {
        name: string;
        url: string;
    } | null;
    segments: StringSegment[];
    initialStringTranslations: StringTranslationAPI[];
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

    // Set up initial state
    const initialState: EditorState = {
        stringTranslations
    };
    const [state, dispatch] = React.useReducer(reducer, initialState);

    const tabData = props.tabs
        .map(tab => {
            const segments = props.segments.filter(
                segment => segment.location.tab == tab.slug
            );
            const translations = segments.map(segment =>
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
