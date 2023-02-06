let feedbackField = $('.feedbackField')
let receiveButton = $('#receiveButton')
let addressIcon = $('.addressIcon')
let address = $('#walletAddress')

let wallet_type = 'faucet'
let apiKey = 'blacktyger.XbIG7WVg'
let headers = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'X-API-Key': apiKey
}

const spinnerHTMLsm = `<div class="spinner-border spinner-border-sm fs-6" role="status"></div>`
const spinnerHTML = `<div class="spinner-grow spinner-grow-sm align-middle" role="status"></div>
                     <div class="spinner-grow spinner-grow-sm align-middle" role="status"></div>
                     <div class="spinner-grow spinner-grow-sm align-middle" role="status"></div>`

// PROCESS USER REQUEST
async function sendTransaction() {
    let taskFinished = false
    let amount = 0.01
    let query = "api/wallet/request_transaction"
    let body = {
        address: address.val(),
        amount: amount,
        wallet_type: wallet_type
    }

    updateForm(spinnerHTML)
    feedbackField.text('Connecting to the server..')

    let encryptedPayload = await encryptPayload(body)
    console.log(encryptedPayload)

    let response = await fetch(query, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({'data': encryptedPayload})
      }).then(checkStatus)
        .catch(err => console.log(err))

    if (response) {
        if (!response.error && 'result' in response) {
            feedbackField.text('Preparing wallet..')

            let taskId = response.result.task_id
            let task = await getTaskStatus(taskId)

            while (!taskFinished) {
                if (task.status === 'finished') {
                    feedbackField.text('')
                    taskFinished = true
                    await finishedTaskHandler(task, 'sent')

                } else if (task.status === 'failed') {
                    feedbackField.text('')
                    taskFinished = true
                    transactionFailedAlert(task)
                    console.log(task.status)

                } else if (task.status === 'queued') {
                    console.log(task.status)
                    await sleep(2000)
                    feedbackField.text('Preparing wallet..')
                    task = await getTaskStatus(taskId)

                } else if (task.status === 'started') {
                    console.log(task.status)
                    await sleep(2000)
                    feedbackField.text('Preparing transaction..')
                    task = await getTaskStatus(taskId)
                }
            }
        } else {
            userRestrictedAlert(response.message)
            feedbackField.text('')
            await resetForm()
        }
    }
    feedbackField.text('')
}


// RESTRICTED USER ALERT
function userRestrictedAlert(result) {
        Swal.fire({
        icon: 'info',
        // title: `UNSUCCESSFUL`,
        html:`
            ${result}
            <hr class="mt-5" />
            <div class="my-2">
                Need support? Join
                <a href="https://t.me/GiverOfEpic" target="_blank" class="text-dark">
                    <i class="fa-brands fa-telegram ms-1"></i> <b>GiverOfEpic</b>. 
                </a>
            </div>
            <hr class="mb-2" />
            `,
        position: 'center',
        showConfirmButton: true,
        confirmButtonText: `<i class="fa fa-check"></i> CONFIRM`,
    }).then((result) => {console.log('alert result:', result)})
}


async function transactionInitializedAlert(task) {
    // SweetAlert2 instance spawned when first step of the transaction was successful
    // and script is waiting for receiving wallet to send response slate.
    let timerInterval

    Swal.fire({
        html:
            `<div class="card mt-1 bg-blue text-light">
                 <div class="card-img">
                    <img class="card-img" src="static/img/stack-wallet.png" alt="img">
                 </div>
                 <div class="card-body">
                     Open or refresh your wallet and confirm incoming transaction.
                     <a href="#" data-bs-toggle="tooltip" data-bs-title="
                        It will be done automatically after full synchronization of the wallet, you may need to refresh the history.">
                        <b><sup><i class="fa-solid fa-circle-info text-light"></i></sup></b>
                     </a>
                     <br><br>
                     <p>After <span><b>180</b></span> seconds transaction will be automatically cancelled.</p>
                 </div>
                 <div class="card-footer mb-0 pb-0">
                     <small class="text-light-50"><pre>ID: ${task.result.result['tx_slate_id']}</pre></small>
                 </div>
             </div>`,
        timer: 1000*60*3,
        position: 'center',
        timerProgressBar: true,
        showCancelButton: true,
        cancelButtonText: `<i class="fa fa-xmark"></i> CANCEL TRANSACTION`,
        allowOutsideClick: false,
        cancelButtonColor: 'orange',
        showConfirmButton: true,
        confirmButtonText: `<i class="fa fa-check"></i> CONFIRM`,
        confirmButtonColor: 'green',

        didOpen: () => {
            getToolTips()
            const b = Swal.getHtmlContainer().querySelector('span').querySelector('b')
            timerInterval = setInterval(() => {
                b.textContent = (Swal.getTimerLeft() / 1000).round(0)
            }, 1000)
        },
        willClose: () => {clearInterval(timerInterval)}

    }).then(async (aResult) => {
        let tResult = task.result.result
        console.log(await aResult)
        console.log(tResult)
        updateForm(spinnerHTMLsm)

        // Closed by timer
        if (aResult.dismiss === Swal.DismissReason.timer) {
            console.log('Closed by timer')
            await cancelTransaction(tResult['tx_slate_id'])
            await spawnToast('error', 'Transaction time expired')
            await resetForm()

        // Canceled by user
        } else if (aResult.dismiss === Swal.DismissReason.cancel) {
            console.log('Canceled by user')
            await cancelTransaction(tResult['tx_slate_id'])
            await spawnToast('warning', 'Transaction cancelled by user.')
            await resetForm()

        // Confirmed by user
        } else if (aResult.isConfirmed) {
            updateForm(spinnerHTML)
            feedbackField.text('Waiting for response..')

            let taskFinished = false
            console.log('Confirmed by user')
            let result = await finalizeTransaction(tResult['tx_slate_id'])
            console.log(result)
            let task = await getTaskStatus(result.result['task_id'])
            console.log(task)

            while (!taskFinished) {
                if (task.status === 'finished') {
                    feedbackField.text('')
                    taskFinished = true
                    await finishedTaskHandler(task, 'confirmed')
                } else if (task.status === 'failed') {
                    feedbackField.text('')
                    taskFinished = true
                    console.log('failed' + task.result)
                    await cancelTransaction(tResult['tx_slate_id'])
                    transactionFailedAlert("Receiver wallet was offline, transaction is cancelled.")
                } else {
                    console.log(task.status)
                    await sleep(2000)
                    task = await getTaskStatus(result.result['task_id'])
                }
            }
        }
    })
}


// CONFIRMED TRANSACTION ALERT
function transactionConfirmedAlert() {
    Swal.fire({
        icon: 'success',
        title: `Transaction confirmed!`,
        html:`Your EPIC will be spendable after <b>1 confirmation</b>, on average ~<b>1 minute</b>.`,
        position: 'center',
        showConfirmButton: true,
        confirmButtonText: `<i class="fa fa-check"></i> OK`,
    }).then(async (result) => {
        await resetForm()
        console.log('alert result:', result)
    })
}


// FAILED TRANSACTION ALERT
function transactionFailedAlert(reason) {
        Swal.fire({
        icon: 'warning',
        title: `UNSUCCESSFUL`,
        html:`
             ${reason}
             <hr class="mt-4" />
             <div class="my-2">
                 Need support? Join
                 <a href="https://t.me/GiverOfEpic" target="_blank" class="text-dark">
                     <i class="fa-brands fa-telegram ms-1"></i> <b>GiverOfEpic</b>. 
                 </a>
             </div>
             <hr class="mb-2" />
             `,
        position: 'center',
        showConfirmButton: true,
        confirmButtonText: `<i class="fa fa-check"></i> CONFIRM`,
    }).then(async (result) => {
        await resetForm()
        console.log('alert result:', result)
    })
}


// HANDLE FINISHED TASK
async function finishedTaskHandler(task, type) {
    console.log(task.result);
    if (!task.result) {
        console.log('error: task finished but no results');
    } else if (task.result.error) {
        if (type === 'confirmed') {
            await transactionFailedAlert(task.result.message)
        } else if (type === 'sent') {
            await transactionFailedAlert(task.result.message)
        }
    } else {
        if (type === 'confirmed') {
            await transactionConfirmedAlert()
        } else if (type === 'sent') {
            await transactionInitializedAlert(task)
        }
    }
}


// SPAWN TOAST NOTIFICATION
async function spawnToast(icon, title) {
    const Toast = Swal.mixin({
        toast: true,
        position: 'top',
        iconColor: 'white',
        customClass: {
            popup: 'colored-toast'
        },
        showConfirmButton: false,
        timer: 2500,
        timerProgressBar: true
    })
    await Toast.fire({
        icon: icon,
        title: title,
    })
}


// GET TASK STATUS FROM REDIS/QUEUE
async function getTaskStatus(taskId) {
    let query = `/api/wallet/get_task/id=${taskId}`

    return await fetch(query, {
        method: 'GET',
        headers: {
            'Accept': '*/*',
            'Content-Type': 'application/json'
        }
    }).then(response => response.json())
      .catch(err => {console.log(err)})
}


// ENCRYPT REQUEST PAYLOAD
async function encryptPayload(payload) {
    let query = `api/wallet/encrypt_data`

    return await fetch(query, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
    }).then(response => response.json())
      .catch(err => {console.log(err)})
}


// CANCEL TRANSACTION
function cancelTransaction(tx_slate_id) {
    let query = `/api/wallet/cancel_transaction/tx_slate_id=${tx_slate_id}}`
    let body = {'tx_slate_id': tx_slate_id}

    return fetch(query, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(body)
    }).then(response => response.json())
        .catch(err => {console.log(err)})
}


// FEEDBACK IF CONNECTION WITH DB FAILED
checkStatus = async (response) => {
    if (response.status >= 200 && response.status < 300)
        return await response.json()
    feedbackField.text(response.status)
}


// UPDATE ADDRESS INPUT AND CONFIRM BUTTON STATE
function updateForm(conf_btn_html) {
    receiveButton.attr('disabled', true)
    receiveButton.html(conf_btn_html)
    addressIcon.css('color', 'grey');
    address.attr('disabled', true)
}


// RESET ADDRESS INPUT AND CONFIRM BUTTON STATE
async function resetForm() {
    receiveButton.html('RECEIVE')
    receiveButton.timedDisable(5);
    await sleep(5000)
    receiveButton.attr('disabled', false);
    addressIcon.css('color', 'green');
    address.attr('disabled', false);
}

function toast(text='', icon='info', timer=3000, timerProgressBar=false) {
    const Toast = Swal.mixin({
        toast: true,
        showConfirmButton: true,
        didOpen: (toast) => {
        toast.addEventListener('mouseenter', Swal.stopTimer)
        toast.addEventListener('mouseleave', Swal.resumeTimer)
        }
    });
    Toast.fire({
        icon: icon,
        text: text,
        timer: timer,
        timerProgressBar: timerProgressBar,
    });
}

// ROUND NUMBERS
Number.prototype.round = function(places) {
  return +(Math.round(this + "e+" + places)  + "e-" + places);
}


//TOOLTIP
$(document).ready(function(){
    getToolTips()
});
function getToolTips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))
}


// SLEEP/WAIT FUNCTION
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}


$.fn.timedDisable = function(time) {
    if (time == null) {time = 5}
    let seconds = Math.ceil(time); // Calculate the number of seconds

    return $(this).each(function() {
      const disabledElem = $(this);
      const originalText = this.innerHTML; // Remember the original text content

    // append the number of seconds to the text
    disabledElem.text(originalText + ' (' + seconds + ')');

    // do a set interval, using an interval of 1000 milliseconds
    //     and clear it after the number of seconds counts down to 0
      const interval = setInterval(function () {
          seconds = seconds - 1;
          // decrement the seconds and update the text
          disabledElem.text(originalText + ' (' + seconds + ')');
          if (seconds === 0) { // once seconds is 0...
              disabledElem.text(originalText); //reset to original text
              clearInterval(interval); // clear interval
          }
      }, 1000);
    });
};

// // FINALIZE TRANSACTION
// function finalizeTransaction(tx_slate_id) {
//     let query = `/api/finalize_transaction/tx_slate_id=${tx_slate_id}&address=${address.val()}`
//
//     return fetch(query, {
//         method: 'GET',
//         headers: headers
//     ).then(response => response.json())
//       .catch(err => {console.log(err)})
// }