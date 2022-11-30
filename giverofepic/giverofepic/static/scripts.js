
// document.addEventListener('DOMContentLoaded', function () {
//     keep_alive_server()
//     try {setInterval(keep_alive_server, 5 * 1000)()
//     } catch (error) {}
// });


function toast(icon='info', text='', timer=2000, timerProgressBar=false) {
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
};

jQuery.fn.rotate = function(degrees) {
    $(this).css({'-webkit-transform' : 'rotate('+ degrees +'deg)',
                 '-moz-transform' : 'rotate('+ degrees +'deg)',
                 '-ms-transform' : 'rotate('+ degrees +'deg)',
                 'transform' : 'rotate('+ degrees +'deg)'});
};

// Accordion buttons animation
let rotation1 = 0;
let rotation2 = 0;
let rotation3 = 0;

$(document).ready(function(){
    $("#headingOne").click(function(){
        rotation1 += 180;
        $("#costsIcon").rotate(rotation1);
    });
    $("#headingTwo").click(function(){
        rotation2 += 180;
        $("#rigIcon").rotate(rotation2);
    });
    $("#headingThree").click(function(){
        rotation3 += 180;
        $("#resultIcon").rotate(rotation3);
    });
});

// Return URL to flag .svg for given currency code
function getFlagIcon(currencyCode) {
    const currencyToCountry = {'GBP': 'gb', 'USD': 'us', 'EUR': 'eu', 'PLN': 'pl', 'CNY': 'cn'}
    return `frontend/static/img/flags/${currencyToCountry[currencyCode]}.svg`
}


// Listen for currency select changes and manage flag icon
$('#currencySelect').on('change', function() {
    $('#flagIcon').attr('src', getFlagIcon(this.value))
});


// Listen for algorithm select changes, update units
$('#algorithmSelect').on('change', function() {
    const algoSettings = {
        'progpow': {icon: 'sports_esports', units: 'MH/s'},
        'randomx': {icon: 'memory', units: 'KH/s'},
        'cuckoo': {icon: 'dns', units: 'GH/s'}
        }

    $('#algoIcon').text(algoSettings[this.value]['icon'])
    $('#hashrateUnits').text(algoSettings[this.value]['units'])
});


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


function apiCall(body, query, method='POST') {
    return fetch(query, {
        method: method,
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(body),
    }).then(response => response.json()
    ).catch(err => console.log(err))

}