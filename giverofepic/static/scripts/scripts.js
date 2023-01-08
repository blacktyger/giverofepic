let feedbackField = $('.feedbackField')
let confirmButton = $('#confirmButton')
let addressIcon = $('.addressIcon')
let address = $('#walletAddress')


const spinnerHTMLsm = `<div class="spinner-border spinner-border-sm fs-6" role="status"></div>`
const spinnerHTML = `<div class="spinner-grow spinner-grow-sm align-middle" role="status"></div>
                     <div class="spinner-grow spinner-grow-sm align-middle" role="status"></div>
                     <div class="spinner-grow spinner-grow-sm align-middle" role="status"></div>`


// PROCESS USER REQUEST
async function sendTransaction() {
    let taskFinished = false
    let amount = 0.01
    let query = "api/initialize_transaction"
    let body = {receiver_address: address.val(), amount: amount}

    updateForm(spinnerHTML)
    // transactionFailedAlert('dupa')
    // listenForResponseAlert({})

    let response = await fetch(query, {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(body),
      }).then(checkStatus)
        // .then(r => r)
        .catch(err => console.log(err))

    if (response) {
        if (!response.error && 'result' in response) {
            let taskId = response.result.task_id
            let task = await getTaskStatus(taskId)

            while (!taskFinished) {
                if (task.status === 'finished') {
                    taskFinished = true
                    await finishedTaskHandler(task, 'sent')
                } else if (task.status === 'failed') {
                    taskFinished = true
                    transactionFailedAlert(task)
                    console.log(task.status)
                } else {
                    console.log(task.status)
                    await sleep(2000)
                    task = await getTaskStatus(taskId)
                }
            }
        } else {userRestrictedAlert(response.message)}
    }
    await resetForm()
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


async function listenForResponseAlert(task) {
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
                     Open your Wallet and confirm incoming transaction.
                     <a href="#" data-bs-toggle="tooltip" data-bs-title="
                        It will be done automatically after full synchronization of the wallet">
                        <b><sup><i class="fa-solid fa-circle-info text-light"></i></sup></b>
                     </a>
                     <br><br>
                     <p>After <span><b>180</b></span> seconds transaction will be automatically canceled.</p>
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
            // Swal.showLoading()
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

        // Closed by timer
        if (aResult.dismiss === Swal.DismissReason.timer) {
            console.log('Closed by timer')
            await cancelTransaction(tResult['tx_slate_id'])

        // Canceled by user
        } else if (aResult.dismiss === Swal.DismissReason.cancel) {
            console.log('Canceled by user')
            await cancelTransaction(tResult['tx_slate_id'])

        // Confirmed by user
        // TODO: finalize_transaction
        } else if (aResult.isConfirmed) {
            let taskFinished = false
            console.log('Confirmed by user')
            let result = await finalizeTransaction(tResult['tx_slate_id'])
            console.log(result)
            let task = await getTaskStatus(result.result['task_id'])
            console.log(task)

            while (!taskFinished) {
                if (task.status === 'finished') {
                    taskFinished = true
                    await finishedTaskHandler(task, 'confirmed')
                } else if (task.status === 'failed') {
                    taskFinished = true
                    console.log('failed' + task)
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
        html:``,
        position: 'center',
        showConfirmButton: true,
        confirmButtonText: `<i class="fa fa-check"></i> OK`,
    }).then((result) => {console.log('alert result:', result)})
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
    }).then((result) => {console.log('alert result:', result)})
}


// HANDLE FINISHED TASK
async function finishedTaskHandler(task, type) {
    console.log(task.result);
    if (!task.result) {
        console.log('error: task finished but no results');
    } else if (task.result.error) {
        if (type === 'confirmed') {
            transactionFailedAlert(task.result.message)
        } else if (type === 'sent') {
            transactionFailedAlert(task.result.message)
        }
    } else {
        if (type === 'confirmed') {
            transactionConfirmedAlert()
        } else if (type === 'sent') {
            await listenForResponseAlert(task)
        }
    }
}


// GET TASK STATUS FROM REDIS/QUEUE
async function getTaskStatus(taskId) {
    let query = `/api/get_task/id=${taskId}`

    return await fetch(query, {
        method: 'GET',
        headers: {
            'Accept': '*/*',
            'Content-Type': 'application/json'
        }
    }).then(response => response.json())
      .catch(err => {console.log(err)})
}


// FINALIZE TRANSACTION
function finalizeTransaction(tx_slate_id) {
    let query = `/api/finalize_transaction/tx_slate_id=${tx_slate_id}`

    return fetch(query, {
        method: 'GET',
        headers: {
            'Accept': '*/*',
            'Content-Type': 'application/json'
        }
    }).then(response => response.json())
      .catch(err => {console.log(err)})
}


// CANCEL TRANSACTION
function cancelTransaction(tx_slate_id) {
    let query = `/api/cancel_transaction/tx_slate_id=${tx_slate_id}`

    return fetch(query, {
        method: 'GET',
        headers: {
            'Accept': '*/*',
            'Content-Type': 'application/json'
        }
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
    confirmButton.attr('disabled', true)
    confirmButton.html(conf_btn_html)
    addressIcon.css('color', 'grey');
    address.attr('disabled', true)
}


// RESET ADDRESS INPUT AND CONFIRM BUTTON STATE
async function resetForm() {
    confirmButton.html('CONFIRM')
    confirmButton.timedDisable(5);
    await sleep(5000)
    confirmButton.attr('disabled', false);
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
