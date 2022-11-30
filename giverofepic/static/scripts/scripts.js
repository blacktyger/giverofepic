let API_CALLS = 0

const spinnerHTMLsm = `<div class="spinner-grow spinner-grow-sm fs-6" role="status"></div>`
const spinnerHTML = `<div class="spinner-grow spinner-grow-sm ms-1" role="status"></div>
                     <div class="spinner-grow spinner-grow-sm" role="status"></div>
                     <div class="spinner-grow spinner-grow-sm" role="status"></div>`



// Accordion buttons animation
let rotation1 = 0;

$(document).ready(function(){
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))

    $("#costsIcon").rotate(rotation1);

    $("#headingOne").click(function(){
        rotation1 += 180;
        $("#costsIcon").rotate(rotation1);
    });
});


async function updateTask(taskId) {
    let query = `/api/get_task/id=${taskId}`

    return await fetch(query, {
        method: 'GET',
        headers: {
            'Accept': '*/*',
            'Content-Type': 'application/json'
        }
    });
}

// esZ7pubuHN4Dyn8WsCRjzhe12ZtgHqmnthGoopA1iSskm2xwXcKK

checkStatus = async (response) => {
    if (response.status >= 200 && response.status < 300)
      return await response.json()
    let feedbackField = $('.feedbackField')
    feedbackField.text(response.status)
}


async function sendTransaction() {
    let address = $('#walletAddress')
    let feedbackField = $('.feedbackField')
    let amount = 0.01
    let query = "api/initialize_transaction"
    let body = {receiver_address: address.val(), amount: amount}
    let taskFinished = false

    feedbackField.html(spinnerHTML)

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
            let task = await updateTask(taskId)
                .then(response => response.json())
                .catch(err => {console.log(err)})

            while (!taskFinished) {
                if (task.status === 'finished') {
                    console.log(task.status)
                    taskFinished = true
                } else if (task.status === 'failed') {
                    console.log(task.status)
                    taskFinished = true
                } else if (task.status === 'queued'){
                    console.log(task.status)
                    // feedbackField.text(task.status)
                    await sleep(3000)

                    task = await updateTask(taskId)
                    .then(response => response.json())
                    .catch(err => {console.log(err)})

                    console.log(task)
                }
            }
        } else {
            taskFinished = true
            feedbackField.text(response.message)
        }
    }
}

// Return URL to flag .svg for given currency code
function getFlagIcon(currencyCode) {
    const currencyToCountry = {'GBP': 'gb', 'USD': 'us', 'EUR': 'eu', 'PLN': 'pl', 'CNY': 'cn'}
    return `frontend/static/img/flags/${currencyToCountry[currencyCode]}.svg`
}


// Return URL to flag .svg for given currency code
function getPoolIcon(pool) {
    return `frontend/static/img/${pool}`
}


async function updateCalculator() {
    // Get values from all fields and save as object
    const body = {
        "unit": $(".hashrateUnits").html(),
        "hashrate": $("#hashrate").val(),
        "algorithm": $("#algorithmSelect").val(),
        "currency": $("#currencySelect").val(),
        "pool": $("#poolSelect").val(),
        "pool_fee": $("#pool_fee").val(),
        "energy_price": $("#energy").val(),
        "power_consumption": $("#consumption").val()
    }

    // Update UI fields before api call
    updateAlgo(body.algorithm)
    $('.hashrate').text($('#hashrate').val())

    // Execute API call only if all fields have value (0 is accepted)
    if (body.hashrate && body.power_consumption &&
        body.energy_price && body.pool_fee) {

        const data = await apiCall(body, '/calculate', "POST")
        console.log('API RESPONSE:' + data)

        if (data) {
            // Update UI fields after success api call
            $('#result-income-1').text(parseFloat(data.coins_per_day[1]).round(3))
            $('#result-income-7').text((parseFloat(data.coins_per_day[1]) * 7).round(3))
            $('#result-costs-1').text(parseFloat(data.cost_total[1]).round(3))
            $('#result-costs-7').text((parseFloat(data.cost_total[1]) * 7).round(3))
            $('#result-profit-1').text(parseFloat(data.profit_per_day[1]).round(3))
            $('#result-profit-7').text((parseFloat(data.profit_per_day[1]) * 7).round(3))
            $('.epic-price').text(parseFloat(data.epic_price).round(2))
        } else {
            console.log('API CALL UNSUCCESSFUL')
        }
    }
}


async function apiCall(body, query, method='POST') {
    let spinnerField = $('#resultSpinner')
    let beforeSpinner = spinnerField.html()

    if (beforeSpinner === spinnerHTML) {
        console.log('API CALLS IN THIS SESSION: ', API_CALLS)
        return
    }

    API_CALLS += 1
    spinnerField.html(spinnerHTML)

    let response = await fetch(query, {
        method: method,
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(body),
    }).then(response => response.json()
    ).catch(err => console.log(err))

    spinnerField.html(beforeSpinner)
    console.log('API CALLS IN THIS SESSION: ', API_CALLS)
    return response
}


// Update algorithm related fields
function updateAlgo(algorithm) {
    const algoSettings = {
        'progpow': {icon: 'sports_esports', units: 'MH/s', hardware: 'GPU'},
        'randomx': {icon: 'memory', units: 'KH/s', hardware: 'CPU'},
        'cuckoo': {icon: 'dns', units: 'GH/s', hardware: 'ASIC'}
        }
    $('.gearIcon').text(algoSettings[algorithm]['icon'])
    $('.gearType').text(algoSettings[algorithm]['hardware'])
    $('.hashrateUnits').text(algoSettings[algorithm]['units'])
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


Number.prototype.round = function(places) {
  return +(Math.round(this + "e+" + places)  + "e-" + places);
}

jQuery.fn.rotate = function(degrees) {
    $(this).css({'-webkit-transform' : 'rotate('+ degrees +'deg)',
                 '-moz-transform' : 'rotate('+ degrees +'deg)',
                 '-ms-transform' : 'rotate('+ degrees +'deg)',
                 'transform' : 'rotate('+ degrees +'deg)'});
};

// ===================== NOTEPAD



// document.addEventListener('DOMContentLoaded', function () {
//     keep_alive_server()
//     try {setInterval(keep_alive_server, 5 * 1000)()
//     } catch (error) {}
// });

// Running Loop keeping alive connection with back-end
function keep_alive_server() {
    fetch(document.location + "keep-alive/?alive=true", {
        method: 'GET',
        cache: 'no-cache'
    })
        .then(resp => resp.json())
        .then(data => {
            document.getElementById("heightText").innerHTML = data.height
            document.getElementById("algoIcon").innerHTML = data.algo.icon
            document.getElementById("algoText").innerHTML = data.algo.text
            document.getElementById("deltaText").innerHTML = data.delta
        })
        .catch(error => {console.error(error)});
    }

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}