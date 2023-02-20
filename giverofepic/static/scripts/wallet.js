let feedbackField = $('.feedbackField')
let receiveButton = $('#receiveButton')
let addressIcon = $('.addressIcon')
let address = $('#walletAddress')

let apiKey = 'blacktyger.XbIG7WVg'
let headers = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'X-API-Key': apiKey
}



// FEEDBACK IF CONNECTION WITH DB FAILED
checkStatus = async (response, feedbackField) => {
    if (response.status >= 200 && response.status < 300)
        return await response.json()
    feedbackField.text(response.status)
}