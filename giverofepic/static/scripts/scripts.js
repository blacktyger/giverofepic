let feedbackField = $('.feedbackField')
let confirmButton = $('#confirmButton')
let addressIcon = $('.addressIcon')
let address = $('#walletAddress')


const spinnerHTMLsm = `<div class="spinner-grow spinner-grow-sm fs-6" role="status"></div>`
const spinnerHTML = `<div class="spinner-grow spinner-grow-sm align-middle" role="status"></div>
                     <div class="spinner-grow spinner-grow-sm align-middle" role="status"></div>
                     <div class="spinner-grow spinner-grow-sm align-middle" role="status"></div>`

// esZ7pubuHN4Dyn8WsCRjzhe12ZtgHqmnthGoopA1iSskm2xwXcKK


function transactionFailedAlert(reason) {
        Swal.fire({
        icon: 'warning',
        title: `REQUEST UNSUCCESSFUL`,
        html:`${reason}`,
        position: 'center',
        showConfirmButton: true,
        confirmButtonText: `<i class="fa fa-check"></i> OK`
    }).then((result) => {console.log(result)})
}


// SweetAlert2 instance spawned when first step of the transaction was successful
// and script is waiting for receiving wallet to send response slate.
function listenForResponseAlert() {
    let timerInterval

    Swal.fire({
        // icon: 'info',
        // iconHtml:`<span class="fs-6">?</span>`,
        // title: `<!--<i class="fa-regular fa-circle-check"></i> CONFIRM TRANSACTION-->`,
        html:
            `<div class="card mt-1 bg-blue text-light">
                 <div class="card-img"><img class="card-img" src="static/img/stack-wallet.png"></div>
                 <div class="card-body">
                     Open your <b>Stack-Wallet</b> and confirm incoming transaction.
                     <a href="#" data-bs-toggle="tooltip" data-bs-title="
                        Just open your wallet, it will be done automatically after full synchronization">
                        <b><sup><i class="fa-solid fa-circle-info text-light"></i></sup></b>
                     </a>
                     <br><br>
                     <p>After <span><b>180</b></span> seconds transaction will be automatically canceled.</p>
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
    }).then((result) => {
        console.log(result)
        //TODO: Closed by timer: cancel transaction and remove slate
        if (result.dismiss === Swal.DismissReason.timer) {
        console.log('I was closed by the timer')
        }
    })
}


async function sendTransaction() {
    let taskFinished = false
    let amount = 0.01
    let query = "api/initialize_transaction"
    let body = {receiver_address: address.val(), amount: amount}
    confirmButton.attr('disabled', 'true')
    confirmButton.html(spinnerHTML)

    let response = await fetch(query, {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(body),
      }).then(checkStatus)
        .then(r => r)
        .catch(err => console.log(err))

    if (response) {
        if (!response.error && 'result' in response) {
            let taskId = response.result.task_id
            let task = await getTaskStatus(taskId)

            while (!taskFinished) {
                if (task.status === 'finished') {
                    console.log(task.status)
                    taskFinished = true
                    taskFeedback(task)
                    confirmButton.html('CONFIRM')

                } else if (task.status === 'failed') {
                    console.log(task.status)
                    taskFinished = true
                    confirmButton.html('CONFIRM')
                    console.log(task)
                    transactionFailedAlert(task)

                } else {
                    await sleep(2000)
                    task = await getTaskStatus(taskId)
                    console.log(task.status)
                }
            }
        } else {
            taskFinished = true
            feedbackField.html(response.message)
        }
    }
}


// HANDLE FINISHED TASK
function taskFeedback(task) {
    console.log(task.result);

    if (!task.result) {
        console.log('error: task finished but no results');
        return
    }

    if (task.result.error) {
        let addr = address.val()
        address.attr('disabled', 'true').val('')
        address.attr('placeholder', addr)
        addressIcon.css('color', 'grey');
        transactionFailedAlert(task.result.message)
    } else {
        listenForResponseAlert()
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


// FEEDBACK IF CONNECTION WITH DB FAILED
checkStatus = async (response) => {
    if (response.status >= 200 && response.status < 300)
        return await response.json()

    feedbackField.text(response.status)
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

