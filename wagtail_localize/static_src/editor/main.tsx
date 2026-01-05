import React from 'react';
import ReactDOM from 'react-dom';
import TranslationEditor from './components/TranslationEditor';

document.addEventListener('DOMContentLoaded', async () => {
    const element = document.querySelector('.js-translation-editor');

    if (element instanceof HTMLElement && element.dataset.props) {
        const csrfTokenElement = element.querySelector(
            '[name="csrfmiddlewaretoken"]',
        );

        if (csrfTokenElement instanceof HTMLInputElement) {
            const csrfToken = csrfTokenElement.value;

            const props = JSON.parse(element.dataset.props);

            let Component = TranslationEditor;

            ReactDOM.render(
                <Component csrfToken={csrfToken} {...props} />,
                element,
            );
        } else {
            console.error(
                "Not starting translation editor because I couldn't find the CSRF token element!",
            );
        }
    }
});
