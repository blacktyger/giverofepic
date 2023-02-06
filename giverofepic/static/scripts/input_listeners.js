$('#walletAddress').on('input', async function() {
    let button = $('#receiveButton')
    let address = $('#walletAddress').val()
    let addrText = $('.addressFeedback')
    let addrIcon = $('.addressIcon')

    if (!address) {
        addrIcon.css('color', 'grey')
        button.attr('disabled', true)
        addrText.text('')
    } else {
        if (address.trim().length === 52) {
        addrIcon.css('color', 'green')
            button.attr('disabled', false)
            addrText.text('')
        } else {
        addrIcon.css('color', 'orange')
            button.attr('disabled', true)
            addrText.text(`* Invalid wallet address`)
        }
    }
});