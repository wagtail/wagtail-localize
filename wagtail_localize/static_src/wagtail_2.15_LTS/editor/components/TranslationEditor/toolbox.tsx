import React, { FunctionComponent } from 'react';
import styled from 'styled-components';
import gettext from 'gettext';

import Icon from '../../../common/components/Icon';

import CloudIcon from './cloud-solid.svg';

import { EditorProps } from '.';
import { EditorState, EditorAction } from './reducer';

const ToolboxWrapper = styled.div`
    padding-top: 20px;

    &:after {
        content: '';
        display: table;
        clear: both;
    }
`;

const ToolWrapper = styled.div`
    float: left;
    margin-left: 50px;
    margin-bottom: 20px;
    min-height: 100px;
`;

const HiddenFileInput = styled.input`
    border: 0;
    clip: rect(0 0 0 0);
    height: 1px;
    margin: -1px;
    overflow: hidden;
    padding: 0;
    position: absolute;
    width: 1px;
`;

const StyledCloudIcon = styled(CloudIcon)`
    width: 1.5em;
    height: 1.5em;
    vertical-align: text-top;
`;

interface EditorToolboxProps extends EditorProps, EditorState {
    dispatch: React.Dispatch<EditorAction>;
    csrfToken: string;
}

const EditorToolbox: FunctionComponent<EditorToolboxProps> = ({
    object: { isLocked },
    links,
    machineTranslator,
    csrfToken,
    stringTranslations,
    segments
}) => {
    if (isLocked) {
        return <></>;
    }

    const hasUntranslatedSegments =
        Array.from(stringTranslations.keys()).length < segments.length;

    const uploadPofileForm = React.useRef<HTMLFormElement>(null);
    const uploadPofileFileInput = React.useRef<HTMLInputElement>(null);

    const onClickUploadPO = () => {
        if (uploadPofileFileInput.current) {
            uploadPofileFileInput.current.click();
        }
    };

    const uploadPofile = (e: React.ChangeEvent<HTMLInputElement>) => {
        e.preventDefault();

        if (uploadPofileForm.current) {
            uploadPofileForm.current.submit();
        }
    };

    return (
        <ToolboxWrapper>
            <ToolWrapper>
                <p>
                    {gettext('Download PO file and input translations offline')}
                </p>
                <a
                    className="button button-primary button--icon"
                    href={links.downloadPofile}
                    download
                >
                    <Icon name="download" /> {gettext('Download PO file')}
                </a>
            </ToolWrapper>

            <ToolWrapper>
                <p>
                    {gettext(
                        'Upload translated PO file to submit translations'
                    )}
                </p>
                <button
                    className="button button-primary button--icon"
                    onClick={onClickUploadPO}
                >
                    <Icon name="upload" /> {gettext('Upload PO file')}
                </button>
                <form
                    ref={uploadPofileForm}
                    action={links.uploadPofile}
                    method="post"
                    encType="multipart/form-data"
                >
                    <input
                        type="hidden"
                        name="csrfmiddlewaretoken"
                        value={csrfToken}
                    />
                    <input
                        type="hidden"
                        name="next"
                        value={window.location.href}
                    />
                    <HiddenFileInput
                        ref={uploadPofileFileInput}
                        onChange={uploadPofile}
                        type="file"
                        name="file"
                    />
                </form>
            </ToolWrapper>

            {machineTranslator && (
                <ToolWrapper>
                    <p>
                        {gettext('Translate all missing strings with ') +
                            machineTranslator.name}
                    </p>
                    <form
                        action={machineTranslator.url}
                        method="post"
                        encType="multipart/form-data"
                    >
                        <input
                            type="hidden"
                            name="csrfmiddlewaretoken"
                            value={csrfToken}
                        />
                        <input
                            type="hidden"
                            name="next"
                            value={window.location.href}
                        />
                        <button
                            type="submit"
                            className="button button-primary button--icon"
                            disabled={!hasUntranslatedSegments}
                        >
                            <StyledCloudIcon />{' '}
                            {gettext('Translate with ') +
                                machineTranslator.name}
                        </button>
                    </form>
                </ToolWrapper>
            )}
        </ToolboxWrapper>
    );
};

export default EditorToolbox;
