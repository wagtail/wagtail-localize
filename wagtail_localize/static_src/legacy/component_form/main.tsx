document.addEventListener('DOMContentLoaded', () => {
    const toggleInput = (trigger: Element, isChecked: boolean) => {
        const componentForm = trigger.closest('.component-form');
        if (!componentForm) {
            return;
        }
        if (isChecked) {
            componentForm.classList.remove('component-form--disabled');
        } else {
            componentForm.classList.add('component-form--disabled');
        }

        const enableInput = componentForm.querySelector(
            '.component-form__fieldname-enabled input'
        ) as HTMLInputElement | null;
        if (enableInput) {
            enableInput.checked = isChecked;
        }
    };
    // Component enable buttons
    document
        .querySelectorAll('.component-form__enable-button')
        .forEach(enableButton => {
            enableButton.addEventListener('click', () => {
                toggleInput(enableButton, true);
            });
        });

    // Component disable buttons
    document
        .querySelectorAll('.component-form__disable-button')
        .forEach(disableButton => {
            disableButton.addEventListener('click', () => {
                toggleInput(disableButton, false);
            });
        });
});
