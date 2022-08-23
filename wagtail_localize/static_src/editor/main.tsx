import React from 'react';
import ReactDOM from 'react-dom';

document.addEventListener('DOMContentLoaded', async () => {
  const element = document.querySelector('.js-translation-editor');

  if (element instanceof HTMLElement && element.dataset.props) {
    const csrfTokenElement = element.querySelector(
      '[name="csrfmiddlewaretoken"]'
    );

    if (csrfTokenElement instanceof HTMLInputElement) {
      const csrfToken = csrfTokenElement.value;

      const props = JSON.parse(element.dataset.props)

      let TranslationEditor = React.lazy(() => import("./components/TranslationEditor"))
      if (props.uses_legacy_header) {
        TranslationEditor = React.lazy(() => import("../wagtail_2.15_LTS/editor/components/TranslationEditor"))
      }

      ReactDOM.render(
        <React.Suspense fallback={<div>Loading translation editor...</div>}>
          <TranslationEditor
            csrfToken={csrfToken}
            {...props}
          />
        </React.Suspense>,
        element
      );
    } else {
      console.error(
        "Not starting translation editor because I couldn't find the CSRF token element!"
      );
    }
  }
});
