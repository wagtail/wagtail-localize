import React, { FunctionComponent } from 'react';

import Section from '../../../common/components/Section';
import {Tabs, TabContent} from '../../../common/components/Tabs';

import './style.scss';
import { EditorState, reducer } from './reducer';
import EditorHeader from './header';
import EditorFooter from './footer';
import EditorSegmentList from './segments';

export interface Locale {
    code: string;
    displayName: string;
}

export interface BreadcrumbItem {
    isRoot: boolean;
    title: string;
    exploreUrl: string;
}

export interface Translation {
    title: string;
    locale: Locale;
    editUrl?: string;
}

export interface StringSegment {
    id: number;
    contentPath: string;
    source: string;
    location: {
        tab: string;
        field: string;
        blockId: string|null;
        subField: string | null;
        helpText: string;
    };
    editUrl: string;
}

export interface StringTranslationAPI {
    string_id: number;
    segment_id: number;
    data: string;
    comment: string;
}

export interface StringTranslation {
    value: string;
    isSaving: boolean;
    isErrored: boolean;
    comment: string;
}

export interface EditorProps {
    csrfToken: string;
    object: {
        title: string;
        isLive: boolean;
        isLocked: boolean;
        lastPublishedDate: string | null;
        liveUrl?: string;
    };
    breadcrumb: BreadcrumbItem[];
    tabs: string[];
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
        unpublishUrl: string;
        lockUrl: string;
        unlockUrl: string;
        deleteUrl: string;
    }
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
            isErrored: false,
            comment: translation.comment
        });
    });

    // Set up initial state
    const initialState: EditorState = {
        stringTranslations
    };
    const [state, dispatch] = React.useReducer(reducer, initialState);

    let tabs = <></>;
    if (props.tabs.length > 1) {
        tabs = <Tabs tabs={props.tabs}>
            {props.tabs.map(tab => {
                return <TabContent tab={tab}>
                    <Section
                        title={`${props.sourceLocale.displayName} to ${props.locale.displayName} translation`}
                    >
                        <EditorSegmentList {...props} segments={props.segments.filter(segment => segment.location.tab == tab)} {...state} dispatch={dispatch} />
                    </Section>
                </TabContent>
            })}
        </Tabs>;
    } else {
        tabs = <Section
            title={`${props.sourceLocale.displayName} to ${props.locale.displayName} translation`}
        >
            <EditorSegmentList {...props} {...state} dispatch={dispatch} />
        </Section>;
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
