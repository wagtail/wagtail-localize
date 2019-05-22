$(function() {
    /* Interface to set permissions from the explorer / editor */
    $('a.action-switch-language').on('click', function() {
        ModalWorkflow({
            url: this.href,
            onload: {
            },
            responses: {
            }
        });
        return false;
    });
});
